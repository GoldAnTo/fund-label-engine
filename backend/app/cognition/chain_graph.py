"""产业链图谱加载与查询"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from app.cognition.industry_db import IndustryDB


def _config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "cognition_chains.yaml"


def load_chains() -> dict[str, dict[str, Any]]:
    """加载产业链图谱配置"""
    with open(_config_path(), encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_chain(direction: str, chains: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """获取某个方向的产业链图谱"""
    if chains is None:
        chains = load_chains()
    return chains.get(direction)


def get_all_stock_keywords(chain: dict[str, Any]) -> list[str]:
    """获取产业链中所有环节的股票名称关键词（非excluded的环节）"""
    keywords: list[str] = []
    for link in chain.get("chain", []):
        if link.get("exclude"):
            continue
        keywords.extend(link.get("stocks", []))
    return keywords


def get_all_industry_keywords(chain: dict[str, Any]) -> list[str]:
    """获取产业链中所有环节的行业关键词"""
    keywords: list[str] = []
    for link in chain.get("chain", []):
        if link.get("exclude"):
            continue
        keywords.extend(link.get("industry_keywords", []))
    return keywords


def enrich_chain_with_industry_db(
    chain: dict[str, Any], industry_db: IndustryDB
) -> dict[str, Any]:
    """用行业数据库增强产业链环节的股票列表。

    遍历非 excluded 的环节，用 industry_keywords 查行业数据库，
    把查到的额外股票代码补充到 extra_stocks 字段（不修改原有 stocks 列表）。
    如果 industry_db 未加载或无数据，直接返回原 chain 不做修改。
    """
    if not industry_db.is_loaded():
        return chain

    for link in chain.get("chain", []):
        if link.get("exclude"):
            continue
        # 用行业关键词查找更多相关股票
        for ind_kw in link.get("industry_keywords", []):
            extra_stocks = industry_db.get_stocks_by_industry(ind_kw)
            existing = set(link.get("stocks", []))
            existing_codes = set(link.get("extra_stocks", []))
            for s in extra_stocks:
                if s not in existing and s not in existing_codes:
                    link.setdefault("extra_stocks", []).append(s)
                    existing_codes.add(s)
    return chain
