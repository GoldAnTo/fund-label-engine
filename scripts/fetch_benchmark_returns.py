from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SupportedKind = Literal["index", "synthetic"]

INDEX_MAP = {
    "沪深300指数": ("000300", "1.000300", "沪深300"),
    "沪深300": ("000300", "1.000300", "沪深300"),
    "中证500指数": ("000905", "1.000905", "中证500"),
    "中证500": ("000905", "1.000905", "中证500"),
    "中证800指数": ("000906", "1.000906", "中证800"),
    "中证800": ("000906", "1.000906", "中证800"),
    "中证700指数": ("000907", "1.000907", "中证700"),
    "中证700": ("000907", "1.000907", "中证700"),
    "中证2000指数": ("932000", "2.932000", "中证2000"),
    "中证2000": ("932000", "2.932000", "中证2000"),
    "中证TMT产业主题指数": ("000998", "1.000998", "中证TMT"),
    "中证TMT": ("000998", "1.000998", "中证TMT"),
    "中证红利指数": ("000922", "1.000922", "中证红利"),
    "中证红利": ("000922", "1.000922", "中证红利"),
    "中证环保产业指数": ("000827", "1.000827", "中证环保"),
    "中证环保": ("000827", "1.000827", "中证环保"),
    "中证医药100指数": ("000978", "1.000978", "医药100"),
    "中证医药100": ("000978", "1.000978", "医药100"),
    "中证细分医药产业主题指数": ("000814", "1.000814", "细分医药"),
    "细分医药": ("000814", "1.000814", "细分医药"),
    "中证内地消费主题指数": ("000942", "1.000942", "内地消费"),
    "中证内地消费": ("000942", "1.000942", "内地消费"),
    "恒生指数": ("HSI", "100.HSI", "恒生指数"),
    "恒生": ("HSI", "100.HSI", "恒生指数"),
    "中证港股通大消费主题指数": ("931027", "2.931027", "港股通大消费"),
    "港股通大消费": ("931027", "2.931027", "港股通大消费"),
    "中证主要消费行业指数": ("000932", "sina:sh000932", "中证主要消费"),
    "中证主要消费": ("000932", "sina:sh000932", "中证主要消费"),
    "中证可选消费行业指数": ("000931", "sina:sh000931", "中证可选消费"),
    "中证可选消费": ("000931", "sina:sh000931", "中证可选消费"),
    "中证新兴产业指数": ("000964", "sina:sh000964", "中证新兴产业"),
    "中证新兴产业": ("000964", "sina:sh000964", "中证新兴产业"),
    "中证医药卫生指数": ("000933", "sina:sh000933", "中证医药卫生"),
    "中证医药卫生": ("000933", "sina:sh000933", "中证医药卫生"),
    "创业板综合指数": ("399102", "sina:sz399102", "创业板综合"),
    "创业板综合": ("399102", "sina:sz399102", "创业板综合"),
    "中小企业综合指数": ("399101", "sina:sz399101", "中小企业综合"),
    "中小企业综合": ("399101", "sina:sz399101", "中小企业综合"),
    "中证全债指数": ("H11001", "sina:shH11001", "中证全债"),
    "中证全债": ("H11001", "sina:shH11001", "中证全债"),
    "中证综合债指数": ("H11008", "sina:shH11008", "中证综合债"),
    "中证综合债券指数": ("H11008", "sina:shH11008", "中证综合债"),
    "中证综合债": ("H11008", "sina:shH11008", "中证综合债"),
    "中证国债指数": ("H11006", "sina:shH11006", "中证国债"),
    "中证国债": ("H11006", "sina:shH11006", "中证国债"),
    "上证国债指数": ("000012", "1.000012", "上证国债"),
    "上证国债": ("000012", "1.000012", "上证国债"),
}

_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_SINA_KLINE_URL = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData"
_SYNTHETIC_CALENDAR_SECID = "1.000300"
_DEPOSIT_CURRENT_ANNUAL_RETURN = 0.0035
_ONE_YEAR_DEPOSIT_ANNUAL_RETURN = 0.015
_THREE_YEAR_DEPOSIT_ANNUAL_RETURN = 0.02

