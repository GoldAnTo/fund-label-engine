from scripts.fetch_benchmark_returns import resolve_benchmark


def test_resolve_single_index_tracking_target():
    mapping = resolve_benchmark(
        "000176",
        "指数型-股票",
        "沪深300指数",
        "沪深300指数收益率*95%+银行活期存款利率(税后)*5%",
    )

    assert mapping is not None
    assert mapping.benchmark_code == "000300"
    assert mapping.benchmark_name == "沪深300"
    assert mapping.mapping_reason == "tracking_target_exact_supported_index"
    assert len(mapping.components) == 1
    assert mapping.components[0].weight == 1.0


def test_resolve_composite_benchmark_with_supported_components():
    mapping = resolve_benchmark(
        "000001",
        "混合型-偏股",
        "该基金无跟踪标的",
        "沪深300指数收益率*80%+上证国债指数收益率*20%",
    )

    assert mapping is not None
    assert mapping.mapping_reason == "composite_benchmark_supported_components"
    assert mapping.benchmark_code == "000300:0.80+000012:0.20"
    assert [component.weight for component in mapping.components] == [0.8, 0.2]


def test_unresolved_when_composite_contains_unsupported_bond_index():
    mapping = resolve_benchmark(
        "000002",
        "混合型-偏股",
        "该基金无跟踪标的",
        "沪深300指数收益率*80%+中债综合指数收益率*20%",
    )

    assert mapping is None


def test_resolve_current_deposit_component():
    mapping = resolve_benchmark(
        "000003",
        "指数型-股票",
        "中证500指数",
        "中证500指数收益率*95%+银行活期存款利率(税后)*5%",
    )

    assert mapping is not None
    assert mapping.mapping_reason == "tracking_target_exact_supported_index"


def test_resolve_fixed_deposit_rate_plus_spread():
    mapping = resolve_benchmark(
        "000004",
        "混合型-灵活",
        "该基金无跟踪标的",
        "1年期存款利率+3%(单利年化)",
    )

    assert mapping is not None
    assert mapping.mapping_reason == "composite_benchmark_supported_components"
    assert mapping.components[0].benchmark_code == "BANK_1Y_PLUS"
