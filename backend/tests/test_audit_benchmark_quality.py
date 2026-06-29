from scripts.audit_benchmark_quality import classify_component, summarize_fund_quality


def test_classify_component_ready_when_resolved_and_has_returns():
    component = {
        "status": "resolved",
        "reason": "index",
        "component_code": "000300",
        "component_name": "沪深300",
    }

    assert classify_component(component, {"000300"}) == "ready"


def test_classify_component_missing_source_when_resolved_without_returns():
    component = {
        "status": "resolved",
        "reason": "index",
        "component_code": "H11001",
        "component_name": "中证全债",
    }

    assert classify_component(component, {"000300"}) == "missing_source"


def test_classify_component_mapping_required_for_exact_required_reason():
    component = {
        "status": "unresolved",
        "reason": "exact_component_mapping_required",
        "component_code": None,
        "component_name": "沪深300金融地产行业指数",
    }

    assert classify_component(component, {"000300"}) == "mapping_required"


def test_summarize_fund_quality_uses_worst_component_status():
    components = [
        {
            "status": "resolved",
            "reason": "index",
            "component_code": "000300",
            "component_name": "沪深300",
        },
        {
            "status": "resolved",
            "reason": "index",
            "component_code": "H11001",
            "component_name": "中证全债",
        },
    ]

    summary = summarize_fund_quality(components, {"000300"})

    assert summary["quality_status"] == "missing_source"
    assert summary["blocking_components"] == "H11001:中证全债"


def test_classify_component_ready_for_live_numeric_index_even_without_returns_set():
    # 复现 bug：000012(上证国债) 是可实时拉取的数字指数码，即使没单独出现在
    # benchmark_returns（那里存的是复合串 000300:0.80+000012:0.20），也应算有源。
    component = {
        "status": "resolved",
        "reason": "index",
        "component_code": "000012",
        "component_name": "上证国债",
        "secid": "1.000012",
    }

    assert classify_component(component, set()) == "ready"


def test_summarize_fund_quality_ready_when_composed_returns_exist():
    # 000017: 沪深300*80%+上证国债*20%，两组件 resolved 且已合成出 benchmark_returns，
    # 不应被误判成 missing_source。
    components = [
        {"status": "resolved", "reason": "index", "component_code": "000300", "component_name": "沪深300", "secid": "1.000300"},
        {"status": "resolved", "reason": "index", "component_code": "000012", "component_name": "上证国债", "secid": "1.000012"},
    ]

    summary = summarize_fund_quality(components, set(), has_composed_returns=True)

    assert summary["quality_status"] == "ready"
    assert summary["blocking_components"] == ""


def test_classify_component_ready_for_synthetic_rate_component():
    component = {
        "status": "resolved",
        "reason": "synthetic",
        "component_code": "BANK_CURRENT",
        "component_name": "银行活期存款利率",
        "secid": "synthetic:0.003500",
    }

    assert classify_component(component, set()) == "ready"

