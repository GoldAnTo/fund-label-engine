"""从 Investoday 拉取已校验的精确指数日行情，输出标准 component returns CSV。

边界：只支持白名单中的精确指数，不做名称宽匹配，不写 SQLite。
输出 CSV 可交给 import_benchmark_component_returns.py 导入 benchmark_component_returns。
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import date
from pathlib import Path
from typing import Any

import requests

ALLOWED_INDEXES = {
    "H11001": "中证全债",
    "H11009": "中证综合债",
    "H11006": "中证国债",
    "000998": "中证TMT",
    "000964": "中证新兴产业",
    "000942": "内地消费",
    "931027": "港股通大消费",
    "399102": "创业板综合",
    "399101": "中小企业综合",
    "HSI": "恒生指数",
}
SOURCE_TAG = "investoday:index/quotes"
DEFAULT_BASE_URL = "https://data-api.investoday.net/data"


class InvestodayDataError(RuntimeError):
    pass


def _require_api_key() -> str:
    api_key = os.getenv("INVESTDATA_API_KEY") or os.getenv("INVESTODAY_API_KEY")
    if not api_key:
        raise InvestodayDataError("missing INVESTDATA_API_KEY or INVESTODAY_API_KEY")
    return api_key


def _rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("code") != 0:
        raise InvestodayDataError(f"Investoday error code={payload.get('code')} message={payload.get('message')}")
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows = data.get("data") or data.get("list") or data.get("items")
        if isinstance(rows, list):
            return rows
    return []


def _post_json(base_url: str, api_key: str, path: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    response = requests.post(
        base_url.rstrip("/") + path,
        headers={"apiKey": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    response.raise_for_status()
    return _rows_from_payload(response.json())


def _get_json(base_url: str, api_key: str, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    response = requests.get(
        base_url.rstrip("/") + path,
        headers={"apiKey": api_key},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return _rows_from_payload(response.json())


def validate_basic_info(index_code: str, rows: list[dict[str, Any]]) -> None:
    expected_name = ALLOWED_INDEXES[index_code]
    matched = [row for row in rows if str(row.get("indexCode") or "") == index_code]
    if not matched:
        raise InvestodayDataError(f"{index_code}: basic-info missing exact indexCode")
    row = matched[0]
    actual_names = [str(row.get("indexName") or ""), str(row.get("indexNameFull") or "")]
    if not any(expected_name in name for name in actual_names):
        raise InvestodayDataError(
            f"{index_code}: basic-info name {actual_names!r} does not match expected {expected_name!r}"
        )


def build_csv_rows(index_code: str, quote_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    csv_rows: list[dict[str, str]] = []
    for row in quote_rows:
        raw_date = str(row.get("date") or "")[:10]
        try:
            trade_date = date.fromisoformat(raw_date).isoformat()
            prev_close = float(row["previousClosePrice"])
            close = float(row["closePrice"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvestodayDataError(f"{index_code}: invalid quote row {row!r}") from exc
        if prev_close <= 0:
            raise InvestodayDataError(f"{index_code}: previousClosePrice must be positive on {trade_date}")
        csv_rows.append(
            {
                "component_code": index_code,
                "trade_date": trade_date,
                "daily_return": f"{close / prev_close - 1.0:.10f}",
                "source": SOURCE_TAG,
            }
        )
    csv_rows.sort(key=lambda item: item["trade_date"])
    return csv_rows


def fetch_index_csv_rows(
    base_url: str,
    api_key: str,
    index_code: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, str]]:
    if index_code not in ALLOWED_INDEXES:
        raise InvestodayDataError(f"{index_code}: not in whitelist")
    basic_rows = _post_json(base_url, api_key, "/index/basic-info", {"indexCodes": [index_code]})
    validate_basic_info(index_code, basic_rows)
    quote_rows = _get_json(
        base_url,
        api_key,
        "/index/quotes",
        {
            "indexCode": index_code,
            "beginDate": start_date,
            "endDate": end_date,
            "pageNum": 1,
            "pageSize": 500,
        },
    )
    return build_csv_rows(index_code, quote_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--codes",
        default=",".join(ALLOWED_INDEXES),
        help="逗号分隔指数代码；只能是白名单内精确指数",
    )
    parser.add_argument("--base-url", default=os.getenv("FINANCIAL_DATA_BASE_URL", DEFAULT_BASE_URL))
    args = parser.parse_args(argv)

    api_key = _require_api_key()
    codes = [code.strip() for code in args.codes.split(",") if code.strip()]
    for code in codes:
        if code not in ALLOWED_INDEXES:
            raise SystemExit(f"unsupported code {code}; allowed={','.join(ALLOWED_INDEXES)}")

    rows: list[dict[str, str]] = []
    for code in codes:
        code_rows = fetch_index_csv_rows(args.base_url, api_key, code, args.start_date, args.end_date)
        rows.extend(code_rows)
        print(f"{code} {ALLOWED_INDEXES[code]}: {len(code_rows)} rows")

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["component_code", "trade_date", "daily_return", "source"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
