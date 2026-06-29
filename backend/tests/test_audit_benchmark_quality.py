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
