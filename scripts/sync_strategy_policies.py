"""
策略政策同步脚本:把 config/strategy_policy/*.yaml 写入 strategy_policies 表。

为什么需要这个脚本:
    0015_governance_core.sql 的 research_inputs / investment_theses / decision_records
    都有外键 (policy_id, version) → strategy_policies。
    也就是说,任何 ResearchInput 写入前必须先有 strategy_policies。
    而现在策略只在 YAML 文件里(在版本控制中),还没进数据库。
    这个脚本就是把"已在版本控制里的策略"同步到数据库,只做同步不做审批。

纪律:
    1. 不删除/覆盖数据库已有数据(用 INSERT OR IGNORE)
    2. 不修改已 active 的策略字段(由应用层做,不在本脚本)
    3. 默认保留 YAML 里的 policy_status(由产品/运营在 UI 上手动切到 active)
       原因:阶段 0 不希望 smoke 脚本自动激活生产策略

用法:
    python scripts/sync_strategy_policies.py <db_path>
    不传 db_path 默认用 /tmp/fle-p0/governance.sqlite
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

# 注册自定义日期适配器，避免 Python 3.12+ 弃用默认适配器的警告
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())

# 把项目根目录加入 sys.path,让 migration runner 可用
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _parse_yaml(path: Path) -> dict[str, Any]:
    """用 PyYAML 解析(pyproject.toml 已声明依赖)。"""
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: 顶层不是 dict")
    return data


def sync_yaml_to_db(yaml_path: Path, db_path: Path) -> dict[str, Any]:
    """把单份 YAML 同步进 strategy_policies。返回摘要。"""
    parsed = _parse_yaml(yaml_path)
    if "policy_id" not in parsed or "version" not in parsed:
        raise ValueError(f"{yaml_path}: missing policy_id or version")

    policy_id = str(parsed["policy_id"])
    version = int(parsed["version"])
    business_mode = str(parsed.get("business_mode", "private_strategy"))
    policy_status_yaml = str(parsed.get("policy_status", "draft"))
    approved_for_production = int(bool(parsed.get("approved_for_production", False)))

    # JSON 字段:把 list / dict 值以 json.dumps 存到对应 *_json 列
    json_keys = [
        "market_scope",
        "position_limit",
        "allowed_universe",
        "excluded_universe",
        "valuation_policy",
        "monitoring_policy",
        "investment_policy",
        "candidate_priority",
    ]
    json_vals: dict[str, str | None] = {}
    for k in json_keys:
        v = parsed.get(k)
        if v is None:
            json_vals[k + "_json"] = None
        else:
            json_vals[k + "_json"] = json.dumps(v, ensure_ascii=False)

    conn = sqlite3.connect(str(db_path))
    try:
        if not _table_exists(conn, "strategy_policies"):
            raise RuntimeError(
                f"strategy_policies 表不存在,db={db_path}。"
                "请先跑 migration(run_migrations)"
            )

        cols = [
            "policy_id", "version", "business_mode", "policy_status",
            "approved_for_production", "strategy_name", "strategy_type",
            "investment_horizon", "benchmark", "target_return", "risk_budget",
            "maximum_drawdown", "leverage_limit", "liquidity_limit",
            "effective_from", "effective_to", "approved_by", "schema_doc",
            "change_policy",
        ] + list(json_vals.keys())

        placeholders = ",".join("?" * len(cols))
        col_list = ",".join(cols)
        values = [
            policy_id,
            version,
            business_mode,
            policy_status_yaml,
            approved_for_production,
            str(parsed.get("strategy_name", "")),
            str(parsed.get("strategy_type", "")),
            parsed.get("investment_horizon"),
            parsed.get("benchmark"),
            parsed.get("target_return"),
            parsed.get("risk_budget"),
            parsed.get("maximum_drawdown"),
            parsed.get("leverage_limit"),
            parsed.get("liquidity_limit"),
            parsed.get("effective_from"),
            parsed.get("effective_to"),
            parsed.get("approved_by"),
            parsed.get("schema_doc", "docs/p0/domain-language-v0.md"),
            parsed.get("change_policy", "append_new_version"),
        ] + list(json_vals.values())

        before = conn.execute(
            "SELECT 1 FROM strategy_policies WHERE policy_id=? AND version=?",
            (policy_id, version),
        ).fetchone()
        conn.execute(
            f"INSERT OR IGNORE INTO strategy_policies ({col_list}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        after = conn.execute(
            "SELECT 1 FROM strategy_policies WHERE policy_id=? AND version=?",
            (policy_id, version),
        ).fetchone()

        return {
            "policy_id": policy_id,
            "version": version,
            "was_present": before is not None,
            "now_present": after is not None,
        }
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _ensure_migrations(db_path: Path) -> None:
    """如果 strategy_policies 不存在,跑 migration。"""
    conn = sqlite3.connect(str(db_path))
    try:
        exists = _table_exists(conn, "strategy_policies")
    finally:
        conn.close()
    if not exists:
        from app.persistence.migrations_runner import run_migrations  # noqa: E402

        run_migrations(str(db_path))


def main(argv: list[str]) -> int:
    yaml_dir = _PROJECT_ROOT / "config" / "strategy_policy"
    if not yaml_dir.exists():
        print(f"FAIL: {yaml_dir} 不存在")
        return 1

    db_path = Path(
        argv[0] if argv else os.environ.get("FLE_DB_PATH", "/tmp/fle-p0/governance.sqlite")
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 不删除已有数据库;复用或新建
    _ensure_migrations(db_path)
    print(f"[1/4] migrations OK: {db_path}")

    results = []
    for ypath in sorted(yaml_dir.glob("*.yaml")):
        r = sync_yaml_to_db(ypath, db_path)
        results.append((ypath.name, r))
        print(f"[2/4] synced: {ypath.name} -> policy_id={r['policy_id']} v{r['version']}")

    # 同步策略后,编译宪法
    from app.governance.constitution import create_constitution_from_policy

    for ypath in sorted(yaml_dir.glob("*.yaml")):
        policy_dict = _parse_yaml(ypath)
        policy_id = str(policy_dict["policy_id"])
        version = int(policy_dict["version"])
        constitution = create_constitution_from_policy(policy_dict, policy_id, version)
        print(
            f"[3/4] constitution: {ypath.name} -> "
            f"{len(constitution.criteria)} criteria, valid={constitution.validation.valid}"
        )
        if constitution.validation.warnings:
            for w in constitution.validation.warnings:
                print(f"        warning: {w}")

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT policy_id, version, business_mode, policy_status, strategy_name FROM strategy_policies ORDER BY policy_id, version"
        ).fetchall()
    finally:
        conn.close()
    print(f"[4/4] strategy_policies now has {len(rows)} rows:")
    for r in rows:
        print(f"  - {r[0]} v{r[1]} ({r[2]}) [{r[3]}] {r[4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
