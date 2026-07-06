"""同类分位数计算。

为每只基金在每个关键指标上，按风格标签分组计算百分位排名。

设计要点：
- 分组维度：以风格标签为单位，加上一个 'all_market' 全市场基线
- 指标方向：'higher_better'（越大越好，如收益、夏普）和 'lower_better'（越小越好，如回撤、波动）
- 百分位口径：percentile ∈ [0, 1]，越大代表排名越靠前
- 排名口径：rank_value 从 1 开始，1 = 同类第一
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# 关键指标清单
# metric_code  -> (source_table, source_metric_col, direction)
PERCENTILE_METRICS: list[tuple[str, str, str, str]] = [
    # (metric_code, source_table, source_metric_col, direction)
    ("annualized_return_1y", "fund_label_evidence", "metric", "higher_better"),
    ("sharpe_ratio_1y", "fund_label_evidence", "metric", "higher_better"),
    ("max_drawdown_1y", "fund_label_evidence", "metric", "lower_better"),
    ("annualized_excess_return_1y", "fund_label_evidence", "metric", "higher_better"),
    ("information_ratio_1y", "fund_label_evidence", "metric", "higher_better"),
    ("roe_weighted", "fund_factor_exposures", "exposure_value", "higher_better"),
    ("pe_weighted", "fund_factor_exposures", "exposure_value", "lower_better"),
    ("pb_weighted", "fund_factor_exposures", "exposure_value", "lower_better"),
]

# 从 fund_label_evidence 取数时用的 metric 字符串
# 多个 metric 字符串映射到同一 percentile metric_code
EVIDENCE_METRIC_ALIAS: dict[str, list[str]] = {
    "annualized_return_1y": ["annualized_return_1y"],
    "sharpe_ratio_1y": ["sharpe_ratio_1y"],
    "max_drawdown_1y": ["max_drawdown_1y"],
    "annualized_excess_return_1y": ["annualized_excess_return_1y"],
    "information_ratio_1y": ["information_ratio_1y"],
}


@dataclass
class FundMetricRow:
    fund_code: str
    metric_code: str
    value: float


def _load_fund_metrics(
    conn: sqlite3.Connection,
    run_id: str,
) -> dict[str, dict[str, float]]:
    """加载所有基金的所有关键指标值。

    返回 {fund_code: {metric_code: value}}
    """
    metrics: dict[str, dict[str, float]] = {}
    # 临时设 row_factory 以便用列名访问
    original_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        # 1) 从 fund_label_evidence 取（用 label_code 关联 fund_label_results 过滤本 run）
        for percentile_metric, evidence_metrics in EVIDENCE_METRIC_ALIAS.items():
            placeholders = ",".join("?" for _ in evidence_metrics)
            rows = conn.execute(
                f"""
                SELECT fle.fund_code, fle.value
                FROM fund_label_evidence fle
                JOIN fund_label_results flr
                  ON fle.run_id = flr.run_id
                 AND fle.fund_code = flr.fund_code
                 AND fle.label_code = flr.label_code
                WHERE fle.run_id = ?
                  AND fle.metric IN ({placeholders})
                  AND flr.status = 'active'
                """,
                [run_id, *evidence_metrics],
            ).fetchall()
            for row in rows:
                try:
                    v = float(row["value"])
                except (TypeError, ValueError):
                    continue
                metrics.setdefault(row["fund_code"], {})[percentile_metric] = v

        # 2) 从 fund_factor_exposures 取
        factor_metric_codes = [m for m, src, _, _ in PERCENTILE_METRICS if src == "fund_factor_exposures"]
        if factor_metric_codes:
            placeholders = ",".join("?" for _ in factor_metric_codes)
            rows = conn.execute(
                f"""
                SELECT fund_code, factor_code, exposure_value
                FROM fund_factor_exposures
                WHERE factor_code IN ({placeholders})
                """,
                factor_metric_codes,
            ).fetchall()
            for row in rows:
                try:
                    v = float(row["exposure_value"])
                except (TypeError, ValueError):
                    continue
                metrics.setdefault(row["fund_code"], {})[row["factor_code"]] = v
    finally:
        conn.row_factory = original_factory

    return metrics


def _load_fund_style_tags(
    conn: sqlite3.Connection,
    run_id: str,
) -> dict[str, set[str]]:
    """加载每只基金的风格标签集合。"""
    original_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT fund_code, label_code
            FROM fund_label_results
            WHERE run_id = ? AND status = 'active'
            """,
            (run_id,),
        ).fetchall()
        tag_map: dict[str, set[str]] = {}
        for row in rows:
            tag_map.setdefault(row["fund_code"], set()).add(row["label_code"])
    finally:
        conn.row_factory = original_factory
    return tag_map


