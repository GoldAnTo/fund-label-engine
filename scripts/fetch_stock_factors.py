"""拉取股票因子横截面数据，落到独立的 factor cache DB。

数据源：东财公开 datacenter-web 接口（无 cookie / JS）。
- PE / PB / 总市值 → RPT_VALUEANALYSIS_DET（按 TRADE_DATE 过滤当日横截面）
- ROE / 营收增速 / 净利润增速 → RPT_LICO_FN_CPD（按 REPORTDATE 过滤最新季报）
- valuation_percentile → 用 PB 横截面做 0~1 平滑分位数（派生）

写入到 ``data/stock_factors.sqlite``（项目根 data/ 目录），表结构与
``backend/app/persistence/migrations/0003_phase5_stock_factors_and_labels.sql``
中的 ``stock_factor_values`` 一致，可被 ``load_stock_factors`` 直接读取。

用法：
    python scripts/fetch_stock_factors.py --trade-date 2026-06-23 \\
        --report-date 2025-09-30
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_factor_values (
    stock_code TEXT NOT NULL,
    factor_code TEXT NOT NULL,
    factor_value REAL,
    as_of_date TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (stock_code, factor_code, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_stock_factor_values_date
    ON stock_factor_values(as_of_date);
"""


def _curl_get(url: str, retries: int = 3) -> dict:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            out = subprocess.run(
                ["curl", "-s", "--max-time", "25", "-A", "Mozilla/5.0", url],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            if not out.strip():
                raise ValueError("empty body")
            return json.loads(out)
        except Exception as exc:  # noqa: BLE001 - 重试覆盖网络抖动 + JSON 异常
            last_exc = exc
            time.sleep(2 + attempt * 2)
    assert last_exc is not None
    raise last_exc


def fetch_pe_pb_market_cap(conn: sqlite3.Connection, trade_date: str) -> int:
    """拉取当日 PE_TTM / PB_MRQ / TOTAL_MARKET_CAP / CLOSE_PRICE 横截面。

    其中 CLOSE_PRICE 既作为单独的 ``close_price`` 因子保存，也用于后续
    ``compute_dividend_yield`` 的分母（TTM 每股分红 / 当前股价）。
    """
    inserted = 0
    page = 1
    while True:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_VALUEANALYSIS_DET&"
            "columns=SECURITY_CODE,TRADE_DATE,PE_TTM,PB_MRQ,TOTAL_MARKET_CAP,CLOSE_PRICE&"
            f"pageNumber={page}&pageSize=200&sortColumns=SECURITY_CODE&sortTypes=1&"
            f"filter=(TRADE_DATE%3D%27{trade_date}%27)"
        )
        payload = _curl_get(url)
        data = payload.get("result") or {}
        items = data.get("data") or []
        if not items:
            break
        for it in items:
            code = it.get("SECURITY_CODE")
            if not code:
                continue
            pe = it.get("PE_TTM")
            pb = it.get("PB_MRQ")
            cap = it.get("TOTAL_MARKET_CAP")
            close = it.get("CLOSE_PRICE")
            rows: list[tuple[str, float]] = []
            if isinstance(pe, (int, float)):
                rows.append(("pe", float(pe)))
            if isinstance(pb, (int, float)):
                rows.append(("pb", float(pb)))
            if isinstance(cap, (int, float)) and cap > 0:
                rows.append(("log10_market_cap", math.log10(cap)))
            if isinstance(close, (int, float)) and close > 0:
                rows.append(("close_price", float(close)))
            for fc, fv in rows:
                conn.execute(
                    "INSERT OR REPLACE INTO stock_factor_values "
                    "(stock_code, factor_code, factor_value, as_of_date, source) "
                    "VALUES (?, ?, ?, ?, 'eastmoney.value_analysis')",
                    (code, fc, fv, trade_date),
                )
                inserted += 1
        conn.commit()
        pages = data.get("pages") or 0
        sys.stderr.write(
            f"  [PE/PB] page {page}/{pages}: +{len(items)} stocks\n"
        )
        if pages and page >= pages:
            break
        page += 1
        time.sleep(0.15)
    return inserted