_EAST_TO_SINA: dict[str, str] = {
    "1.000300": "sh000300",
    "1.000905": "sh000905",
    "1.000906": "sh000906",
    "1.000907": "sh000907",
    "1.000998": "sh000998",
    "1.000922": "sh000922",
    "1.000827": "sh000827",
    "1.000814": "sh000814",
    "1.000942": "sh000942",
    "1.000978": "sh000978",
    "1.000012": "sh000012",
    "2.932000": "sh932000",
}


@dataclass(frozen=True)
class BenchmarkComponent:
    benchmark_code: str
    secid: str
    benchmark_name: str
    weight: float
    kind: SupportedKind = "index"
    source_text: str = ""


@dataclass(frozen=True)
class BenchmarkMapping:
    fund_code: str
    benchmark_code: str
    benchmark_name: str
    source_text: str
    mapping_reason: str
    components: tuple[BenchmarkComponent, ...]


@dataclass(frozen=True)
class ComponentAudit:
    component_code: str | None
    component_name: str
    weight: float | None
    source_text: str
    status: str
    reason: str
    secid: str | None = None


def _read_codes(path: str | Path) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _normalize(text: str | None) -> str:
    return (
        (text or "")
        .replace(" ", "")
        .replace("％", "%")
        .replace("＋", "+")
        .replace("＊", "*")
        .strip()
    )


def _daily_return_from_annual(annual_return: float) -> float:
    return (1.0 + annual_return) ** (1.0 / 252.0) - 1.0


def _synthetic_component(
    code: str,
    name: str,
    annual_return: float,
    weight: float,
    source_text: str,
) -> BenchmarkComponent:
    return BenchmarkComponent(
        code,
        f"synthetic:{annual_return:.6f}",
        name,
        weight,
        "synthetic",
        source_text,
    )


def _single_mapping(
    fund_code: str,
    code: str,
    secid: str,
    name: str,
    source_text: str,
    reason: str,
) -> BenchmarkMapping:
    return BenchmarkMapping(
        fund_code=fund_code,
        benchmark_code=code,
        benchmark_name=name,
        source_text=source_text,
        mapping_reason=reason,
        components=(BenchmarkComponent(code, secid, name, 1.0, "index", source_text),),
    )


def _extract_weight(term: str) -> tuple[str, float | None]:
    patterns = [
        r"(?P<w>\d+(?:\.\d+)?)%[×*]?(?P<name>.+)",
        r"(?P<name>.+?)[×*](?P<w>\d+(?:\.\d+)?)%",
        r"(?P<w>\d+(?:\.\d+)?)%(?P<name>.+)",
    ]
    for pattern in patterns:
        match = re.fullmatch(pattern, term)
        if match:
            return match.group("name"), float(match.group("w")) / 100.0
    return term, None


def _clean_component_name(name: str) -> str:
    cleaned = re.sub(r"收益率|\(税后\)|\(全价\)|\(总值\)|\(财富\)|财富|全价|总值", "", name)
    cleaned = re.sub(r"\(使用估值汇率折算\)|\(指年收益率,评价时按期间折算\)", "", cleaned)
    return cleaned.strip()


def _match_index_component(name: str, weight: float, source_text: str) -> BenchmarkComponent | None:
    cleaned = _clean_component_name(name)
    for key in sorted(INDEX_MAP, key=len, reverse=True):
        if key in cleaned:
            code, secid, index_name = INDEX_MAP[key]
            return BenchmarkComponent(code, secid, index_name, weight, "index", source_text)
    return None


def _match_synthetic_component(name: str, weight: float, source_text: str) -> BenchmarkComponent | None:
    cleaned = _clean_component_name(name)
    if "活期存款" in cleaned:
        return _synthetic_component(
            "BANK_CURRENT",
            "银行活期存款利率",
            _DEPOSIT_CURRENT_ANNUAL_RETURN,
            weight,
            source_text,
        )
    return None


