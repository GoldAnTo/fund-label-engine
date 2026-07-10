"""数据质量巡检：定期扫描数据问题，给出报告。

检查项：
1. NAV 数据完整性：缺口、孤立日、最近日期
2. 持仓数据陈旧度：最近一份报告期距今
3. 因子数据新鲜度：stock_factor_values as_of_date 距今
4. 基准数据缺口：哪些基金的业绩比较基准解析不出来
5. 数据快照新鲜度：data_snapshots 表中最新一条数据距今多久
6. 异常值检查：NAV 收益率离群、持仓权重和偏离 [0,1]、持仓权重超过阈值
7. 报告期错配：同一报告期基金数显著偏少（数据采集遗漏）
8. 报告期覆盖率：当前报告期有多少基金 vs 历史最大期
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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

    # 兼容：表不存在时直接返回，不抛异常
    try:
        conn.execute("SELECT 1 FROM stock_factor_values LIMIT 1")
    except sqlite3.OperationalError:
        return findings

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

    # 兼容：表不存在时静默返回
    try:
        conn.execute("SELECT 1 FROM benchmark_components LIMIT 1")
    except sqlite3.OperationalError:
        return findings

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


# ------------------------------------------------------------------
# 检查项 6：异常值
# ------------------------------------------------------------------

# 业务阈值：单日 NAV 涨跌幅超过 |X| 视为离群。
# 中国基金市场的涨停板是 10%，跨境 QDII 可能更高，保守用 0.20（20%）。
NAV_DAILY_RETURN_OUTLIER = 0.20

# 持仓单只股票权重上限（基金法规为 10%，专户/分级略高）。
HOLDING_WEIGHT_OUTLIER = 0.30

# 同一报告期单基金持仓数量上限（>30 通常是数据问题，如重复抓取）。
HOLDING_COUNT_OUTLIER = 100


def inspect_nav_return_outliers(
    conn: sqlite3.Connection,
    threshold: float = NAV_DAILY_RETURN_OUTLIER,
    top_n: int = 10,
) -> list[InspectionFinding]:
    """检查 NAV 日收益率离群值（绝对值超过阈值）。"""
    findings: list[InspectionFinding] = []
    try:
        rows = conn.execute(
            """
            SELECT fund_code, nav_date, daily_return
            FROM nav_history
            WHERE daily_return IS NOT NULL
              AND ABS(daily_return) > ?
            ORDER BY ABS(daily_return) DESC
            LIMIT ?
            """,
            (threshold, top_n),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM nav_history "
            "WHERE daily_return IS NOT NULL "
            "  AND ABS(daily_return) > ?",
            (threshold,),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return findings

    if total > 0:
        samples = [
            f"{r['fund_code']} {r['nav_date']} {r['daily_return']*100:.2f}%"
            for r in rows
        ]
        findings.append(
            InspectionFinding(
                severity="critical" if total > 50 else "warning",
                category="nav_outliers",
                title=f"{total} 条 NAV 日收益率超过 ±{threshold*100:.0f}%",
                detail=(
                    f"绝对值超过 {threshold*100:.0f}% 的日收益。大量出现通常是 "
                    "NAV 字段误抓（如累计净值）、分红除权未处理或脏数据。"
                ),
                count=total,
                samples=samples,
            )
        )
    return findings


def inspect_holding_weight_outliers(
    conn: sqlite3.Connection,
    threshold: float = HOLDING_WEIGHT_OUTLIER,
    top_n: int = 10,
) -> list[InspectionFinding]:
    """检查持仓权重离群值（单只股票权重超过 30% 通常是数据问题）。"""
    findings: list[InspectionFinding] = []
    candidates = ["stock_holdings", "fund_stock_holdings"]
    table = None
    for t in candidates:
        try:
            conn.execute(f"SELECT 1 FROM {t} LIMIT 1")
            table = t
            break
        except sqlite3.OperationalError:
            continue
    if not table:
        return findings

    try:
        rows = conn.execute(
            f"""
            SELECT fund_code, report_period, stock_code, stock_name, weight
            FROM {table}
            WHERE weight IS NOT NULL
              AND (weight > ? OR weight < 0)
            ORDER BY weight DESC
            LIMIT ?
            """,
            (threshold, top_n),
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE weight IS NOT NULL AND (weight > ? OR weight < 0)",
            (threshold,),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return findings

    if total > 0:
        period_key = "report_period" if "report_period" in rows[0].keys() else "report_date"
        samples = [
            f"{r['fund_code']} {r[period_key]} {r['stock_code']} {r['weight']*100:.1f}%"
            for r in rows
        ]
        findings.append(
            InspectionFinding(
                severity="critical" if total > 20 else "warning",
                category="holding_outliers",
                title=f"{total} 条持仓权重超过 {threshold*100:.0f}% 或为负",
                detail=(
                    "持仓权重应位于 [0, 1] 之间。出现 > 1 或 < 0 通常是单位错（百分比 vs 小数）"
                    "或加载脚本错误。"
                ),
                count=total,
                samples=samples,
            )
        )
    return findings


def inspect_holding_count_outliers(
    conn: sqlite3.Connection,
    threshold: int = HOLDING_COUNT_OUTLIER,
) -> list[InspectionFinding]:
    """检查单基金单期持仓数量离群（重复抓取或数据错误）。"""
    findings: list[InspectionFinding] = []
    candidates = ["stock_holdings", "fund_stock_holdings"]
    table = None
    period_col = None
    for t in candidates:
        try:
            cols = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({t})").fetchall()
            }
            table = t
            period_col = "report_period" if "report_period" in cols else "report_date"
            break
        except sqlite3.OperationalError:
            continue
    if not table:
        return findings

    rows = conn.execute(
        f"""
        SELECT fund_code, {period_col} AS period, COUNT(*) AS n
        FROM {table}
        GROUP BY fund_code, {period_col}
        HAVING n > ?
        ORDER BY n DESC
        LIMIT 10
        """,
        (threshold,),
    ).fetchall()

    if rows:
        findings.append(
            InspectionFinding(
                severity="warning",
                category="holding_count_outliers",
                title=f"{len(rows)} 个 (基金, 报告期) 持仓数 > {threshold}",
                detail="正常基金单期持仓应在 10-80 只之间。> 100 通常是数据重复抓取。",
                count=len(rows),
                samples=[f"{r['fund_code']} {r['period']} {r['n']}只" for r in rows],
            )
        )

    return findings


# ------------------------------------------------------------------
# 检查项 7：报告期错配
# ------------------------------------------------------------------

# 报告期错配阈值：最近一期基金数 < 历史最大期基金数 × 该比例。
REPORT_PERIOD_COVERAGE_RATIO = 0.6


def inspect_holding_report_period_coverage(
    conn: sqlite3.Connection,
    min_coverage_ratio: float = REPORT_PERIOD_COVERAGE_RATIO,
) -> list[InspectionFinding]:
    """检查持仓报告期覆盖率：最近一期基金数 < 历史最大期 × 阈值。

    业务含义：基金池中所有基金应每季度披露持仓。如果最近一期覆盖基金数
    显著低于历史最大期（小于 60%），说明本期数据采集遗漏较多。
    """
    findings: list[InspectionFinding] = []
    candidates = [("stock_holdings", "report_period"), ("fund_stock_holdings", "report_date")]
    table = None
    period_col = None
    for t, col in candidates:
        try:
            conn.execute(f"SELECT 1 FROM {t} LIMIT 1")
            table = t
            period_col = col
            break
        except sqlite3.OperationalError:
            continue
    if not table:
        return findings

    rows = conn.execute(
        f"""
        SELECT {period_col} AS period, COUNT(DISTINCT fund_code) AS fund_count
        FROM {table}
        WHERE {period_col} IS NOT NULL
        GROUP BY {period_col}
        ORDER BY {period_col} DESC
        LIMIT 20
        """,
    ).fetchall()
    if not rows:
        return findings

    # 最大基金数
    max_funds = max(r["fund_count"] for r in rows)
    # 最近一期
    latest = rows[0]
    if max_funds == 0:
        return findings

    ratio = latest["fund_count"] / max_funds
    if ratio < min_coverage_ratio:
        findings.append(
            InspectionFinding(
                severity="critical" if ratio < 0.4 else "warning",
                category="report_period_coverage",
                title=(
                    f"最近报告期 {latest['period']} 仅覆盖 {latest['fund_count']} 只基金"
                    f"（历史最大 {max_funds} 只，{ratio*100:.0f}%）"
                ),
                detail=(
                    f"近 20 期最大覆盖 {max_funds} 只基金，最近一期 {latest['fund_count']} 只，"
                    f"覆盖率 {ratio*100:.0f}% < 阈值 {min_coverage_ratio*100:.0f}%。"
                    "本期可能数据采集遗漏较多，建议检查 fetch_fund_holdings.py。"
                ),
                count=latest["fund_count"],
                samples=[
                    f"{r['period']} 覆盖 {r['fund_count']} 只"
                    for r in rows[:8]
                ],
            )
        )

    return findings


# ------------------------------------------------------------------
# 检查项 8：综合概览（用于 report 顶部 KPI 行）
# ------------------------------------------------------------------


def collect_overview(conn: sqlite3.Connection) -> dict[str, Any]:
    """收集数据质量综合指标，用于报告顶部 KPI 和 API 返回。

    字段说明：
    - total_funds: 基金池总数
    - nav_covered_funds: 至少有一条 NAV 数据的基金数
    - nav_missing_funds: 没有 NAV 数据的基金数
    - holding_covered_funds: 至少有一份持仓报告的基金数
    - holding_missing_funds: 没有持仓的基金数
    - latest_nav_date: 整个池最近 NAV 日期
    - latest_holding_period: 整个池最近持仓报告期
    - factor_stock_count: 因子覆盖股票数
    - latest_factor_as_of: 最新因子 as_of_date
    - benchmark_resolved_funds: 至少有一个 resolved 组件的基金数
    - benchmark_total_funds: 有 benchmark_components 行的基金数
    """
    overview: dict[str, Any] = {
        "total_funds": 0,
        "nav_covered_funds": 0,
        "nav_missing_funds": 0,
        "holding_covered_funds": 0,
        "holding_missing_funds": 0,
        "latest_nav_date": None,
        "latest_holding_period": None,
        "factor_stock_count": 0,
        "latest_factor_as_of": None,
        "benchmark_resolved_funds": 0,
        "benchmark_total_funds": 0,
    }

    try:
        overview["total_funds"] = conn.execute(
            "SELECT COUNT(*) FROM fund_profiles"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        pass

    try:
        row = conn.execute(
            """
            SELECT
                COUNT(DISTINCT fund_code) AS covered,
                MAX(nav_date) AS latest
            FROM nav_history
            """
        ).fetchone()
        if row:
            overview["nav_covered_funds"] = row["covered"] or 0
            overview["latest_nav_date"] = row["latest"]
    except sqlite3.OperationalError:
        pass

    try:
        overview["nav_missing_funds"] = conn.execute(
            """
            SELECT COUNT(*) FROM fund_profiles fp
            WHERE NOT EXISTS (
                SELECT 1 FROM nav_history nh WHERE nh.fund_code = fp.fund_code
            )
            """
        ).fetchone()[0]
    except sqlite3.OperationalError:
        pass

    # 持仓表
    for t, col in (("stock_holdings", "report_period"), ("fund_stock_holdings", "report_date")):
        try:
            conn.execute(f"SELECT 1 FROM {t} LIMIT 1")
        except sqlite3.OperationalError:
            continue
        try:
            row = conn.execute(
                f"""
                SELECT COUNT(DISTINCT fund_code) AS covered, MAX({col}) AS latest
                FROM {t}
                """
            ).fetchone()
            if row:
                overview["holding_covered_funds"] = row["covered"] or 0
                overview["latest_holding_period"] = row["latest"]
        except sqlite3.OperationalError:
            continue
        break

    try:
        overview["holding_missing_funds"] = conn.execute(
            """
            SELECT COUNT(*) FROM fund_profiles fp
            WHERE NOT EXISTS (
                SELECT 1 FROM stock_holdings sh WHERE sh.fund_code = fp.fund_code
            )
              AND NOT EXISTS (
                SELECT 1 FROM fund_stock_holdings fsh WHERE fsh.fund_code = fp.fund_code
            )
            """
        ).fetchone()[0]
    except sqlite3.OperationalError:
        pass

    # 因子表
    for ftable in ("stock_factor_values", "stock_factors"):
        try:
            conn.execute(f"SELECT 1 FROM {ftable} LIMIT 1")
        except sqlite3.OperationalError:
            continue
        try:
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({ftable})").fetchall()}
            if "as_of_date" in cols:
                row = conn.execute(
                    f"SELECT MAX(as_of_date) AS latest, COUNT(DISTINCT stock_code) AS n "
                    f"FROM {ftable}"
                ).fetchone()
            else:
                # stock_factors 表无 as_of_date 概念时，只统计股票数
                row = conn.execute(
                    f"SELECT NULL AS latest, COUNT(DISTINCT stock_code) AS n FROM {ftable}"
                ).fetchone()
            if row:
                overview["factor_stock_count"] = row["n"] or 0
                overview["latest_factor_as_of"] = row["latest"]
        except sqlite3.OperationalError:
            pass
        break

    # 基准
    try:
        overview["benchmark_total_funds"] = conn.execute(
            "SELECT COUNT(DISTINCT fund_code) FROM benchmark_components"
        ).fetchone()[0]
        overview["benchmark_resolved_funds"] = conn.execute(
            "SELECT COUNT(DISTINCT fund_code) FROM benchmark_components "
            "WHERE status = 'resolved'"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        pass

    return overview


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
        # 异常值检查
        findings.extend(inspect_nav_return_outliers(conn))
        findings.extend(inspect_holding_weight_outliers(conn))
        findings.extend(inspect_holding_count_outliers(conn))
        # 报告期错配
        findings.extend(inspect_holding_report_period_coverage(conn))
        # 综合概览（写到 JSON 方便后续消费）
        overview = collect_overview(conn)

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
                    "overview": overview,
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
