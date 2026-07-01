"""债券基准 component 日频收益导入层。

把可靠日频源整理成标准 CSV，导入到 source DB 的 ``benchmark_component_returns`` 表，
供 ``fetch_benchmark_returns.py`` 合成复合基准时复用。

边界（刻意做窄）：
- 只允许白名单 component（债券指数），不碰可在线拉取的宽指数。
- 严格数据质量校验：白名单、日期格式、小数（非百分数）、source 必填非 unknown。
- 同 (component_code, trade_date) 幂等覆盖。
- 全量校验通过且达到 ``--min-rows`` 才写库，否则不写任何行（原子）。

CSV 格式：
    component_code,trade_date,daily_return,source
    H11001,2025-06-25,0.0012,csindex_official
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

ALLOWED_COMPONENT_CODES = {
    "H11001",            # 中证全债
    "H11006",            # 中证国债
    "H11008",            # 中证企业债（保留白名单，但不用于中证综合债）
    "H11009",            # 中证综合债
    "000998",            # 中证TMT
    "000964",            # 中证新兴产业
    "000942",            # 内地消费
    "931027",            # 港股通大消费
    "399102",            # 创业板综合
    "399101",            # 中小企业综合
    "HSI",               # 恒生指数
    "LOCAL_CBOND_COMPOSITE",  # 中债综合
    "LOCAL_CBOND_TOTAL",      # 中债总
    "LOCAL_CHINA_BOND_TOTAL",  # 中国债券总
    "LOCAL_SP_CHINA_BOND",  # 标普中国债券
    "LOCAL_XHFT_CHINA_GOV_BOND",  # 新华富时中国国债
}

# 单日收益的合理区间。债券指数单日波动极小；用 ±10% 作为防百分数误填的上限，
# 既能挡住 1.2(=120%) 这类误填，也不会误伤极端股债日。
_MAX_ABS_DAILY_RETURN = 0.10


class RowError(ValueError):
    """CSV 行校验失败。"""


def validate_row(row: dict[str, Any]) -> tuple[str, str, float, str]:
    component_code = (row.get("component_code") or "").strip()
    trade_date = (row.get("trade_date") or "").strip()
    raw_return = (row.get("daily_return") or "").strip()
    source = (row.get("source") or "").strip()

    if component_code not in ALLOWED_COMPONENT_CODES:
        raise RowError(f"component_code {component_code!r} not in whitelist")
    try:
        date.fromisoformat(trade_date)
    except ValueError as exc:
        raise RowError(f"invalid trade_date {trade_date!r}") from exc
    if not source or source.lower() == "unknown":
        raise RowError("source is required and must not be 'unknown'")
    try:
        daily_return = float(raw_return)
    except (TypeError, ValueError) as exc:
        raise RowError(f"daily_return {raw_return!r} is not a number") from exc
    if abs(daily_return) > _MAX_ABS_DAILY_RETURN:
        raise RowError(
            f"daily_return {daily_return} out of plausible daily range "
            f"(|r|<= {_MAX_ABS_DAILY_RETURN}); likely a percentage mis-fill"
        )
    return component_code, trade_date, daily_return, source


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_component_returns (
            component_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            daily_return REAL NOT NULL,
            source TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (component_code, trade_date)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_benchmark_component_returns_code "
        "ON benchmark_component_returns(component_code, trade_date)"
    )


def import_csv(
    conn: sqlite3.Connection,
    csv_path: str | Path,
    min_rows: int = 1,
) -> dict[str, Any]:
    parsed: list[tuple[str, str, float, str]] = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for lineno, row in enumerate(reader, 2):
            try:
                parsed.append(validate_row(row))
            except RowError as exc:
                raise RowError(f"line {lineno}: {exc}") from exc

    # 按 component 统计去重后的覆盖行数（幂等：同 component/date 只算一条）。
    by_component_dates: dict[str, set[str]] = {}
    for component_code, trade_date, _ret, _src in parsed:
        by_component_dates.setdefault(component_code, set()).add(trade_date)

    for component_code, dates in by_component_dates.items():
        if len(dates) < min_rows:
            raise RowError(
                f"component {component_code} has {len(dates)} distinct dates, "
                f"below min_rows={min_rows}; refusing to import to avoid false ready"
            )

    _ensure_table(conn)
    for component_code, trade_date, daily_return, source in parsed:
        conn.execute(
            """
            INSERT OR REPLACE INTO benchmark_component_returns
            (component_code, trade_date, daily_return, source, fetched_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (component_code, trade_date, daily_return, source),
        )
    conn.commit()
    return {
        "imported": len(parsed),
        "components": {code: len(dates) for code, dates in by_component_dates.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="source SQLite path")
    parser.add_argument("--from-csv", required=True)
    parser.add_argument(
        "--min-rows",
        type=int,
        default=180,
        help="每个 component 至少需要的去重交易日数，低于此值拒绝导入",
    )
    args = parser.parse_args(argv)

    csv_path = Path(args.from_csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    conn = sqlite3.connect(args.db)
    try:
        stats = import_csv(conn, csv_path, min_rows=args.min_rows)
    finally:
        conn.close()
    print(
        f"imported {stats['imported']} rows; "
        f"components={stats['components']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
