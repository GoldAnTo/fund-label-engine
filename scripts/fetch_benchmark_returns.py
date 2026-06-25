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

INDEX_MAP = {
    "沪深300指数": ("000300", "1.000300", "沪深300"),
    "沪深300": ("000300", "1.000300", "沪深300"),
    "中证500指数": ("000905", "1.000905", "中证500"),
    "中证500": ("000905", "1.000905", "中证500"),
    "中证800指数": ("000906", "1.000906", "中证800"),
    "中证800": ("000906", "1.000906", "中证800"),
    "上证国债指数": ("000012", "1.000012", "上证国债"),
    "上证国债": ("000012", "1.000012", "上证国债"),
}

_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_SYNTHETIC_CALENDAR_SECID = "1.000300"
_DEPOSIT_CURRENT_ANNUAL_RETURN = 0.0035
_ONE_YEAR_DEPOSIT_ANNUAL_RETURN = 0.015


@dataclass(frozen=True)
class BenchmarkComponent:
    benchmark_code: str
    secid: str
    benchmark_name: str
    weight: float


@dataclass(frozen=True)
class BenchmarkMapping:
    fund_code: str
    benchmark_code: str
    benchmark_name: str
    source_text: str
    mapping_reason: str
    components: tuple[BenchmarkComponent, ...]


def _read_codes(path: str | Path) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _normalize(text: str | None) -> str:
    return (text or "").replace(" ", "").replace("％", "%").strip()


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
        components=(BenchmarkComponent(code, secid, name, 1.0),),
    )


def _daily_return_from_annual(annual_return: float) -> float:
    return (1.0 + annual_return) ** (1.0 / 252.0) - 1.0


def _synthetic_component(
    code: str,
    name: str,
    annual_return: float,
    weight: float,
) -> BenchmarkComponent:
    return BenchmarkComponent(code, f"synthetic:{annual_return:.6f}", name, weight)


def _parse_weighted_components(text: str) -> tuple[BenchmarkComponent, ...] | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    components: list[BenchmarkComponent] = []
    seen_codes: set[str] = set()
    for key, (code, secid, name) in INDEX_MAP.items():
        if code in seen_codes:
            continue
        patterns = [
            rf"(?P<w1>\d+(?:\.\d+)?)%[×*]{re.escape(key)}(?:收益率)?",
            rf"{re.escape(key)}(?:收益率)?[×*](?P<w2>\d+(?:\.\d+)?)%",
            rf"(?P<w3>\d+(?:\.\d+)?)%{re.escape(key)}(?:收益率)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            weight_text = (
                match.groupdict().get("w1")
                or match.groupdict().get("w2")
                or match.groupdict().get("w3")
            )
            if weight_text is None:
                continue
            components.append(
                BenchmarkComponent(code, secid, name, float(weight_text) / 100.0)
            )
            seen_codes.add(code)
            break
    deposit_patterns = [
        (
            r"(?P<w>\d+(?:\.\d+)?)%[×*]?(?:同期银行)?(?:商业银行)?(?:税后)?活期存款(?:基准)?利率(?:\(税后\))?",
            "BANK_CURRENT",
            "银行活期存款利率",
            _DEPOSIT_CURRENT_ANNUAL_RETURN,
        ),
        (
            r"(?:同期银行)?(?:商业银行)?(?:税后)?活期存款(?:基准)?利率(?:\(税后\))?[×*](?P<w>\d+(?:\.\d+)?)%",
            "BANK_CURRENT",
            "银行活期存款利率",
            _DEPOSIT_CURRENT_ANNUAL_RETURN,
        ),
        (
            r"(?P<w>\d+(?:\.\d+)?)%[×*]?(?:银行)?活期存款利率(?:\(税后\))?",
            "BANK_CURRENT",
            "银行活期存款利率",
            _DEPOSIT_CURRENT_ANNUAL_RETURN,
        ),
    ]
    for pattern, code, name, annual_return in deposit_patterns:
        match = re.search(pattern, normalized)
        if not match or code in seen_codes:
            continue
        components.append(
            _synthetic_component(
                code,
                name,
                annual_return,
                float(match.group("w")) / 100.0,
            )
        )
        seen_codes.add(code)
    fixed_return_match = re.fullmatch(
        r"(?:1年期|一年期|金融机构人民币一年期|1年期人民币)"
        r"(?:定期)?存款(?:基准)?利率(?:\(税后\))?\+(?P<plus>\d+(?:\.\d+)?)%.*",
        normalized,
    )
    if fixed_return_match and not components:
        plus = float(fixed_return_match.group("plus")) / 100.0
        return (
            _synthetic_component(
                "BANK_1Y_PLUS",
                f"一年期存款利率+{plus:.2%}",
                _ONE_YEAR_DEPOSIT_ANNUAL_RETURN + plus,
                1.0,
            ),
        )
    if not components:
        return None
    total_weight = sum(item.weight for item in components)
    if not 0.9999 <= total_weight <= 1.0001:
        return None
    return tuple(components)


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
            if re.search(pattern, bench):
                return _single_mapping(
                    fund_code,
                    code,
                    secid,
                    name,
                    benchmark or "",
                    "index_fund_benchmark_supported_index",
                )
    components = _parse_weighted_components(bench)
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
    for row in rows:
        mapping = resolve_benchmark(
            row["fund_code"],
            row["fund_type"],
            row["tracking_target"],
            row["benchmark"],
        )
        if mapping:
            mappings.append((row, mapping))
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
                ],
            )
            writer.writeheader()
            for row, mapping in mappings:
                writer.writerow(
                    {
                        "fund_code": row["fund_code"],
                        "fund_name": row["fund_name"],
                        "fund_type": row["fund_type"],
                        "benchmark_code": mapping.benchmark_code,
                        "benchmark_name": mapping.benchmark_name,
                        "mapping_reason": mapping.mapping_reason,
                        "tracking_target": row["tracking_target"],
                        "benchmark": row["benchmark"],
                    }
                )

    print(f"funds={len(rows)} mapped={len(mappings)} unmapped={len(unmapped)}")
    if args.dry_run:
        for row, mapping in mappings:
            print(row["fund_code"], row["fund_name"], mapping.benchmark_name, mapping.mapping_reason)
        return 0

    ensure_table(conn)
    conn.execute(
        f"DELETE FROM benchmark_returns WHERE fund_code IN ({','.join('?' for _ in codes)})",
        codes,
    )
    conn.commit()
    cache: dict[str, list[dict[str, str | float]]] = {}
    cache[_SYNTHETIC_CALENDAR_SECID] = fetch_index_returns(
        _SYNTHETIC_CALENDAR_SECID,
        args.start_date,
        args.end_date,
    )
    total = 0
    for idx, (row, mapping) in enumerate(mappings, 1):
        for component in mapping.components:
            if component.secid.startswith("synthetic:"):
                continue
            if component.secid not in cache:
                cache[component.secid] = fetch_index_returns(component.secid, args.start_date, args.end_date)
                time.sleep(0.2)
        index_rows = _compose_returns(mapping, cache)
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
                    f"eastmoney.index_kline:{mapping.mapping_reason}",
                ),
            )
        conn.commit()
        total += len(index_rows)
        print(f"[{idx}/{len(mappings)}] {mapping.fund_code} {mapping.benchmark_name}: {len(index_rows)} rows")
    print(f"Done. mapped_funds={len(mappings)}, total_rows={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
