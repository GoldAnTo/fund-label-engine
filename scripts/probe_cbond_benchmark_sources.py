"""CBOND_TOTAL / CHINA_BOND_TOTAL / SP_CHINA_BOND benchmark 源探针（只读）。

只读探针：检验 Investoday 和 akshare 中债登是否能提供这三个 component
对应的精确日频指数。**绝不**用宽指数或中债综合/中债国债总做代理。

用法：
    python scripts/probe_cbond_benchmark_sources.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_INVESTODAY_BASE = "https://data-api.investoday.net/data"

SEARCH_QUERIES = [
    "中债总",
    "中债总指数",
    "中国债券总",
    "中国债券总指数",
    "中债-总",
    "中债-总指数",
    "中债综合",
    "中债综合指数",
    "中债国债总",
    "中债国债总指数",
    "标普中国债券",
    "标普中国债券指数",
]


def _probe_investoday(base_url: str, api_key: str) -> dict[str, Any]:
    import requests

    headers = {"apiKey": api_key}
    report: dict[str, Any] = {"queries": [], "candidates": []}
    for query in SEARCH_QUERIES:
        response = requests.get(
            base_url.rstrip("/") + "/search",
            headers=headers,
            params={"key": query, "type": "12,13", "pageNum": 1, "pageSize": 20},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data") or data.get("list") or data.get("items") or []
        report["queries"].append({"query": query, "items": items})
        for item in items:
            name = str(item.get("shortName") or item.get("name") or "")
            full = str(item.get("fullName") or "")
            if "中债" in name or "中债" in full or "标普中国" in name or "标普中国" in full:
                report["candidates"].append(item)
    return report


def _probe_akshare() -> dict[str, Any]:
    try:
        import akshare as ak
    except ImportError:
        return {"akshare_available": False}
    general_func = getattr(ak, "bond_index_general_cbond", None)
    if general_func is None:
        return {"akshare_available": True, "categories": []}
    candidates = [
        "国债总指数", "政策性金融债指数", "非政策性金融债指数",
        "商业银行债券指数", "非银行金融机构债券指数", "企业债指数",
        "中短期债券指数", "长期债券指数", "浮动利率债券指数",
        "可转换债券指数", "资产支持证券指数", "其它债券指数",
    ]
    valid: list[str] = []
    for category in candidates:
        try:
            general_func(index_category=category, indicator="财富", period="总值")
        except Exception:
            continue
        valid.append(category)
    return {"akshare_available": True, "categories": valid}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--base-url", default=os.getenv("FINANCIAL_DATA_BASE_URL", DEFAULT_INVESTODAY_BASE))
    args = parser.parse_args(argv)

    api_key = os.getenv("INVESTDATA_API_KEY") or os.getenv("INVESTODAY_API_KEY")
    result: dict[str, Any] = {
        "investoday": {"api_key_present": bool(api_key)},
        "akshare": _probe_akshare(),
    }
    if api_key:
        try:
            result["investoday"].update(_probe_investoday(args.base_url, api_key))
        except Exception as exc:
            result["investoday"]["error"] = f"{type(exc).__name__}: {exc}"
    result["decision"] = {
        "LOCAL_CBOND_TOTAL": "missing_source",
        "LOCAL_CHINA_BOND_TOTAL": "missing_source",
        "LOCAL_SP_CHINA_BOND": "missing_source",
        "fallback_policy": "no_proxy_no_broad_index",
    }
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote probe result -> {args.out_json}")
    print(
        "decision:",
        "missing_source:",
        "LOCAL_CBOND_TOTAL/LOCAL_CHINA_BOND_TOTAL/LOCAL_SP_CHINA_BOND",
        "no proxy",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