def fetch_roe_growth(
    conn: sqlite3.Connection, trade_date: str, report_date: str
) -> int:
    """拉取最新季报的 ROE / 营收增速 / 净利增速，as_of_date 复用 trade_date。"""
    inserted = 0
    page = 1
    while True:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_LICO_FN_CPD&"
            "columns=SECURITY_CODE,WEIGHTAVG_ROE,YSTZ,SJLTZ&"
            f"pageNumber={page}&pageSize=200&sortColumns=SECURITY_CODE&sortTypes=1&"
            f"filter=(REPORTDATE%3D%27{report_date}%27)"
        )
        payload = _curl_get(url)
        data = payload.get("result") or {}
        items = data.get("data") or []
        if not items:
            break
        for it in items:
            code = it.get("SECURITY_CODE")
            if not code:
                continue
            roe = it.get("WEIGHTAVG_ROE")
            ystz = it.get("YSTZ")
            sjltz = it.get("SJLTZ")
            rows: list[tuple[str, float]] = []
            # 东财把百分数原值返回（如 8.28 表示 8.28%），归一化为 0~1 小数
            if isinstance(roe, (int, float)):
                rows.append(("roe", roe / 100.0))
            if isinstance(ystz, (int, float)):
                rows.append(("revenue_growth", ystz / 100.0))
            if isinstance(sjltz, (int, float)):
                rows.append(("profit_growth", sjltz / 100.0))
            for fc, fv in rows:
                conn.execute(
                    "INSERT OR REPLACE INTO stock_factor_values "
                    "(stock_code, factor_code, factor_value, as_of_date, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (code, fc, fv, trade_date, f"eastmoney.cpd_{report_date}"),
                )
                inserted += 1
        conn.commit()
        pages = data.get("pages") or 0
        sys.stderr.write(
            f"  [ROE/Growth] page {page}/{pages}: +{len(items)} stocks\n"
        )
        if pages and page >= pages:
            break
        page += 1
        time.sleep(0.15)
    return inserted


def compute_valuation_percentile(
    conn: sqlite3.Connection, trade_date: str
) -> int:
    """根据当日 PB 横截面排名，给出 0~1 平滑百分位（0=最便宜）。

    用 ``(rank+0.5)/n``，避免 0 和 1 的端点退化。
    """
    rows = conn.execute(
        "SELECT stock_code, factor_value FROM stock_factor_values "
        "WHERE factor_code='pb' AND as_of_date=? AND factor_value > 0 "
        "ORDER BY factor_value",
        (trade_date,),
    ).fetchall()
    n = len(rows)
    inserted = 0
    for rank, (code, _pb) in enumerate(rows):
        pct = (rank + 0.5) / n
        conn.execute(
            "INSERT OR REPLACE INTO stock_factor_values "
            "(stock_code, factor_code, factor_value, as_of_date, source) "
            "VALUES (?, 'valuation_percentile', ?, ?, 'derived.pb_xs')",
            (code, pct, trade_date),
        )
        inserted += 1
    conn.commit()
    sys.stderr.write(f"  [valuation_percentile] {inserted} stocks ranked\n")
    return inserted