def _parse_fixed_return_benchmark(text: str) -> tuple[BenchmarkComponent, ...] | None:
    normalized = _normalize(text)
    fixed_plus = re.fullmatch(
        r"(?P<base>1年期|一年期|金融机构人民币一年期|1年期人民币|三年期银行)"
        r"(?:定期)?存款(?:基准)?利率(?:\(税后\))?\+(?P<plus>\d+(?:\.\d+)?)%.*",
        normalized,
    )
    if fixed_plus:
        base = fixed_plus.group("base")
        base_rate = _THREE_YEAR_DEPOSIT_ANNUAL_RETURN if "三年" in base else _ONE_YEAR_DEPOSIT_ANNUAL_RETURN
        plus = float(fixed_plus.group("plus")) / 100.0
        return (
            _synthetic_component(
                "BANK_FIXED_PLUS",
                f"{base}存款利率+{plus:.2%}",
                base_rate + plus,
                1.0,
                text,
            ),
        )
    annual = re.fullmatch(r"年化收益率(?P<rate>\d+(?:\.\d+)?)%", normalized)
    if annual:
        annual_return = float(annual.group("rate")) / 100.0
        return (
            _synthetic_component(
                "FIXED_ANNUAL_RETURN",
                f"年化收益率{annual_return:.2%}",
                annual_return,
                1.0,
                text,
            ),
        )
    return None


def parse_benchmark_components(text: str | None) -> tuple[tuple[BenchmarkComponent, ...] | None, list[ComponentAudit]]:
    normalized = _normalize(text)
    if not normalized or "暂未披露" in normalized:
        return None, [ComponentAudit(None, "", None, text or "", "unresolved", "benchmark_missing")]

    fixed = _parse_fixed_return_benchmark(text or "")
    if fixed:
        return fixed, [
            ComponentAudit(
                component.component_code if hasattr(component, "component_code") else component.benchmark_code,
                component.benchmark_name,
                component.weight,
                component.source_text,
                "resolved",
                "synthetic_fixed_return",
                component.secid,
            )
            for component in fixed
        ]

    components: list[BenchmarkComponent] = []
    audits: list[ComponentAudit] = []
    terms = [term for term in re.split(r"\+", normalized) if term]
    for term in terms:
        raw_name, weight = _extract_weight(term)
        component_name = _clean_component_name(raw_name)
        if weight is None:
            audits.append(ComponentAudit(None, component_name, None, term, "unresolved", "weight_missing"))
            continue
        component = _match_index_component(component_name, weight, term)
        if component is None:
            component = _match_synthetic_component(component_name, weight, term)
        if component is None:
            audits.append(
                ComponentAudit(
                    None,
                    component_name,
                    weight,
                    term,
                    "unresolved",
                    "unsupported_component_or_missing_source",
                )
            )
            continue
        components.append(component)
        audits.append(
            ComponentAudit(
                component.benchmark_code,
                component.benchmark_name,
                component.weight,
                term,
                "resolved",
                component.kind,
                component.secid,
            )
        )
    total_weight = sum(component.weight for component in components)
    if audits and any(audit.status != "resolved" for audit in audits):
        return None, audits
    if not components:
        return None, audits
    if not 0.9999 <= total_weight <= 1.0001:
        audits.append(
            ComponentAudit(
                None,
                "total_weight",
                total_weight,
                normalized,
                "unresolved",
                "resolved_weight_sum_not_100_percent",
            )
        )
        return None, audits
    return tuple(components), audits


def resolve_benchmark(
    fund_code: str,
    fund_type: str | None,
    tracking_target: str | None,
    benchmark: str | None,
) -> BenchmarkMapping | None:
    target = _normalize(tracking_target)
    bench = _normalize(benchmark)
    if target and target != "该基金无跟踪标的":
        for key, (code, secid, name) in INDEX_MAP.items():
            if target == key:
                return _single_mapping(
                    fund_code,
                    code,
                    secid,
                    name,
                    tracking_target or "",
                    "tracking_target_exact_supported_index",
                )
    if fund_type == "指数型-股票":
        for key, (code, secid, name) in INDEX_MAP.items():
            if not key.endswith("指数"):
                continue
            pattern = rf"(?:95%[×*])?{re.escape(key)}收益率(?:[×*]95%)?"
            if re.fullmatch(pattern, bench):
                return _single_mapping(
                    fund_code,
                    code,
                    secid,
                    name,
                    benchmark or "",
                    "index_fund_benchmark_supported_index",
                )
    components, _audits = parse_benchmark_components(benchmark)
    if components:
        code = "+".join(f"{item.benchmark_code}:{item.weight:.2f}" for item in components)
        name = "+".join(f"{item.benchmark_name}{item.weight:.0%}" for item in components)
        return BenchmarkMapping(
            fund_code=fund_code,
            benchmark_code=code,
            benchmark_name=name,
            source_text=benchmark or "",
            mapping_reason="composite_benchmark_supported_components",
            components=components,
        )
    return None


