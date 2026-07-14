"""使用 akshare 抓取真实基金数据并写入 SQLite 数据库。

用法:
    python scripts/fetch_real_data.py /tmp/fle-p0/source.sqlite

脚本会从 akshare 抓取 8 支覆盖 7 个认知方向的基金及其相关数据
（持仓、行业、经理、净值、费率、股票因子等），写入本地 SQLite。
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterable

# 避免环境代理干扰 akshare 接口
os.environ.setdefault("NO_PROXY", "*")

# 强制无缓冲输出，便于实时观察进度
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:  # noqa: BLE001
    pass

import akshare as ak
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 目标基金列表（覆盖 7 个认知方向） =====
TARGET_FUNDS: list[tuple[str, str, str]] = [
    ("110022", "易方达消费行业", "consumer"),
    ("320007", "诺安成长混合", "AI"),
    ("003095", "中欧医疗健康混合C", "innovation_drug"),
    ("100032", "富国中证红利指数增强", "dividend_defense"),
    ("000697", "汇添富移动互联", "growth_investing"),
    ("005827", "易方达蓝筹精选", "value_investing"),
    ("161725", "招商中证白酒指数", "consumer"),
    ("519983", "长信量化先锋混合", "value_investing"),
]

REPORT_DATES: list[str] = ["2024", "2023"]
NAV_LIMIT: int = 60
RETRY_TIMES: int = 3
RETRY_SLEEP: float = 1.5
TOP_N_HOLDINGS: int = 10

# ===== 表结构（与 seed_sample_db.py 保持一致） =====
SCHEMA: tuple[str, ...] = (
    """CREATE TABLE IF NOT EXISTS fund_profiles (
        fund_code TEXT PRIMARY KEY,
        fund_name TEXT NOT NULL,
        fund_type TEXT NOT NULL,
        inception_date TEXT,
        fund_company TEXT,
        fund_size REAL
    )""",
    """CREATE TABLE IF NOT EXISTS nav_history (
        fund_code TEXT NOT NULL,
        nav_date TEXT NOT NULL,
        nav REAL,
        adjusted_nav REAL,
        daily_return REAL,
        PRIMARY KEY (fund_code, nav_date)
    )""",
    """CREATE TABLE IF NOT EXISTS fund_stock_holdings (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        weight REAL NOT NULL,
        market TEXT,
        PRIMARY KEY (fund_code, report_date, stock_code)
    )""",
    """CREATE TABLE IF NOT EXISTS fund_industry_allocations (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        industry TEXT NOT NULL,
        weight REAL NOT NULL,
        PRIMARY KEY (fund_code, report_date, industry)
    )""",
    """CREATE TABLE IF NOT EXISTS fund_manager_links (
        fund_code TEXT NOT NULL,
        manager_name TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        tenure_years REAL
    )""",
    """CREATE TABLE IF NOT EXISTS fee_structures (
        fund_code TEXT PRIMARY KEY,
        management_fee REAL,
        custody_fee REAL,
        sales_service_fee REAL
    )""",
    """CREATE TABLE IF NOT EXISTS fund_positions (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        equity_position REAL,
        PRIMARY KEY (fund_code, report_date)
    )""",
    """CREATE TABLE IF NOT EXISTS stock_factors (
        stock_code TEXT NOT NULL,
        factor_date TEXT NOT NULL,
        pb REAL,
        roe REAL,
        dividend_yield REAL,
        revenue_growth REAL,
        profit_growth REAL,
        market_cap_bucket TEXT,
        valuation_percentile REAL,
        style TEXT,
        PRIMARY KEY (stock_code, factor_date)
    )""",
)


def _retry(callable_fn, *args, **kwargs):
    """带重试的调用封装，失败抛出最后一次异常。"""
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            return callable_fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_SLEEP)
    assert last_exc is not None
    raise last_exc


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in {"nan", "none"}:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        f = float(value)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _parse_quarter_label(label: str) -> str | None:
    """从 '2024年1季度股票投资明细' 中提取 'YYYY-MM-DD'。"""
    import re

    if not isinstance(label, str):
        return None
    m = re.search(r"(\d{4})年(\d)季度", label)
    if not m:
        # 兼容 '2024年4季度' 之类的格式
        m = re.search(r"(\d{4})年(\d+)\s*季度", label)
    if not m:
        return None
    year = int(m.group(1))
    quarter = int(m.group(2))
    end_month = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}.get(quarter)
    if not end_month:
        return None
    return f"{year}-{end_month}"


def fetch_fund_basic_info(fund_code: str) -> dict[str, Any]:
    """通过 fund_individual_basic_info_xq 获取基金基础信息与经理列表。"""
    info: dict[str, Any] = {
        "fund_code": fund_code,
        "fund_name": None,
        "fund_type": None,
        "inception_date": None,
        "fund_company": None,
        "fund_size": None,
        "managers": [],
    }
    try:
        df = _retry(ak.fund_individual_basic_info_xq, symbol=fund_code)
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: 基金基本信息抓取失败 - {exc}")
        return info
    if df is None or df.empty:
        return info
    item_col = "item" if "item" in df.columns else df.columns[0]
    value_col = "value" if "value" in df.columns else df.columns[1]
    for _, row in df.iterrows():
        item = str(row[item_col]).strip() if row[item_col] is not None else ""
        value = row[value_col]
        if value is None or (isinstance(value, float) and pd.isna(value)):
            value_str = ""
        else:
            value_str = str(value).strip()
        if item == "基金名称":
            info["fund_name"] = value_str or None
        elif item == "成立时间":
            info["inception_date"] = value_str or None
        elif item == "基金公司":
            info["fund_company"] = value_str or None
        elif item == "基金类型":
            info["fund_type"] = _normalize_fund_type(value_str)
        elif item == "最新规模":
            info["fund_size"] = _parse_fund_size(value_str)
        elif item == "基金经理":
            # 可能多人，用常见分隔符拆分
            managers = [m.strip() for m in re_split_managers(value_str) if m.strip()]
            info["managers"] = managers
    return info


def re_split_managers(value: str) -> list[str]:
    import re as _re

    if not value:
        return []
    # 常见分隔符：、、, , / ， 中英文逗号等
    parts = _re.split(r"[、,,，/／\s]+", value)
    return [p for p in parts if p]


def _normalize_fund_type(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if "股票" in raw:
        return "股票型"
    if "混合" in raw:
        return "混合型-偏股"
    if "债券" in raw:
        return "债券型"
    if "指数" in raw:
        return "指数型"
    return raw


def _parse_fund_size(raw: str | None) -> float | None:
    if not raw:
        return None
    s = raw.strip()
    if "亿" in s:
        num = s.replace("亿", "").strip()
        return _safe_float(num)
    if "万" in s:
        num = _safe_float(s.replace("万", "").strip())
        return num / 10000.0 if num is not None else None
    return _safe_float(s)


def fetch_holdings(fund_code: str) -> dict[str, list[tuple[str, str, float, str]]]:
    """抓取多个报告期的持仓，返回 {report_date: [(stock_code, stock_name, weight, market), ...]}。"""
    out: dict[str, list[tuple[str, str, float, str]]] = {}
    for date_label in REPORT_DATES:
        try:
            df = _retry(ak.fund_portfolio_hold_em, symbol=fund_code, date=date_label)
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: {date_label} 持仓抓取失败 - {exc}")
            continue
        if df is None or df.empty:
            continue
        if "占净值比例" not in df.columns or "股票代码" not in df.columns:
            continue
        quarter_col = "季度" if "季度" in df.columns else None
        report_date: str | None = None
        if quarter_col:
            report_date = _parse_quarter_label(str(df[quarter_col].iloc[0]))
        if not report_date:
            report_date = f"{date_label}-12-31"
        rows: list[tuple[str, str, float, str]] = []
        for _, row in df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            if not code or code.lower() == "nan":
                continue
            name = row.get("股票名称", "")
            name = str(name).strip() if name is not None else ""
            w_raw = row.get("占净值比例")
            w = _safe_float(w_raw)
            if w is None:
                continue
            # 占净值比例已经是百分比，转换为小数
            w_decimal = w / 100.0
            market = "HK" if _is_hk_code(code) else "A"
            rows.append((code, name, w_decimal, market))
        # 同报告期内同股票可能多行（重复数据），按股票代码去重，保留权重最大者
        dedup: dict[str, tuple[str, str, float, str]] = {}
        for code, name, w, market in rows:
            if code not in dedup or w > dedup[code][2]:
                dedup[code] = (code, name, w, market)
        rows = list(dedup.values())
        rows.sort(key=lambda x: x[2], reverse=True)
        rows = rows[:TOP_N_HOLDINGS]
        if rows:
            # 同报告期可能多条（不同季度），保留最新一个
            out[report_date] = rows
    return out


def _is_hk_code(code: str) -> bool:
    # 港股代码：5 位数字
    return code.isdigit() and len(code) == 5


def fetch_industry_allocations(fund_code: str) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for date_label in REPORT_DATES:
        try:
            df = _retry(
                ak.fund_portfolio_industry_allocation_em,
                symbol=fund_code,
                date=date_label,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: {date_label} 行业配置抓取失败 - {exc}")
            continue
        if df is None or df.empty:
            continue
        if "行业类别" not in df.columns or "占净值比例" not in df.columns:
            continue
        for _, row in df.iterrows():
            report_date = (
                str(row.get("截止时间", "")).strip()
                if row.get("截止时间") is not None
                else ""
            )
            industry = str(row.get("行业类别", "")).strip()
            w = _safe_float(row.get("占净值比例"))
            if not industry or w is None:
                continue
            if not report_date or report_date.lower() == "nan":
                report_date = f"{date_label}-12-31"
            # 限制每期最多 8 个行业
            out.setdefault(report_date, [])
            if len([x for x in out[report_date] if True]) < 8:
                out[report_date].append((industry, w / 100.0))
    return out


def fetch_nav_history(fund_code: str) -> list[tuple[str, float, float, float]]:
    """获取最近 NAV_LIMIT 个交易日的净值。"""
    try:
        df = _retry(ak.fund_open_fund_info_em, symbol=fund_code, indicator="累计净值走势")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: 净值抓取失败 - {exc}")
        return []
    if df is None or df.empty:
        return []
    if "净值日期" not in df.columns or "累计净值" not in df.columns:
        return []
    df = df.tail(NAV_LIMIT).reset_index(drop=True)
    rows: list[tuple[str, float, float, float]] = []
    prev_nav: float | None = None
    for _, row in df.iterrows():
        d = str(row["净值日期"]).strip()
        nav = _safe_float(row["累计净值"])
        if nav is None:
            continue
        if prev_nav is None or prev_nav == 0:
            daily = 0.0
        else:
            daily = (nav - prev_nav) / prev_nav
        rows.append((d, nav, nav, daily))
        prev_nav = nav
    return rows


def _fetch_one_stock_factor(code: str) -> tuple[str, dict[str, Any] | None]:
    """抓取单只股票的财务因子，返回 (code, factors_dict or None)。"""
    # 该接口中所有带 (%) 的列都是百分数，统一除以 100
    try:
        df = _retry(ak.stock_financial_analysis_indicator, symbol=code, start_year="2023")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: 股票 {code} 财务因子抓取失败 - {exc}", flush=True)
        return code, None
    if df is None or df.empty:
        return code, None
    # 取最新一行（按日期降序）
    if "日期" in df.columns:
        df = df.copy()
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df = df.sort_values("日期", ascending=False)
    row = df.iloc[0]

    def col(name: str) -> float | None:
        return _safe_float(row.get(name)) if name in df.columns else None

    roe = col("净资产收益率(%)")
    if roe is not None:
        roe = roe / 100.0
    rev_growth = col("主营业务收入增长率(%)")
    if rev_growth is not None:
        rev_growth = rev_growth / 100.0
    profit_growth = col("净利润增长率(%)")
    if profit_growth is not None:
        profit_growth = profit_growth / 100.0
    dividend_yield = col("股息发放率(%)")
    if dividend_yield is not None:
        dividend_yield = dividend_yield / 100.0

    # PB 来自 stock_value_em：列名是"市净率"（非百分数，是倍数）
    pb = _fetch_pb_from_value_em(code)

    return code, {
        "pb": pb,
        "roe": roe,
        "revenue_growth": rev_growth,
        "profit_growth": profit_growth,
        "dividend_yield": dividend_yield,
    }


def fetch_stock_factors(stock_codes: Iterable[str]) -> dict[str, dict[str, Any]]:
    """并发抓取股票的财务因子，返回 {stock_code: {...}}。"""
    unique_codes = sorted({c for c in stock_codes if c})
    out: dict[str, dict[str, Any]] = {}
    if not unique_codes:
        return out
    # 并发抓取（akshare 是网络 IO 密集型）
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_fetch_one_stock_factor, code): code for code in unique_codes}
        done = 0
        for fut in as_completed(futures):
            done += 1
            code, fac = fut.result()
            if fac is not None:
                out[code] = fac
            if done % 10 == 0 or done == len(unique_codes):
                print(f"  股票因子进度: {done}/{len(unique_codes)}", flush=True)
    return out


def _fetch_pb_from_value_em(stock_code: str) -> float | None:
    """通过 stock_value_em 获取最近一日的市净率（PB）。"""
    try:
        df = _retry(ak.stock_value_em, symbol=stock_code)
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: 股票 {stock_code} PB 抓取失败 - {exc}")
        return None
    if df is None or df.empty or "市净率" not in df.columns:
        return None
    # 取最后一行（最近交易日）
    last = df.iloc[-1]
    v = _safe_float(last.get("市净率"))
    return v


def _market_cap_bucket(pb: float | None) -> str | None:
    """用 PB 粗略判断市值风格（仅作简化占位）。"""
    if pb is None:
        return None
    # 简化：返回统一标签；真实场景应由总市值判断
    return "large_cap"


def fetch_market_pb_quantile() -> float | None:
    """获取全市场近 10 年 PB 分位（最近交易日），作为估值分位的近似基准。"""
    try:
        df = _retry(ak.stock_a_all_pb)
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: 全市场 PB 抓取失败 - {exc}")
        return None
    if df is None or df.empty:
        return None
    last = df.iloc[-1]
    for col_name in (
        "quantileInRecent10YearsMiddlePB",
        "quantileInAllHistoryMiddlePB",
    ):
        if col_name in df.columns:
            v = _safe_float(last.get(col_name))
            if v is not None:
                return v
    return None


def fetch_and_seed(db_path: str | Path) -> None:
    """主流程：抓取真实数据填充数据库。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()

        market_pb_quantile = fetch_market_pb_quantile()
        print(f"全市场近期 PB 分位（参考）: {market_pb_quantile}")

        # 用于汇总的容器
        profiles_rows: list[tuple] = []
        holdings_rows: list[tuple] = []
        industry_rows: list[tuple] = []
        manager_rows: list[tuple] = []
        fee_rows: list[tuple] = []
        nav_rows: list[tuple] = []
        position_rows: list[tuple] = []

        all_stock_codes: set[str] = set()
        # 用一个 dict 保存每个基金对应的 stock_codes 列表，便于后续关联 manager 任期等
        fund_stock_codes: dict[str, list[str]] = {}

        for idx, (fund_code, fund_name, direction) in enumerate(TARGET_FUNDS, start=1):
            print(f"[{idx}/{len(TARGET_FUNDS)}] 抓取 {fund_code} {fund_name}...")

            # 1. 基本信息 + 经理
            info = fetch_fund_basic_info(fund_code)
            actual_name = info.get("fund_name") or fund_name
            profiles_rows.append(
                (
                    fund_code,
                    actual_name,
                    info.get("fund_type") or "混合型-偏股",
                    info.get("inception_date"),
                    info.get("fund_company"),
                    info.get("fund_size"),
                )
            )
            for mgr in info.get("managers") or []:
                manager_rows.append(
                    (
                        fund_code,
                        mgr,
                        info.get("inception_date"),
                        None,
                        None,
                    )
                )
            manager_count = len(info.get("managers") or [])
            print(f"  基本信息 OK, 经理 {manager_count} 人")

            # 2. 持仓
            holdings_by_date = fetch_holdings(fund_code)
            holdings_count = 0
            stock_codes: list[str] = []
            seen_keys: set[tuple[str, str]] = set()
            for rdate, rows in holdings_by_date.items():
                for code, name, weight, market in rows:
                    key = (rdate, code)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    holdings_rows.append(
                        (fund_code, rdate, code, name, weight, market)
                    )
                    stock_codes.append(code)
                    holdings_count += 1
            fund_stock_codes[fund_code] = stock_codes
            all_stock_codes.update(stock_codes)
            print(f"  持仓: {len(holdings_by_date)} 个报告期, 共 {holdings_count} 只")

            # 3. 行业配置
            industry_by_date = fetch_industry_allocations(fund_code)
            industry_count = 0
            for rdate, rows in industry_by_date.items():
                for industry, w in rows:
                    industry_rows.append((fund_code, rdate, industry, w))
                    industry_count += 1
            print(f"  行业: {industry_count} 条")

            # 4. 净值历史
            nav_data = fetch_nav_history(fund_code)
            for d, nav, adj_nav, daily in nav_data:
                nav_rows.append((fund_code, d, nav, adj_nav, daily))
            print(f"  净值: {len(nav_data)} 天")

            # 5. 费率（写默认值）
            fee_rows.append((fund_code, 0.015, 0.0025, None))

            # 6. 仓位（从十大重仓股权重估算）
            for rdate, rows in holdings_by_date.items():
                # 估算股票仓位 = top10 权重之和 * 1.2（考虑非重仓部分），上限 0.95
                top10_sum = sum(w for _, _, w, _ in rows)
                equity_pos = min(top10_sum * 1.2, 0.95)
                position_rows.append((fund_code, rdate, round(equity_pos, 4)))

        # 7. 股票因子
        print(f"开始抓取 {len(all_stock_codes)} 只股票的财务因子...")
        factors_map = fetch_stock_factors(sorted(all_stock_codes))

        # 计算 valuation_percentile：在已抓到的股票中按 PB 排序的相对分位
        # 取不到 PB 的留 None
        pb_pairs = [
            (code, f["pb"]) for code, f in factors_map.items() if f.get("pb") is not None
        ]
        if pb_pairs:
            pb_pairs.sort(key=lambda x: x[1])
            n = len(pb_pairs)
            rank = {code: (i + 1) / n for i, (code, _) in enumerate(pb_pairs)}
        else:
            rank = {}

        factor_rows: list[tuple] = []
        factor_date = "2025-12-31"
        for code, fac in factors_map.items():
            pb = fac.get("pb")
            percentile = rank.get(code, market_pb_quantile)
            style = _infer_style(fac)
            factor_rows.append(
                (
                    code,
                    factor_date,
                    pb,
                    fac.get("roe"),
                    fac.get("dividend_yield"),
                    fac.get("revenue_growth"),
                    fac.get("profit_growth"),
                    _market_cap_bucket(pb),
                    percentile,
                    style,
                )
            )

        # 写入数据库
        conn.executemany(
            "INSERT INTO fund_profiles VALUES (?, ?, ?, ?, ?, ?)",
            profiles_rows,
        )
        conn.executemany(
            "INSERT INTO fund_stock_holdings VALUES (?, ?, ?, ?, ?, ?)",
            holdings_rows,
        )
        conn.executemany(
            "INSERT INTO fund_industry_allocations VALUES (?, ?, ?, ?)",
            industry_rows,
        )
        conn.executemany(
            "INSERT INTO fund_manager_links VALUES (?, ?, ?, ?, ?)",
            manager_rows,
        )
        conn.executemany(
            "INSERT INTO fee_structures VALUES (?, ?, ?, ?)",
            fee_rows,
        )
        conn.executemany(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            nav_rows,
        )
        conn.executemany(
            "INSERT INTO fund_positions VALUES (?, ?, ?)",
            position_rows,
        )
        conn.executemany(
            "INSERT INTO stock_factors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            factor_rows,
        )
        conn.commit()

        # 统计
        n_funds = len({r[0] for r in profiles_rows})
        n_holdings = len(holdings_rows)
        n_stocks = len(factor_rows)
        print(
            f"数据库已写入: {path}, 共 {n_funds} 基金, {n_holdings} 持仓, {n_stocks} 股票"
        )
    finally:
        conn.close()


def _infer_style(fac: dict[str, Any]) -> str | None:
    """根据财务因子推断风格标签。"""
    pb = fac.get("pb")
    roe = fac.get("roe")
    growth = fac.get("revenue_growth") or 0.0
    div_yield = fac.get("dividend_yield") or 0.0
    if div_yield and div_yield > 0.03:
        return "dividend_steady"
    if roe is not None and roe > 0.15 and growth > 0.2:
        return "quality_growth"
    if growth and growth > 0.3:
        return "quality_growth"
    if pb is not None and pb < 3:
        return "deep_value"
    return "balanced"


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: fetch_real_data.py <db_path>", file=sys.stderr)
        return 2
    fetch_and_seed(argv[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())