def _percentile_and_rank(
    values: list[float],
    target: float,
    direction: str,
) -> tuple[float, int]:
    """计算 target 在 values 中的百分位和排名。

    percentile: [0, 1]，越大越靠前。
    rank_value: 从 1 开始。
    """
    if not values or target is None:
        return 0.0, 0
    n = len(values)
    if direction == "higher_better":
        # 排名：比 target 大的数量 + 1
        rank = sum(1 for v in values if v > target) + 1
        # 百分位：(n - rank) / (n - 1)，最高 1.0
        percentile = (n - rank) / (n - 1) if n > 1 else 1.0
    else:  # lower_better
        rank = sum(1 for v in values if v < target) + 1
        percentile = (n - rank) / (n - 1) if n > 1 else 1.0
    return percentile, rank


def compute_percentile_ranks(
    conn: sqlite3.Connection,
    run_id: str,
) -> list[dict[str, Any]]:
    """为整次跑批计算所有基金 × 所有指标 × 所有分组的百分位。

    返回写入 fund_percentile_rank 表的记录列表。
    """
    metrics = _load_fund_metrics(conn, run_id)
    tag_map = _load_fund_style_tags(conn, run_id)

    if not metrics:
        return []

    # 准备分组：每只基金对应的分组列表 = ['all_market', *基金的所有风格标签]
    fund_groups: dict[str, list[str]] = {}
    group_members: dict[str, set[str]] = {"all_market": set(metrics.keys())}
    for fund_code in metrics.keys():
        tags = tag_map.get(fund_code, set())
        groups = ["all_market", *sorted(tags)]
        fund_groups[fund_code] = groups
        for g in tags:
            group_members.setdefault(g, set()).add(fund_code)

    now = datetime.now(UTC).isoformat()
    records: list[dict[str, Any]] = []

    for metric_code, _, _, direction in PERCENTILE_METRICS:
        for group_name, members in group_members.items():
            if len(members) < 2:
                # 同类少于 2 只基金，百分位无意义
                continue
            # 收集本组在本指标上的所有值
            values: list[float] = []
            for m in members:
                v = metrics.get(m, {}).get(metric_code)
                if v is not None:
                    values.append(v)
            if len(values) < 2:
                continue
            # 为本组每只基金计算百分位
            for fund_code in members:
                v = metrics.get(fund_code, {}).get(metric_code)
                if v is None:
                    continue
                percentile, rank = _percentile_and_rank(values, v, direction)
                records.append({
                    "run_id": run_id,
                    "fund_code": fund_code,
                    "label_code": group_name,
                    "metric_code": metric_code,
                    "metric_value": v,
                    "percentile": round(percentile, 4),
                    "rank_value": rank,
                    "peer_count": len(values),
                    "direction": direction,
                    "computed_at": now,
                })

    return records


def write_percentile_ranks(
    conn: sqlite3.Connection,
    records: list[dict[str, Any]],
) -> int:
    """写入 fund_percentile_rank 表。"""
    if not records:
        return 0
    conn.executemany(
        """
        INSERT OR REPLACE INTO fund_percentile_rank
        (run_id, fund_code, label_code, metric_code,
         metric_value, percentile, rank_value, peer_count, direction, computed_at)
        VALUES (:run_id, :fund_code, :label_code, :metric_code,
                :metric_value, :percentile, :rank_value, :peer_count, :direction, :computed_at)
        """,
        records,
    )
    return len(records)