def fetch_index_returns(secid: str, start_date: str, end_date: str) -> list[dict[str, str | float]]:
    params = urllib.parse.urlencode(
        {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": "1",
            "beg": start_date.replace("-", ""),
            "end": end_date.replace("-", ""),
        }
    )
    req = urllib.request.Request(
        f"{_KLINE_URL}?{params}",
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
    )
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            text = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
            break
        except Exception as exc:  # noqa: BLE001 - 指数接口偶发断连，有限重试
            last_error = exc
            time.sleep(1.0 * (attempt + 1))
    else:
        raise RuntimeError(f"failed to fetch index returns for {secid}: {last_error}")
    payload = json.loads(text)
    data = payload.get("data")
    if not data or not data.get("klines"):
        return []
    rows = []
    for line in data["klines"]:
        parts = line.split(",")
        if len(parts) < 9:
            continue
        try:
            daily_return = float(parts[8]) / 100.0
        except ValueError:
            continue
        rows.append({"trade_date": parts[0], "daily_return": daily_return})
    return rows


def fetch_sina_index_returns(symbol: str, start_date: str, end_date: str) -> list[dict[str, str | float]]:
    rows: list[dict[str, str | float]] = []
    for datalen in (800, 1500, 2500, 4000):
        params = urllib.parse.urlencode(
            {"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(datalen)}
        )
        req = urllib.request.Request(
            f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData?{params}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
        )
        try:
            text = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
        except Exception:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list) or not data:
            continue
        closes: list[tuple[str, float]] = []
        for row in data:
            trade_date = str(row.get("day", "")).replace("-", "")
            if not start_date.replace("-", "") <= trade_date <= end_date.replace("-", ""):
                continue
            try:
                close = float(row["close"])
            except (KeyError, TypeError, ValueError):
                continue
            closes.append((f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}", close))
        closes.sort()
        if not closes:
            continue
        if closes[0][0] > start_date or closes[-1][0] < end_date:
            rows = []
            continue
        returns: list[dict[str, str | float]] = []
        prev_close: float | None = None
        for trade_date, close in closes:
            if prev_close is not None and prev_close > 0:
                returns.append({"trade_date": trade_date, "daily_return": close / prev_close - 1.0})
            prev_close = close
        return returns
    return rows


def fetch_component_returns(secid: str, start_date: str, end_date: str) -> list[dict[str, str | float]]:
    if secid.startswith("sina:"):
        sina_rows = fetch_sina_index_returns(secid.split(":", 1)[1], start_date, end_date)
        if sina_rows:
            return sina_rows
        return fetch_index_returns(secid.split(":", 1)[1], start_date, end_date)
    sina_symbol = _EAST_TO_SINA.get(secid)
    if sina_symbol:
        sina_rows = fetch_sina_index_returns(sina_symbol, start_date, end_date)
        if sina_rows:
            return sina_rows
    return fetch_index_returns(secid, start_date, end_date)


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_returns (
            fund_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            daily_return REAL NOT NULL,
            benchmark_code TEXT,
            benchmark_name TEXT,
            source TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fund_code, trade_date)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_components (
            fund_code TEXT NOT NULL,
            component_order INTEGER NOT NULL,
            component_code TEXT,
            component_name TEXT NOT NULL,
            weight REAL,
            source_text TEXT,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            secid TEXT,
            run_source TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fund_code, component_order)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_benchmark_components_status ON benchmark_components(status, reason)"
    )


def _load_existing_component_returns(
    conn: sqlite3.Connection,
    benchmark_code: str,
) -> list[dict[str, str | float]]:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark_returns'"
    ).fetchone()
    if table is None:
        return []
    rows = conn.execute(
        "SELECT trade_date, AVG(daily_return) AS daily_return "
        "FROM benchmark_returns WHERE benchmark_code = ? "
        "GROUP BY trade_date ORDER BY trade_date",
        (benchmark_code,),
    ).fetchall()
    return [
        {"trade_date": row["trade_date"], "daily_return": float(row["daily_return"])}
        for row in rows
    ]


