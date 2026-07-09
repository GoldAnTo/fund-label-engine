"""产业链图谱加载与查询"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


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
