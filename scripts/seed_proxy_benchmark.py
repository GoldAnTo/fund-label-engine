"""Fallback 工具：当外部基准数据源不可用时（如离线环境 / akshare 网络受限），
用本地的权益基金 NAV 平均值构造"代理市场指数"，给所有基金一个"可展示"的
业务口径。

⚠️ 这不是生产方案。生产应该跑：
    python scripts/fetch_benchmark_returns.py

它会从 akshare / Wind 拉取真实的指数日收益率，按每只基金的业绩比较
基准描述（fund_profiles.benchmark）做加权合成。

使用场景：
- 演示环境 / 内网部署 / 数据源暂时不可用
- 销售 / 客户演示，让展示池能跑出非零结果
- 性能 / 集成测试中不依赖外部数据

业务语义：
- 所有基金共享同一个"代理指数"（CSI300_PROXY）
- 代理指数 = 所有权益基金当天的平均日收益率
- 这样每只基金的 alpha 趋近 0、beta 趋近 1 — 业务上不正确，但能
  让相对标签的"计算管道"全部跑通，前端能看到所有功能

使用：
    python scripts/seed_proxy_benchmark.py --source /path/to/source.sqlite
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

CSI300_PROXY = "CSI300_PROXY"
SUPPORTED_EQUITY_TYPES = ("股票型", "混合型-偏股", "混合型-灵活", "指数型-股票")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="source DB 路径")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"source DB not found: {source}")

    con = sqlite3.connect(source)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 1. 创建表（如果不存在）
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_components (
            fund_code TEXT,
            component_code TEXT,
            component_name TEXT,
            weight REAL,
            source_text TEXT,
            status TEXT,
            reason TEXT,
            secid TEXT,
            component_order INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_returns (
            fund_code TEXT,
            benchmark_code TEXT,
            trade_date TEXT,
            daily_return REAL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_component_returns (
            component_code TEXT,
            trade_date TEXT,
            daily_return REAL
        )
        """
    )

    # 2. 列出所有权益基金
    placeholders = ",".join("?" * len(SUPPORTED_EQUITY_TYPES))
    codes = [
        r[0] for r in cur.execute(
            f"SELECT fund_code FROM fund_profiles WHERE fund_type IN ({placeholders}) "
            f"ORDER BY fund_code",
            SUPPORTED_EQUITY_TYPES,
        )
    ]
    if not codes:
        print("⚠️  未找到权益基金（fund_type ∈ " + ", ".join(SUPPORTED_EQUITY_TYPES) + "）")
        return
    print(f"权益基金: {len(codes)} 只")

    # 3. 写入 benchmark_components（status=resolved 以满足 eligibility 检查）
    for code in codes:
        cur.execute(
            "INSERT OR REPLACE INTO benchmark_components "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code, CSI300_PROXY, "沪深300代理", 1.0,
             "proxy_benchmark_seed", "resolved", "fallback_to_market_proxy",
             "1.000300", 1),
        )
    print(f"已写入 {len(codes)} 条 benchmark_components")

    # 4. 计算代理指数
    placeholders = ",".join("?" * len(codes))
    cur.execute(
        f"""
        SELECT nav_date, AVG(daily_growth_rate) AS avg_ret
        FROM nav_history
        WHERE daily_growth_rate IS NOT NULL
          AND fund_code IN ({placeholders})
        GROUP BY nav_date
        ORDER BY nav_date
        """,
        codes,
    )
    proxy_returns = cur.fetchall()
    print(f"代理指数: {len(proxy_returns)} 个交易日")

    if not proxy_returns:
        print("⚠️  未找到 NAV 数据，无法合成代理指数。请先跑 fetch_nav_history.py")
        return

    # 5. 写入 benchmark_component_returns
    cur.executemany(
        "INSERT OR REPLACE INTO benchmark_component_returns VALUES (?, ?, ?)",
        [(CSI300_PROXY, r["nav_date"], r["avg_ret"]) for r in proxy_returns],
    )

    # 6. 写入每只基金的 benchmark_returns
    inserts = [
        (code, CSI300_PROXY, r["nav_date"], r["avg_ret"])
        for code in codes
        for r in proxy_returns
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO benchmark_returns VALUES (?, ?, ?, ?)",
        inserts,
    )
    print(f"已写入 {len(inserts)} 条 benchmark_returns")

    con.commit()
    con.close()
    print(
        f"\n✅ 已为 {len(codes)} 只权益基金绑定代理基准\n"
        f"\n下一步：\n"
        f"1. python -m app.batch --source-db {source}  # 重跑批次\n"
        f"2. 重启后端，访问 /explorer 即可看到展示池更新"
    )


if __name__ == "__main__":
    main()