def _fetch_or_reuse_component_returns(
    conn: sqlite3.Connection,
    component: BenchmarkComponent,
    start_date: str,
    end_date: str,
) -> list[dict[str, str | float]]:
    try:
        rows = fetch_component_returns(component.secid, start_date, end_date)
    except Exception as exc:  # noqa: BLE001 - 外部行情源失败时尝试复用本地缓存
        print(f"WARN fetch_failed {component.secid} {component.benchmark_name}: {exc}")
        rows = []
    if rows:
        return rows
    reused = _load_existing_component_returns(conn, component.benchmark_code)
    if reused:
        print(
            f"WARN reused_existing_returns {component.benchmark_code} "
            f"{component.benchmark_name}: {len(reused)} rows"
        )
    return reused


def _compose_returns(
    mapping: BenchmarkMapping,
    cache: dict[str, list[dict[str, str | float]]],
) -> list[dict[str, str | float]]:
    by_date: dict[str, float] = {}
    required_dates: set[str] | None = None
    for component in mapping.components:
        if component.secid.startswith("synthetic:"):
            continue
        rows = cache.get(component.secid, [])
        component_dates = {str(row["trade_date"]) for row in rows}
        required_dates = component_dates if required_dates is None else required_dates & component_dates
    if required_dates is None:
        rows = cache.get(_SYNTHETIC_CALENDAR_SECID)
        if rows is None:
            return []
        required_dates = {str(row["trade_date"]) for row in rows}
    if not required_dates:
        return []
    for component in mapping.components:
        if component.secid.startswith("synthetic:"):
            annual_return = float(component.secid.split(":", 1)[1])
            daily_return = _daily_return_from_annual(annual_return)
            for trade_date in required_dates:
                by_date[trade_date] = by_date.get(trade_date, 0.0) + daily_return * component.weight
            continue
        rows = cache[component.secid]
        row_by_date = {str(row["trade_date"]): float(row["daily_return"]) for row in rows}
        for trade_date in required_dates:
            by_date[trade_date] = by_date.get(trade_date, 0.0) + row_by_date[trade_date] * component.weight
    return [
        {"trade_date": trade_date, "daily_return": by_date[trade_date]}
        for trade_date in sorted(by_date)
    ]


