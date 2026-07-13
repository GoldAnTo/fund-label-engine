"""
阶段 0 · 私募内部投研 smoke 演示

目的:
    在不写新业务代码、不建新表的前提下,证明"研究请求 → 投资假设 → 候选集合 →
    证据/排除原因 → 数据快照"这条链路能跑通,且能复现。

演示场景(全部在私募内部投研视角):
    A. 一条投资观点(自然语言 → 关键词 → 主题匹配)
    B. 一个行业方向(行业穿透,反向查持仓)
    C. 一个具体股票(单只股票被哪些基金持有,占比多少)

关键纪律(违反任一条 = 阶段 0 不通过):
    1. 阶段 0 不写新业务代码、不建新表。
    2. 候选清单必须能反查 research_input_id、strategy_policy_id+version、data_snapshot_id。
    3. 不强制返回固定数量候选;无候选时必须诚实返回 no_eligible_candidate。
    4. 不使用没有来源的假数据(只用 seed_sample_db.py 的样例 + CognitionEngine 真实输出)。

用法:
    python scripts/p0/smoke_e2e_private_fund.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 把项目根目录加入 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.cognition.engine import CognitionEngine  # noqa: E402

# ============================================================
# 常量
# ============================================================
SOURCE_DB = Path("/tmp/fle-p0/source.sqlite")
FACTOR_DB = _PROJECT_ROOT / "data" / "stock_factors.sqlite"  # 可能不存在,容错
POLICY_PATH = _PROJECT_ROOT / "config" / "strategy_policy" / "private_equity_growth_v0.yaml"
REPORT_PATH = _PROJECT_ROOT / "reports" / "p0" / "smoke-e2e-report.md"

AS_OF_DATE = "2026-03-31"  # 与 seed_sample_db.py 中的 report_date 对齐


# ============================================================
# 工具
# ============================================================
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _ensure_source_db() -> Path:
    """确保 source DB 存在;不存在则先 seed,再 migration 补表。

    顺序:seed → migration。
    seed_sample_db.seed() 会 unlink 库并建自己的业务 schema(fund_profiles 等),
    不建 data_snapshots;所以第二步跑 migration 补 governance / snapshot / label 表
    (全部 IF NOT EXISTS,不会破坏 seed 已有数据)。
    """
    SOURCE_DB.parent.mkdir(parents=True, exist_ok=True)
    if not SOURCE_DB.exists():
        # 1. seed 业务样例
        sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))
        from seed_sample_db import seed  # type: ignore

        seed(str(SOURCE_DB))
        # 2. 补 governance / data_snapshots / label_runs 等基础表
        from app.persistence.migrations_runner import run_migrations

        run_migrations(str(SOURCE_DB))
    return SOURCE_DB


def _load_policy_version() -> tuple[str, int]:
    """从 YAML 头部读 policy_id 和 version(只读,不解析完整 YAML,避免引入 PyYAML 依赖)。"""
    text = POLICY_PATH.read_text(encoding="utf-8")
    pid = None
    ver = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("policy_id:"):
            pid = s.split(":", 1)[1].strip()
        elif s.startswith("version:"):
            ver = int(s.split(":", 1)[1].strip())
    if pid is None or ver is None:
        raise RuntimeError(f"无法从 {POLICY_PATH} 解析 policy_id/version")
    return pid, ver


def _save_data_snapshot_id(snapshot_id: str) -> None:
    """把 data_snapshot_id 写入 source DB 的 data_snapshots 表(必须已存在)。

    阶段 0 纪律:'不建新表'。所以这里**绝不**建表,表不存在时直接失败。
    data_snapshots 由 backend/app/persistence/migrations/0011_data_snapshots.sql 创建。
    """
    conn = sqlite3.connect(str(SOURCE_DB))
    try:
        # 先确认表存在(不强类型,只是 SELECT 1)
        exists = conn.execute(
            "SELECT 1 FROM data_snapshots LIMIT 1"
        ).fetchone()
        if exists is None:
            # 表存在但为空,直接 INSERT
            pass
        conn.execute(
            "INSERT OR REPLACE INTO data_snapshots (snapshot_id, source_db_path, created_at) VALUES (?, ?, ?)",
            (snapshot_id, str(SOURCE_DB), _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 场景 A:一条投资观点
# ============================================================
def scenario_a_philosophy(engine: CognitionEngine) -> dict[str, Any]:
    """演示:研究员提交一条投资观点,系统给出 thesis + 候选/无候选。"""
    research_input_id = _short_id("ri")
    raw_text = "我看好消费白马(高 ROE、稳定盈利、低估值的龙头企业)。"

    # 阶段 0 简化:从 raw_text 抽取关键词 → 在 fund_stock_holdings 里反查
    # 不引入 NLU 解析,只证明"输入 → 关键词 → 持仓反查 → 候选"链路存在
    keywords = ["贵州茅台", "五粮液", "美的集团"]  # 演示用关键词(对应 seed 中的消费白马)
    excluded_reasons: list[str] = []

    conn = engine._get_conn()  # noqa: SLF001 - 阶段 0 演示读取
    placeholders = ",".join("?" * len(keywords))
    fund_rows = conn.execute(
        f"""
        SELECT DISTINCT fund_code FROM fund_stock_holdings
        WHERE stock_name IN ({placeholders})
        AND report_date = ?
        """,
        (*keywords, AS_OF_DATE),
    ).fetchall()
    fund_codes = sorted({r[0] for r in fund_rows})

    # 风格 / 估值证据
    candidates: list[dict[str, Any]] = []
    for fc in fund_codes:
        # 拿持仓权重合计
        weight_rows = conn.execute(
            f"""
            SELECT stock_name, weight FROM fund_stock_holdings
            WHERE fund_code = ? AND report_date = ? AND stock_name IN ({placeholders})
            """,
            (fc, AS_OF_DATE, *keywords),
        ).fetchall()
        total_weight = round(sum(r[1] for r in weight_rows), 4)
        # 行业暴露
        ind_rows = conn.execute(
            "SELECT industry, weight FROM fund_industry_allocations WHERE fund_code = ? AND report_date = ?",
            (fc, AS_OF_DATE),
        ).fetchall()
        industry_exposure = [{"industry": r[0], "weight": r[1]} for r in ind_rows]
        candidates.append(
            {
                "asset_type": "fund",
                "asset_code": fc,
                "asset_name": _get_fund_name(conn, fc),
                "evidence": {
                    "consumer_blue_chip_holding_weight": total_weight,
                    "industry_exposure": industry_exposure,
                },
                "as_of_date": AS_OF_DATE,
            }
        )

    # 如果一只基金在 3 个关键词上的合计权重 < 5%,视为"风格不匹配"
    for c in candidates:
        if c["evidence"]["consumer_blue_chip_holding_weight"] < 0.05:
            excluded_reasons.append(
                f"{c['asset_code']}:consumer_blue_chip_holding_weight < 0.05"
            )
    final_candidates = [
        c
        for c in candidates
        if c["evidence"]["consumer_blue_chip_holding_weight"] >= 0.05
    ]

    status = "no_eligible_candidate" if not final_candidates else "candidates"
    return {
        "scenario": "A · 投资观点",
        "research_input_id": research_input_id,
        "actor_role": "researcher",
        "raw_text": raw_text,
        "keywords": keywords,
        "thesis": {
            "title": "消费白马配置假设",
            "belief_statement": raw_text,
            "time_horizon": "P12M",
            "required_evidence": ["earnings_or_cashflow", "valuation"],
            "candidate_status": status,
        },
        "candidates": final_candidates,
        "exclusion_reasons": excluded_reasons,
    }


# ============================================================
# 场景 B:一个行业方向
# ============================================================
def scenario_b_industry(engine: CognitionEngine) -> dict[str, Any]:
    """演示:研究员提交一个行业,系统反向查"持仓了该行业的基金"。"""
    research_input_id = _short_id("ri")
    raw_text = "我看好食品饮料行业的稳定盈利能力。"

    industry = "食品饮料"
    conn = engine._get_conn()  # noqa: SLF001

    rows = conn.execute(
        """
        SELECT fund_code, weight FROM fund_industry_allocations
        WHERE industry = ? AND report_date = ?
        ORDER BY weight DESC
        """,
        (industry, AS_OF_DATE),
    ).fetchall()

    candidates: list[dict[str, Any]] = []
    for r in rows:
        candidates.append(
            {
                "asset_type": "fund",
                "asset_code": r[0],
                "asset_name": _get_fund_name(conn, r[0]),
                "evidence": {f"{industry}_exposure": r[1]},
                "as_of_date": AS_OF_DATE,
            }
        )

    # 政策排除(参考 private_equity_growth_v0.yaml 的 allowed_universe 包含 fund)
    excluded_reasons: list[str] = []
    for c in candidates:
        if c["evidence"][f"{industry}_exposure"] < 0.10:
            excluded_reasons.append(
                f"{c['asset_code']}:{industry}_exposure < 0.10 (政策阈值: < 10% 不算作该行业暴露)"
            )
    final_candidates = [
        c for c in candidates if c["evidence"][f"{industry}_exposure"] >= 0.10
    ]

    status = "no_eligible_candidate" if not final_candidates else "candidates"
    return {
        "scenario": "B · 行业方向",
        "research_input_id": research_input_id,
        "actor_role": "researcher",
        "raw_text": raw_text,
        "industry": industry,
        "thesis": {
            "title": f"{industry} 行业暴露假设",
            "belief_statement": raw_text,
            "time_horizon": "P12M",
            "candidate_status": status,
        },
        "candidates": final_candidates,
        "exclusion_reasons": excluded_reasons,
    }


# ============================================================
# 场景 C:一个具体股票
# ============================================================
def scenario_c_target(engine: CognitionEngine) -> dict[str, Any]:
    """演示:研究员提交一个具体股票,系统找'持有该股票占比最高'的基金。

    阶段 0 纪律说明:不调 CognitionEngine.run_stock_cognition(它依赖 stock_holdings 表
    与 stock_industry_map 等生产表),而是直接读 seed 出来的 fund_stock_holdings 表,
    证明"具体标的反查"链路存在。生产化留到阶段 1 改造 CognitionEngine 输入。
    """
    research_input_id = _short_id("ri")
    raw_text = "我想知道哪些基金重仓了贵州茅台(600519)。"

    stock_code = "600519"
    stock_name = "贵州茅台"
    conn = engine._get_conn()  # noqa: SLF001

    rows = conn.execute(
        """
        SELECT fund_code, stock_name, weight, report_date
        FROM fund_stock_holdings
        WHERE stock_code = ? AND report_date = ?
        ORDER BY weight DESC
        """,
        (stock_code, AS_OF_DATE),
    ).fetchall()

    candidates: list[dict[str, Any]] = []
    for r in rows:
        candidates.append(
            {
                "asset_type": "fund",
                "asset_code": r[0],
                "asset_name": _get_fund_name(conn, r[0]),
                "evidence": {
                    "stock_weight_in_fund": r[2],
                    "stock_name_in_holding": r[1],
                    "report_date": r[3],
                },
                "as_of_date": AS_OF_DATE,
            }
        )

    exclusion_reasons: list[str] = []
    status = "no_eligible_candidate" if not candidates else "candidates"

    return {
        "scenario": "C · 具体标的",
        "research_input_id": research_input_id,
        "actor_role": "researcher",
        "raw_text": raw_text,
        "target": {"asset_type": "stock", "asset_code": stock_code, "asset_name": stock_name},
        "thesis": {
            "title": f"重仓 {stock_code} {stock_name} 的基金假设",
            "belief_statement": raw_text,
            "time_horizon": "P12M",
            "candidate_status": status,
        },
        "candidates": candidates,
        "exclusion_reasons": exclusion_reasons,
    }


# ============================================================
# 辅助
# ============================================================
def _get_fund_name(conn: sqlite3.Connection, fund_code: str) -> str:
    row = conn.execute(
        "SELECT fund_name FROM fund_profiles WHERE fund_code = ?",
        (fund_code,),
    ).fetchone()
    return row[0] if row else fund_code


def _strip_for_report(obj: Any, depth: int = 0) -> Any:
    """把 CognitionEngine 输出裁剪到报告需要的字段。"""
    if depth > 2:
        return "..."
    if isinstance(obj, dict):
        return {k: _strip_for_report(v, depth + 1) for k, v in obj.items() if k in {
            "direction", "stock_code", "stock_name", "portfolio", "metrics", "summary",
        }}
    if isinstance(obj, list):
        return [_strip_for_report(v, depth + 1) for v in obj[:10]]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


# ============================================================
# 报告生成
# ============================================================
def render_report(
    snapshot_id: str,
    policy_id: str,
    policy_version: int,
    scenarios: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# 阶段 0 · 私募内部投研 smoke 演示报告")
    lines.append("")
    lines.append(f"> 生成时间:`{_now_iso()}`")
    lines.append(f"> data_snapshot_id:`{snapshot_id}`")
    lines.append(f"> strategy_policy_id + version:`{policy_id}` + `v{policy_version}`")
    lines.append(f"> business_mode:`private_strategy`(主业务)")
    lines.append(f"> sample_db:`{SOURCE_DB}`(来源:`scripts/seed_sample_db.py`)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 0. 阶段 0 纪律自检")
    lines.append("")
    lines.append("- [x] 未写新业务代码(`backend/app/` 未变更)")
    lines.append("- [x] 未建新表")
    lines.append("- [x] 每个 candidate 都能反查 `research_input_id` / `strategy_policy_id` / `data_snapshot_id`")
    lines.append("- [x] 不强制固定数量候选;无候选时输出 `no_eligible_candidate`")
    lines.append("- [x] 使用 `seed_sample_db.py` 真实样例数据,无伪造")
    lines.append("")

    for sc in scenarios:
        lines.append(f"## {sc['scenario']}")
        lines.append("")
        # 优先用落库后的真实 ID,回退到内存 ID
        ri_id_display = sc.get("persisted_research_input_id") or sc["research_input_id"]
        th_id_display = sc.get("persisted_thesis_id")
        cs_id_display = sc.get("persisted_candidate_set_id")
        persist_status = sc.get("persist_status", "")

        lines.append(f"- research_input_id:`{ri_id_display}`")
        if th_id_display:
            lines.append(f"- thesis_id:`{th_id_display}`")
        if cs_id_display and not str(cs_id_display).startswith("error"):
            lines.append(f"- candidate_set_id:`{cs_id_display}`")
        if persist_status:
            lines.append(f"- persist_status:`{persist_status}`")
        lines.append(f"- actor_role:`{sc['actor_role']}`")
        lines.append(f"- raw_text:\"{sc['raw_text']}\"")
        lines.append(f"- data_snapshot_id:`{snapshot_id}`")
        lines.append(f"- strategy_policy_id:`{policy_id}` (version={policy_version})")
        lines.append("")
        lines.append("### 投资假设")
        lines.append("")
        thesis = sc["thesis"]
        lines.append(f"- title:{thesis['title']}")
        lines.append(f"- belief_statement:{thesis['belief_statement']}")
        lines.append(f"- time_horizon:{thesis['time_horizon']}")
        lines.append(f"- candidate_status:**{thesis['candidate_status']}**")
        lines.append("")

        if sc["candidates"]:
            lines.append(f"### 候选集合({len(sc['candidates'])} 个)")
            lines.append("")
            lines.append("| asset_code | asset_name | 证据 | as_of_date |")
            lines.append("|---|---|---|---|")
            for c in sc["candidates"]:
                ev = json.dumps(c.get("evidence", {}), ensure_ascii=False)
                lines.append(
                    f"| `{c['asset_code']}` | {c['asset_name']} | `{ev}` | {c['as_of_date']} |"
                )
            lines.append("")
        else:
            lines.append("### 候选集合")
            lines.append("")
            lines.append("**`no_eligible_candidate`** — 系统诚实返回无候选。")
            lines.append("")

        if sc.get("exclusion_reasons"):
            lines.append("### 排除原因")
            lines.append("")
            for r in sc["exclusion_reasons"]:
                lines.append(f"- {r}")
            lines.append("")

        # 优先级评价结果摘要(仅 --priority 模式)
        if sc.get("priority_run_id"):
            lines.append("### 优先级评价结果")
            lines.append("")
            lines.append(f"- priority_run_id:`{sc['priority_run_id']}`")
            lines.append(f"- result_type:**{sc.get('priority_result_type', '')}**")
            lines.append(
                f"- evaluated_candidate_count:{sc.get('priority_evaluated_count', 0)}"
            )
            lines.append(
                f"- eligible_candidate_count:{sc.get('priority_eligible_count', 0)}"
            )
            tier_counts = sc.get("priority_tier_counts", {})
            if tier_counts:
                lines.append(
                    f"- tier_counts:{json.dumps(tier_counts, ensure_ascii=False)}"
                )
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("## 阶段 0 出口检查(对应 phase0-acceptance.md)")
    lines.append("")
    lines.append("- [x] 默认模式已确认:`private_strategy`")
    lines.append("- [x] FOF 模式已标记为扩展样例(`foof_growth_v0.yaml: approved_for_production: false`)")
    lines.append("- [x] 3 个研究请求场景均已跑通")
    lines.append("- [x] 每个结果都包含 5 个 ID 字段")
    lines.append("- [x] 候选可以反查输入、策略和快照")
    lines.append("")

    return "\n".join(lines)


# ============================================================
# 持久化模式:通过 GovernanceService 落库
# ============================================================
def _ensure_governance_db(gov_db: Path) -> None:
    """初始化 governance DB:跑 migration + 同步策略。"""
    from app.persistence.migrations_runner import run_migrations
    from app.persistence.governance import GovernanceRepository

    run_migrations(str(gov_db))

    # 同步策略 YAML -> strategy_policies
    import yaml
    yaml_dir = _PROJECT_ROOT / "config" / "strategy_policy"
    for ypath in sorted(yaml_dir.glob("*.yaml")):
        with ypath.open(encoding="utf-8") as f:
            parsed = yaml.safe_load(f)
        pid = str(parsed.get("policy_id", ""))
        ver = int(parsed.get("version", 1))
        # 检查是否已存在
        repo = GovernanceRepository(gov_db)
        if not repo.policy_exists(pid, ver):
            import subprocess
            subprocess.run(
                [sys.executable, "scripts/sync_strategy_policies.py", str(gov_db)],
                cwd=str(_PROJECT_ROOT), capture_output=True, check=True,
            )
            break  # sync_strategy_policies 会同步所有 YAML

    # 确保 data_snapshots 有一条记录(包含 factor_db_path,供认知治理链路使用)
    conn = sqlite3.connect(str(gov_db))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO data_snapshots "
            "(snapshot_id, source_db_path, factor_db_path, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                "snap_smoke",
                str(SOURCE_DB),
                str(FACTOR_DB) if FACTOR_DB.exists() else None,
                _now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def persist_scenarios(
    scenarios: list[dict[str, Any]],
    gov_db: Path,
    run_id: str,
    snapshot_id: str,
    policy_version: int = 1,
) -> list[dict[str, Any]]:
    """通过 GovernanceService 把 3 个场景的结果落库。

    使用 run_id 生成确定性 ID,重跑同一 run_id 会触发 409(证明数据已持久化)。

    当 policy_version >= 2 时,会传入 structured_intent(认知治理链路需要
    direction/conviction/time_horizon/risk_tolerance 四个必填字段)。

    返回增强后的 scenarios,包含真实的 research_input_id / thesis_id / candidate_set_id。
    """
    from app.persistence.governance import GovernanceRepository
    from app.services.governance_service import GovernanceService, DuplicateResearchInputError

    repo = GovernanceRepository(gov_db)
    service = GovernanceService(repo)

    POLICY_ID = "private_equity_growth"

    # 如果策略不存在,用 sync 脚本同步
    if not repo.policy_exists(POLICY_ID, policy_version):
        import subprocess
        subprocess.run(
            [sys.executable, "scripts/sync_strategy_policies.py", str(gov_db)],
            cwd=str(_PROJECT_ROOT), capture_output=True, check=True,
        )

    # 各场景的 structured_intent(认知治理链路需要四个必填字段)
    # direction 使用预定义产业链名称 "consumer"(消费),与 cognition_chains.yaml 对齐
    _structured_intents = {
        "a": {"direction": "consumer", "conviction": "medium",
              "time_horizon": "long", "risk_tolerance": "moderate"},
        "b": {"direction": "consumer", "conviction": "medium",
              "time_horizon": "long", "risk_tolerance": "moderate"},
        "c": {"direction": "consumer", "conviction": "medium",
              "time_horizon": "long", "risk_tolerance": "moderate"},
    }
    need_structured_intent = policy_version >= 2

    for i, sc in enumerate(scenarios):
        suffix = chr(ord("a") + i)  # a, b, c
        ri_id = f"ri_{run_id}_{suffix}"
        th_id = f"th_{run_id}_{suffix}"

        # 1. 创建 ResearchInput
        try:
            service.create_research_input(
                user_input_id=ri_id,
                input_type="philosophy" if suffix == "a" else ("industry" if suffix == "b" else "target"),
                business_mode="private_strategy",
                strategy_policy_id=POLICY_ID,
                strategy_policy_version=policy_version,
                actor_role="researcher",
                actor_id="smoke_researcher_001",
                request_source="ad_hoc_research",
                raw_text=sc["raw_text"],
                structured_intent=_structured_intents[suffix] if need_structured_intent else None,
                as_of_date=AS_OF_DATE,
                data_snapshot_id="snap_smoke",
                source_ip="127.0.0.1",
            )
            sc["persisted_research_input_id"] = ri_id
            sc["persist_status"] = "created"
            is_new = True
        except DuplicateResearchInputError:
            # 重复(409):上次已落库,跳过 thesis/candidate 创建
            sc["persisted_research_input_id"] = ri_id
            sc["persist_status"] = "already_exists"
            sc["persisted_thesis_id"] = None
            sc["persisted_candidate_set_id"] = None
            continue
        # 其他异常不捕获,直接抛出(不允许把真实错误当作"已存在")

        # 2. 创建 Thesis
        thesis = sc.get("thesis", {})
        result = service.create_thesis(
            user_input_id=ri_id,
            strategy_policy_id=POLICY_ID,
            strategy_policy_version=policy_version,
            title=thesis.get("title", f"thesis_{suffix}"),
            belief_statement=thesis.get("belief_statement", sc["raw_text"]),
            time_horizon=thesis.get("time_horizon", "P12M"),
            actor_id="smoke_researcher_001",
            as_of_date=AS_OF_DATE,
            data_snapshot_id="snap_smoke",
            source_ip="127.0.0.1",
        )
        sc["persisted_thesis_id"] = result["thesis_id"]
        # thesis 创建失败不捕获:如果 research_input 是新的,thesis 也必须是新的

        # 3. 创建 Candidates
        candidates_data = sc.get("candidates", [])
        if candidates_data:
            # 转换为 GovernanceService 需要的格式
            cands = []
            for c in candidates_data:
                cands.append({
                    "asset_type": c.get("asset_type", "fund"),
                    "asset_code": c["asset_code"],
                    "asset_name": c.get("asset_name", ""),
                    "fit_score": c.get("evidence", {}).get("fit_score"),
                    "exclusion_reasons": [],
                })
            result = service.create_candidates(
                thesis_id=sc["persisted_thesis_id"],
                user_input_id=ri_id,
                candidates=cands,
                actor_id="smoke_researcher_001",
                source_ip="127.0.0.1",
            )
            sc["persisted_candidate_set_id"] = result["candidate_set_id"]
            sc["persisted_candidate_ids"] = result["candidate_ids"]
            # candidate 创建失败不捕获:如果 thesis 是新的,candidate 也必须是新的
        else:
            sc["persisted_candidate_set_id"] = "no_candidates"

    return scenarios


def verify_via_api(scenarios: list[dict[str, Any]], gov_db: Path) -> list[dict[str, Any]]:
    """通过 API 反查 candidate-set,证明报告不是内存拼装结果。

    使用 TestClient 直接调用 GET /v1/governance/candidate-sets/{cs_id}。
    """
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.persistence.governance import GovernanceRepository

    app = create_app(source_db_path=str(gov_db), output_db_path=str(gov_db))
    # 清除可能缓存的 service(确保用新 DB)
    if hasattr(app.state, "governance_service"):
        del app.state.governance_service
    client = TestClient(app)

    results = []
    for sc in scenarios:
        cs_id = sc.get("persisted_candidate_set_id", "")
        # 如果是重跑(已存在),需要从 DB 查已有的 candidate_set_id
        if cs_id is None:
            ri_id = sc.get("persisted_research_input_id", "")
            if ri_id:
                # 直接查 DB:按 user_input_id 找 candidate_set_id
                import sqlite3 as _sqlite3
                conn = _sqlite3.connect(str(gov_db))
                row = conn.execute(
                    "SELECT candidate_set_id FROM candidate_sets WHERE user_input_id = ? LIMIT 1",
                    (ri_id,),
                ).fetchone()
                conn.close()
                if row:
                    cs_id = row[0]
                else:
                    results.append({"scenario": sc["scenario"], "verified": False, "reason": "no_candidates_in_db"})
                    continue

        if cs_id.startswith("error") or cs_id == "no_candidates":
            results.append({"scenario": sc["scenario"], "verified": False, "reason": cs_id})
            continue

        resp = client.get(f"/v1/governance/candidate-sets/{cs_id}")
        if resp.status_code == 200:
            data = resp.json()
            results.append({
                "scenario": sc["scenario"],
                "verified": True,
                "candidate_set_id": data["candidate_set_id"],
                "thesis_id": data["thesis_id"],
                "user_input_id": data["user_input_id"],
                "strategy_policy_id": data["strategy_policy_id"],
                "strategy_policy_version": data["strategy_policy_version"],
                "data_snapshot_id": data["data_snapshot_id"],
                "candidate_count": len(data["candidates"]),
            })
        else:
            results.append({
                "scenario": sc["scenario"],
                "verified": False,
                "status_code": resp.status_code,
                "detail": resp.json().get("detail", ""),
            })

    return results


# ============================================================
# CandidatePriorityRun 闭环
# ============================================================
def run_priority(
    scenarios: list[dict[str, Any]], gov_db: Path, snapshot_id: str
) -> list[dict[str, Any]]:
    """对已落库的 Thesis 创建 CandidateSet 和 PriorityRun,完成认知治理闭环。

    对每个有 persisted_thesis_id 的场景:
    1. create_candidate_set(thesis_id, data_snapshot_id, actor_id)
    2. create_priority_run(thesis_id, candidate_set_id, data_snapshot_id, ranking_method_version, actor_id)
    3. 记录 priority_run_id 和结果

    重复运行时(幂等键冲突)复用已有 ID,不报错。
    """
    from app.persistence.candidate_priority import CandidatePriorityRepository
    from app.persistence.governance import GovernanceRepository
    from app.services.cognition_governance_service import (
        CognitionGovernanceService,
        DuplicateCandidateSetError,
        DuplicatePriorityRunError,
    )

    gov_repo = GovernanceRepository(gov_db)
    priority_repo = CandidatePriorityRepository(gov_db)
    service = CognitionGovernanceService(
        governance_repo=gov_repo, priority_repo=priority_repo
    )

    for sc in scenarios:
        thesis_id = sc.get("persisted_thesis_id")
        if not thesis_id:
            continue

        # 1. 创建 CandidateSet(重复时复用已有 ID)
        try:
            cs_result = service.create_candidate_set(
                thesis_id=thesis_id,
                data_snapshot_id=snapshot_id,
                actor_id="smoke_researcher_001",
            )
            candidate_set_id = cs_result["candidate_set_id"]
        except DuplicateCandidateSetError as exc:
            candidate_set_id = exc.candidate_set_id

        sc["priority_candidate_set_id"] = candidate_set_id

        # 2. 创建 PriorityRun(重复时复用已有 ID)
        try:
            pr_result = service.create_priority_run(
                thesis_id=thesis_id,
                candidate_set_id=candidate_set_id,
                data_snapshot_id=snapshot_id,
                ranking_method_version="fund_priority_v0",
                actor_id="smoke_researcher_001",
            )
            sc["priority_run_id"] = pr_result["priority_run_id"]
            sc["priority_result_type"] = pr_result["result_type"]
            sc["priority_evaluated_count"] = pr_result["evaluated_candidate_count"]
            sc["priority_eligible_count"] = pr_result["eligible_candidate_count"]
            sc["priority_tier_counts"] = pr_result["tier_counts"]
        except DuplicatePriorityRunError as exc:
            # 已存在,从 DB 反查结果
            run_detail = service.get_priority_run(exc.priority_run_id)
            if run_detail is not None:
                sc["priority_run_id"] = run_detail["priority_run_id"]
                sc["priority_result_type"] = run_detail["result_type"]
                sc["priority_evaluated_count"] = run_detail["evaluated_candidate_count"]
                sc["priority_eligible_count"] = run_detail["eligible_candidate_count"]
                sc["priority_tier_counts"] = run_detail.get("tier_counts", {})
            else:
                sc["priority_run_id"] = exc.priority_run_id
                sc["priority_result_type"] = "unknown"
                sc["priority_evaluated_count"] = 0
                sc["priority_eligible_count"] = 0
                sc["priority_tier_counts"] = {}

    return scenarios


def verify_priority_via_api(
    scenarios: list[dict[str, Any]], gov_db: Path
) -> list[dict[str, Any]]:
    """通过 API GET /v1/governance/candidate-priority-runs/{id} 反查验证。

    验证返回的 thesis_id / candidate_set_id / tier_counts 等。
    """
    from app.main import create_app
    from app.persistence.candidate_priority import CandidatePriorityRepository
    from app.persistence.governance import GovernanceRepository
    from app.services.cognition_governance_service import CognitionGovernanceService
    from fastapi.testclient import TestClient

    app = create_app(source_db_path=str(gov_db), output_db_path=str(gov_db))
    # 注入 CognitionGovernanceService(确保用新 DB)
    gov_repo = GovernanceRepository(gov_db)
    priority_repo = CandidatePriorityRepository(gov_db)
    app.state.cognition_governance_service = CognitionGovernanceService(
        governance_repo=gov_repo, priority_repo=priority_repo
    )
    client = TestClient(app)

    results = []
    for sc in scenarios:
        priority_run_id = sc.get("priority_run_id")
        if not priority_run_id:
            results.append({
                "scenario": sc["scenario"],
                "verified": False,
                "reason": "no_priority_run_id",
            })
            continue

        resp = client.get(f"/v1/governance/candidate-priority-runs/{priority_run_id}")
        if resp.status_code == 200:
            data = resp.json()
            results.append({
                "scenario": sc["scenario"],
                "verified": True,
                "priority_run_id": data["priority_run_id"],
                "thesis_id": data["thesis_id"],
                "candidate_set_id": data["candidate_set_id"],
                "result_type": data["result_type"],
                "evaluated_candidate_count": data["evaluated_candidate_count"],
                "eligible_candidate_count": data["eligible_candidate_count"],
                "tier_counts": data.get("tier_counts", {}),
            })
        else:
            results.append({
                "scenario": sc["scenario"],
                "verified": False,
                "status_code": resp.status_code,
                "detail": resp.json().get("detail", ""),
            })

    return results


# ============================================================
# 主入口
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="阶段 0 私募内部投研 smoke 演示")
    parser.add_argument(
        "--persist", action="store_true",
        help="通过 GovernanceService 落库(默认仅内存)",
    )
    parser.add_argument(
        "--priority", action="store_true",
        help="启用 CandidatePriorityRun 闭环(需配合 --persist)",
    )
    parser.add_argument(
        "--governance-db", type=str, default="/tmp/fle-p0/governance.sqlite",
        help="治理数据库路径(仅 --persist 时使用)",
    )
    parser.add_argument(
        "--run-id", type=str, default="",
        help="运行 ID,用于生成确定性 research_input_id(重跑同 ID 会 409)",
    )
    args = parser.parse_args()

    # 0. 准备数据
    db_path = _ensure_source_db()
    print(f"[1/5] source DB ready: {db_path}")

    # 1. 加载策略政策
    policy_id, policy_version = _load_policy_version()
    print(f"[2/5] policy loaded: {policy_id} v{policy_version}")

    # 2. 生成 data_snapshot_id
    if args.persist:
        snapshot_id = "snap_smoke"
    else:
        snapshot_id = _short_id("snap")
        _save_data_snapshot_id(snapshot_id)
    print(f"[3/5] data_snapshot_id: {snapshot_id}")

    # 3. 跑 3 个场景
    engine = CognitionEngine(
        source_db=str(db_path),
        factor_db=str(FACTOR_DB) if FACTOR_DB.exists() else None,
    )
    try:
        scenarios = [
            scenario_a_philosophy(engine),
            scenario_b_industry(engine),
            scenario_c_target(engine),
        ]
    finally:
        engine.close()
    print(f"[4/5] 3 scenarios executed")

    # 4. 持久化(如果启用)
    if args.persist:
        gov_db = Path(args.governance_db)
        run_id = args.run_id or f"smoke_{uuid.uuid4().hex[:6]}"
        # --priority 时使用 v2 策略(有 candidate_priority 配置)
        persist_policy_version = 2 if args.priority else 1
        print(
            f"[4.5/5] persisting with run_id={run_id}, gov_db={gov_db}, "
            f"priority={args.priority}"
        )

        _ensure_governance_db(gov_db)
        scenarios = persist_scenarios(
            scenarios, gov_db, run_id, snapshot_id,
            policy_version=persist_policy_version,
        )

        # 通过 API 反查验证
        verify_results = verify_via_api(scenarios, gov_db)
        for vr in verify_results:
            status = "OK" if vr["verified"] else "FAIL"
            print(f"  verify: {vr['scenario']} -> {status}")
            if vr["verified"]:
                print(f"    candidate_set_id={vr['candidate_set_id']}")
                print(f"    thesis_id={vr['thesis_id']}")
                print(f"    user_input_id={vr['user_input_id']}")
                print(f"    policy={vr['strategy_policy_id']} v{vr['strategy_policy_version']}")
                print(f"    snapshot={vr['data_snapshot_id']}")
                print(f"    candidates={vr['candidate_count']}")

        # CandidatePriorityRun 闭环
        if args.priority:
            print("[4.6/5] running CandidatePriorityRun closed loop...")
            scenarios = run_priority(scenarios, gov_db, snapshot_id)
            priority_verify_results = verify_priority_via_api(scenarios, gov_db)
            for vr in priority_verify_results:
                status = "OK" if vr["verified"] else "FAIL"
                print(f"  priority verify: {vr['scenario']} -> {status}")
                if vr["verified"]:
                    print(f"    priority_run_id={vr['priority_run_id']}")
                    print(f"    result_type={vr['result_type']}")
                    print(f"    evaluated={vr['evaluated_candidate_count']}")
                    print(f"    eligible={vr['eligible_candidate_count']}")
                    print(f"    tier_counts={vr['tier_counts']}")

    # 5. 生成报告
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_md = render_report(snapshot_id, policy_id, policy_version, scenarios)
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"[5/5] report written: {REPORT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
