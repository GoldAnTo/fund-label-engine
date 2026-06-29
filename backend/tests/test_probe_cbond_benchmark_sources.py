"""CBOND_TOTAL / CHINA_BOND_TOTAL / SP_CHINA_BOND benchmark 源探针单测。

锁定"未找到可靠源"的当前结论，避免后续被误改成代理。
"""
from scripts.probe_cbond_benchmark_sources import _probe_akshare


def test_probe_akshare_has_no_broad_total_proxy_category():
    """akshare 中债登接口没有可作"中债总/中国债券总"代理的宽分类。

    已有 '国债总指数' 是真源（LOCAL_CBOND_GOV_TOTAL），不在代理名单内。
    """
    report = _probe_akshare()
    assert report.get("akshare_available") is True
    forbidden_exact = {
        "中债总指数",
        "债券总指数",
        "中债-总指数",
        "中债总指数(总值)",
    }
    categories = set(report.get("categories", []))
    leak = categories & forbidden_exact
    assert not leak, f"broad total category leaked: {leak}"
    assert "总指数" not in categories
    assert "国债总指数" in categories  # 真源已存在，但不允许再代理


def test_search_queries_cover_required_targets():
    """锁定关键搜索词，避免后续漏查。"""
    from scripts.probe_cbond_benchmark_sources import SEARCH_QUERIES

    assert "中债总" in SEARCH_QUERIES
    assert "中国债券总" in SEARCH_QUERIES
    assert "标普中国债券" in SEARCH_QUERIES