def compute_dividend_yield(
    conn: sqlite3.Connection, trade_date: str, start_date: str
) -> int:
    """TTM 股息率：过去 ``[start_date, trade_date]`` 区间内已实施分配的现金分红
    （每 10 股派 RMB）聚合到每只股票，再除以当日 close_price。

    数据源：东财 RPT_SHAREBONUS_DET。``PRETAX_BONUS_RMB`` 单位是「元/10股」（例如
    "10派10.00元" → 字段值 10），所以每股年化分红 = SUM / 10。

    只统计 ``ASSIGN_PROGRESS=='实施分配'`` 的行，避免把"董事会决议通过"等未实施
    的预案错算成实际分红。
    """
    # 收集 [start_date, trade_date] 区间内全部已实施分配。pageSize=500 翻页。
    pretax_by_code: dict[str, float] = {}
    page = 1
    pages_total = 0
    while True:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_SHAREBONUS_DET&"
            "columns=SECURITY_CODE,PRETAX_BONUS_RMB,EX_DIVIDEND_DATE,ASSIGN_PROGRESS&"
            f"pageNumber={page}&pageSize=500&sortColumns=EX_DIVIDEND_DATE&sortTypes=-1&"
            f"filter=(EX_DIVIDEND_DATE%3E%27{start_date}%27)"
            f"(EX_DIVIDEND_DATE%3C%3D%27{trade_date}%27)"
        )
        payload = _curl_get(url)
        data = payload.get("result") or {}
        items = data.get("data") or []
        if not items:
            break
        for it in items:
            # 「实施分配」之外的状态（如「董事会决议通过」）跳过
            if it.get("ASSIGN_PROGRESS") != "实施分配":
                continue
            code = it.get("SECURITY_CODE")
            bonus = it.get("PRETAX_BONUS_RMB")
            if not code or not isinstance(bonus, (int, float)):
                continue
            pretax_by_code[code] = pretax_by_code.get(code, 0.0) + float(bonus)
        pages_total = data.get("pages") or pages_total
        sys.stderr.write(
            f"  [dividend] page {page}/{pages_total}: +{len(items)} bonus rows, "
            f"cum_stocks={len(pretax_by_code)}\n"
        )
        if pages_total and page >= pages_total:
            break
        page += 1
        time.sleep(0.15)

    # 用同一份 trade_date 下的 close_price 计算股息率
    close_rows = conn.execute(
        "SELECT stock_code, factor_value FROM stock_factor_values "
        "WHERE factor_code='close_price' AND as_of_date=? AND factor_value > 0",
        (trade_date,),
    ).fetchall()
    close_by_code: dict[str, float] = {row[0]: float(row[1]) for row in close_rows}

    inserted = 0
    for code, ttm_bonus_per_10 in pretax_by_code.items():
        close = close_by_code.get(code)
        if close is None or close <= 0:
            continue
        per_share = ttm_bonus_per_10 / 10.0
        yield_ = per_share / close
        # 异常值过滤：股息率超过 50% 视为脏数据，跳过
        if yield_ < 0 or yield_ > 0.5:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO stock_factor_values "
            "(stock_code, factor_code, factor_value, as_of_date, source) "
            "VALUES (?, 'dividend_yield', ?, ?, 'derived.sharebonus_ttm')",
            (code, yield_, trade_date),
        )
        inserted += 1
    conn.commit()
    sys.stderr.write(
        f"  [dividend_yield] paid stocks={len(pretax_by_code)}, "
        f"with_close_price={inserted}\n"
    )
    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-date", required=True, help="如 2026-06-23")
    parser.add_argument(
        "--report-date",
        required=True,
        help="最新季报日期，如 2025-09-30",
    )
    parser.add_argument(
        "--dividend-start-date",
        default=None,
        help=(
            "TTM 股息率统计窗口起点。默认 trade-date 往前推 365 天。"
            "区间为左开右闭：(start, trade_date]。"
        ),
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"输出 SQLite 路径，默认 {DEFAULT_DB}",
    )
    args = parser.parse_args(argv)

    if args.dividend_start_date is None:
        from datetime import date, timedelta

        td = date.fromisoformat(args.trade_date)
        args.dividend_start_date = (td - timedelta(days=365)).isoformat()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(CREATE_TABLE_SQL)
    conn.commit()

    sys.stderr.write(f"db: {db_path}\n")
    sys.stderr.write(
        f"trade_date={args.trade_date}, report_date={args.report_date}, "
        f"dividend_start={args.dividend_start_date}\n"
    )

    sys.stderr.write("step 1/4: PE / PB / market_cap / close_price\n")
    n1 = fetch_pe_pb_market_cap(conn, args.trade_date)
    sys.stderr.write("step 2/4: ROE / revenue_growth / profit_growth\n")
    n2 = fetch_roe_growth(conn, args.trade_date, args.report_date)
    sys.stderr.write("step 3/4: valuation_percentile (derived)\n")
    n3 = compute_valuation_percentile(conn, args.trade_date)
    sys.stderr.write("step 4/4: dividend_yield (derived TTM)\n")
    n4 = compute_dividend_yield(
        conn, args.trade_date, args.dividend_start_date
    )

    conn.close()
    print(
        f"Done. value_analysis={n1} cpd={n2} percentile={n3} dividend_yield={n4}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