def _write_component_audits(
    conn: sqlite3.Connection,
    fund_code: str,
    audits: list[ComponentAudit],
    run_source: str,
) -> None:
    for idx, audit in enumerate(audits, 1):
        conn.execute(
            """
            INSERT OR REPLACE INTO benchmark_components
            (fund_code, component_order, component_code, component_name, weight,
             source_text, status, reason, secid, run_source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                fund_code,
                idx,
                audit.component_code,
                audit.component_name,
                audit.weight,
                audit.source_text,
                audit.status,
                audit.reason,
                audit.secid,
                run_source,
            ),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch benchmark/index daily returns for mapped Phase1 funds.")
    parser.add_argument("--db", required=True, help="fundData/source SQLite path")
    parser.add_argument("--codes-file", required=True, help="fund code list")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mapping-csv", help="optional output CSV for mapping audit")
    args = parser.parse_args(argv)

    codes = _read_codes(args.codes_file)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT fund_code, fund_name, fund_type, benchmark, tracking_target
        FROM fund_profiles
        WHERE fund_code IN ({','.join('?' for _ in codes)})
        ORDER BY fund_code
        """,
        codes,
    ).fetchall()
    mappings = []
    unmapped = []
    audit_by_fund: dict[str, list[ComponentAudit]] = {}
    for row in rows:
        _components, audits = parse_benchmark_components(row["benchmark"])
        audit_by_fund[row["fund_code"]] = audits
        mapping = resolve_benchmark(
            row["fund_code"],
            row["fund_type"],
            row["tracking_target"],
            row["benchmark"],
        )
        if mapping:
            mappings.append((row, mapping))
            if mapping.mapping_reason != "composite_benchmark_supported_components":
                audit_by_fund[row["fund_code"]] = [
                    ComponentAudit(
                        c.benchmark_code,
                        c.benchmark_name,
                        c.weight,
                        c.source_text,
                        "resolved",
                        c.kind,
                        c.secid,
                    )
                    for c in mapping.components
                ]
        else:
            unmapped.append(row)

    if args.mapping_csv:
        with open(args.mapping_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "fund_code",
                    "fund_name",
                    "fund_type",
                    "benchmark_code",
                    "benchmark_name",
                    "mapping_reason",
                    "tracking_target",
                    "benchmark",
                    "component_status",
                    "component_reasons",
                ],
            )
            writer.writeheader()
            for row in rows:
                mapping = next((m for r, m in mappings if r["fund_code"] == row["fund_code"]), None)
                audits = audit_by_fund.get(row["fund_code"], [])
                writer.writerow(
                    {
                        "fund_code": row["fund_code"],
                        "fund_name": row["fund_name"],
                        "fund_type": row["fund_type"],
                        "benchmark_code": mapping.benchmark_code if mapping else "",
                        "benchmark_name": mapping.benchmark_name if mapping else "",
                        "mapping_reason": mapping.mapping_reason if mapping else "unmapped",
                        "tracking_target": row["tracking_target"],
                        "benchmark": row["benchmark"],
                        "component_status": ";".join(a.status for a in audits),
                        "component_reasons": ";".join(a.reason for a in audits),
                    }
                )

    print(f"funds={len(rows)} mapped={len(mappings)} unmapped={len(unmapped)}")
    if args.dry_run:
        for row, mapping in mappings:
            print(row["fund_code"], row["fund_name"], mapping.benchmark_name, mapping.mapping_reason)
        return 0

    ensure_table(conn)
    conn.execute(
        f"DELETE FROM benchmark_components WHERE fund_code IN ({','.join('?' for _ in codes)})",
        codes,
    )
    for row in rows:
        _write_component_audits(conn, row["fund_code"], audit_by_fund.get(row["fund_code"], []), "fetch_benchmark_returns_v2")
    conn.commit()

    cache: dict[str, list[dict[str, str | float]]] = {}
    synthetic_calendar_component = BenchmarkComponent(
        _SYNTHETIC_CALENDAR_SECID.split(".", 1)[1],
        _SYNTHETIC_CALENDAR_SECID,
        "合成基准交易日历",
        1.0,
        "index",
        "calendar",
    )
    cache[_SYNTHETIC_CALENDAR_SECID] = _fetch_or_reuse_component_returns(
        conn,
        synthetic_calendar_component,
        args.start_date,
        args.end_date,
    )
    total = 0
    success = 0
    skipped = 0
    for idx, (row, mapping) in enumerate(mappings, 1):
        missing_source = False
        for component in mapping.components:
            if component.secid.startswith("synthetic:"):
                continue
            if component.secid not in cache:
                cache[component.secid] = _fetch_or_reuse_component_returns(
                    conn,
                    component,
                    args.start_date,
                    args.end_date,
                )
                time.sleep(0.2)
            if not cache[component.secid]:
                missing_source = True
        if missing_source:
            skipped += 1
            print(f"[{idx}/{len(mappings)}] SKIP {mapping.fund_code} {mapping.benchmark_name}: missing component returns")
            continue
        index_rows = _compose_returns(mapping, cache)
        if not index_rows:
            skipped += 1
            print(f"[{idx}/{len(mappings)}] SKIP {mapping.fund_code} {mapping.benchmark_name}: no composed rows")
            continue
        conn.execute("DELETE FROM benchmark_returns WHERE fund_code = ?", (mapping.fund_code,))
        for item in index_rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO benchmark_returns
                (fund_code, trade_date, daily_return, benchmark_code, benchmark_name, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    mapping.fund_code,
                    item["trade_date"],
                    item["daily_return"],
                    mapping.benchmark_code,
                    mapping.benchmark_name,
                    f"benchmark.component_returns:{mapping.mapping_reason}",
                ),
            )
        conn.commit()
        total += len(index_rows)
        success += 1
        print(f"[{idx}/{len(mappings)}] {mapping.fund_code} {mapping.benchmark_name}: {len(index_rows)} rows")
    print(f"Done. mapped_funds={len(mappings)}, success_funds={success}, skipped_funds={skipped}, total_rows={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
