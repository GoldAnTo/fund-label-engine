import sqlite3

from scripts.fetch_benchmark_returns import (
    load_local_component_returns,
    parse_benchmark_components,
    resolve_benchmark,
)


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

    assert mapping is not None
    assert mapping.mapping_reason == "composite_benchmark_supported_components"
    assert mapping.benchmark_code == "000300:0.80+LOCAL_CBOND_COMPOSITE:0.20"


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
    assert mapping.components[0].benchmark_code == "BANK_FIXED_PLUS"


def test_parse_components_records_unresolved_bond_component():
    components, audits = parse_benchmark_components(
        "沪深300指数收益率*80%+中债综合指数收益率*20%"
    )

    assert components is not None
    assert any(component.benchmark_code == "LOCAL_CBOND_COMPOSITE" for component in components)
    assert any(audit.component_name == "中债综合" for audit in audits)
    assert all(audit.status == "resolved" for audit in audits)


def test_resolve_thematic_index_with_deposit_component():
    mapping = resolve_benchmark(
        "000005",
        "指数型-股票",
        "该基金无跟踪标的",
        "95%×中证医药100指数收益率+5%×活期存款利率(税后)",
    )

    assert mapping is not None
    assert mapping.benchmark_code == "000978:0.95+BANK_CURRENT:0.05"


def test_load_local_component_returns_from_benchmark_component_returns_table(tmp_path):
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE benchmark_component_returns ("
            "component_code TEXT, trade_date TEXT, daily_return REAL, source TEXT)"
        )
        conn.execute(
            "INSERT INTO benchmark_component_returns VALUES "
            "('LOCAL_CBOND_COMPOSITE', '2026-01-02', 0.0003, 'local_csi_bond')"
        )
        conn.execute(
            "INSERT INTO benchmark_component_returns VALUES "
            "('LOCAL_CBOND_COMPOSITE', '2026-01-03', 0.0004, 'local_csi_bond')"
        )

    rows = load_local_component_returns(db, "LOCAL_CBOND_COMPOSITE")

    assert rows == [
        {"trade_date": "2026-01-02", "daily_return": 0.0003},
        {"trade_date": "2026-01-03", "daily_return": 0.0004},
    ]


def test_load_local_component_returns_accepts_plain_sqlite_connection(tmp_path):
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE benchmark_component_returns ("
            "component_code TEXT, trade_date TEXT, daily_return REAL, source TEXT)"
        )
        conn.execute(
            "INSERT INTO benchmark_component_returns VALUES "
            "('LOCAL_CBOND_TOTAL', '2026-01-02', 0.0002, 'local_bond')"
        )

        rows = load_local_component_returns(conn, "LOCAL_CBOND_TOTAL")

    assert rows == [{"trade_date": "2026-01-02", "daily_return": 0.0002}]
