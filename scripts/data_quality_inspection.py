"""数据质量巡检：定期扫描数据问题，给出报告。

检查项：
1. NAV 数据完整性：缺口、孤立日、最近日期
2. 持仓数据陈旧度：最近一份报告期距今
3. 因子数据新鲜度：stock_factor_values as_of_date 距今
4. 基准数据缺口：哪些基金的业绩比较基准解析不出来
5. 数据快照新鲜度：data_snapshots 表中最新一条数据距今多久
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class InspectionFinding:
    severity: str  # info / warning / critical
    category: str
    title: str
    detail: str
    count: int = 0
    samples: list[str] = field(default_factory=list)


def _days(date_str: str | None) -> float | None:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
        now = datetime.now(UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return (now - dt).total_seconds() / 86400
    except ValueError:
        return None


def inspect_nav_history(conn: sqlite3.Connection, lookback_days: int = 7) -> list[InspectionFinding]:
    """检查 NAV 数据的完整性和新鲜度。"""
    findings: list[InspectionFinding] = []
    today = datetime.now(UTC).date()

    # 最近每只基金的最近 NAV 日期
    rows = conn.execute(
        """
        SELECT fund_code, MAX(nav_date) AS latest
        FROM nav_history
        GROUP BY fund_code
        """
    ).fetchall()

    stale_funds = []
    for r in rows:
        if not r["latest"]:
            continue
        latest_date = datetime.fromisoformat(r["latest"]).date()
        days_old = (today - latest_date).days
        if days_old > lookback_days:
            stale_funds.append((r["fund_code"], r["latest"], days_old))

    if stale_funds:
        findings.append(
            InspectionFinding(
                severity="warning" if len(stale_funds) < 5 else "critical",
                category="nav_history",
                title=f"{len(stale_funds)} 只基金 NAV 数据超过 {lookback_days} 天未更新",
                detail=f"最新 NAV 日期超过 {lookback_days} 天前的基金列表。",
                count=len(stale_funds),
                samples=[f"{c} ({d} 天前)" for c, _, d in stale_funds[:10]],
            )
        )

    return findings


def inspect_holdings_staleness(
    conn: sqlite3.Connection, max_age_days: int = 120
) -> list[InspectionFinding]:
    """检查持仓报告期是否过老。"""
    findings: list[InspectionFinding] = []
    today = datetime.now(UTC).date()

    rows = conn.execute(
        """
        SELECT fund_code, MAX(report_period) AS latest_period
        FROM stock_holdings
        GROUP BY fund_code
        """
    ).fetchall()

    stale = []
    for r in rows:
        if not r["latest_period"]:
            continue
        period = datetime.fromisoformat(r["latest_period"]).date()
        days_old = (today - period).days
        if days_old > max_age_days:
            stale.append((r["fund_code"], r["latest_period"], days_old))

    if stale:
        findings.append(
            InspectionFinding(
                severity="warning",
                category="stock_holdings",
                title=f"{len(stale)} 只基金最新持仓期超过 {max_age_days} 天",
                detail="最新一份持仓报告期距今超过阈值的基金。",
                count=len(stale),
                samples=[f"{c} ({d} 天前)" for c, _, d in stale[:10]],
            )
        )

    return findings


def inspect_factor_freshness(
    conn: sqlite3.Connection, max_age_days: int = 7
) -> list[InspectionFinding]:
    """检查股票因子数据的新鲜度。"""
    findings: list[InspectionFinding] = []
    today = datetime.now(UTC).date()

    row = conn.execute(
        "SELECT MAX(as_of_date) AS latest, COUNT(DISTINCT as_of_date) AS days, "
        "COUNT(DISTINCT stock_code) AS stocks FROM stock_factor_values"
    ).fetchone()

    if not row or not row["latest"]:
        findings.append(
            InspectionFinding(
                severity="critical",
                category="stock_factors",
                title="stock_factor_values 表为空",
                detail="没有任何股票因子记录。",
            )
        )
        return findings

    latest = datetime.fromisoformat(row["latest"]).date()
    days_old = (today - latest).days

    if days_old > max_age_days:
        findings.append(
            InspectionFinding(
                severity="warning",
                category="stock_factors",
                title=f"股票因子快照陈旧 ({days_old} 天前)",
                detail=f"最新 as_of_date = {row['latest']}（覆盖 {row['stocks']} 只股票，{row['days']} 个交易日）",
            )
        )

    return findings


def inspect_benchmark_gaps(conn: sqlite3.Connection) -> list[InspectionFinding]:
    """检查基准组件解析缺失。"""
    findings: list[InspectionFinding] = []

    rows = conn.execute(
        """
        SELECT fund_code, COUNT(*) AS missing
        FROM benchmark_components
        WHERE status = 'unresolved' OR resolved = 0
        GROUP BY fund_code
        """
    ).fetchall()
    if rows:
        findings.append(
            InspectionFinding(
                severity="warning",
                category="benchmark_components",
                title=f"{len(rows)} 只基金的业绩比较基准存在 unresolved 组件",
                detail="这些基金的相对基准标签可能无法计算。",
                count=sum(r["missing"] for r in rows),
                samples=[r["fund_code"] for r in rows[:10]],
            )
        )

    return findings


def inspect_data_snapshots(conn: sqlite3.Connection) -> list[InspectionFinding]:
    """检查 data_snapshots 表的新鲜度。"""
    findings: list[InspectionFinding] = []
    try:
        row = conn.execute(
            "SELECT MAX(created_at) AS latest, COUNT(*) AS total FROM data_snapshots"
        ).fetchone()
    except sqlite3.OperationalError:
        return findings

    if not row or not row["latest"]:
        findings.append(
            InspectionFinding(
                severity="info",
                category="data_snapshots",
                title="data_snapshots 表为空",
                detail="从未记录过数据快照。建议用最新 batch 触发一次。",
            )
        )
        return findings

    days_old = _days(row["latest"])
    if days_old and days_old > 30:
        findings.append(
            InspectionFinding(
                severity="warning",
                category="data_snapshots",
                title=f"data_snapshots 最近一条 {days_old:.0f} 天前",
                detail=f"共 {row['total']} 条快照，最后一条创建于 {row['latest']}",
            )
        )

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="数据质量巡检")
    parser.add_argument(
        "--db",
        required=True,
        help="源数据库路径（fundData）",
    )
    parser.add_argument(
        "--output-db",
        default=None,
        help="输出数据库（label runs）。指定后将检查 data_snapshots 表。",
    )
    parser.add_argument(
        "--json",
        default=None,
        help="JSON 输出路径（用于聚合/MQ）",
    )
    parser.add_argument(
        "--max-nav-staleness-days",
        type=int,
        default=7,
        help="NAV 数据陈旧度阈值（默认 7）",
    )
    parser.add_argument(
        "--max-holding-age-days",
        type=int,
        default=120,
        help="持仓报告期陈旧阈值（默认 120）",
    )
    parser.add_argument(
        "--max-factor-age-days",
        type=int,
        default=7,
        help="股票因子陈旧度阈值（默认 7）",
    )
    args = parser.parse_args(argv)

    findings: list[InspectionFinding] = []
    db_path = args.db
    if not Path(db_path).exists():
        print(f"[data_quality_inspection] DB 不存在: {db_path}", file=sys.stderr)
        return 1

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        findings.extend(inspect_nav_history(conn, args.max_nav_staleness_days))
        findings.extend(inspect_holdings_staleness(conn, args.max_holding_age_days))
        findings.extend(inspect_factor_freshness(conn, args.max_factor_age_days))
        findings.extend(inspect_benchmark_gaps(conn))

    if args.output_db:
        out = Path(args.output_db)
        if out.exists():
            with sqlite3.connect(str(out)) as out_conn:
                out_conn.row_factory = sqlite3.Row
                findings.extend(inspect_data_snapshots(out_conn))

    # 汇总
    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "inspected_at": datetime.now(UTC).isoformat(),
                    "summary": by_severity,
                    "findings": [asdict(f) for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # 控制台输出
    print(f"[data_quality_inspection] {datetime.now(UTC).isoformat(timespec='seconds')}")
    print(f"  发现: critical={by_severity.get('critical', 0)}, "
          f"warning={by_severity.get('warning', 0)}, "
          f"info={by_severity.get('info', 0)}")
    for f in findings:
        icon = {"critical": "✗", "warning": "⚠", "info": "·"}.get(f.severity, "?")
        print(f"  {icon} [{f.category}] {f.title}")
        if f.samples:
            print(f"    示例: {', '.join(f.samples[:5])}{'...' if len(f.samples) > 5 else ''}")

    return 0 if by_severity.get("critical", 0) == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
