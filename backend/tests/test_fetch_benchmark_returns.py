import sqlite3

from scripts.fetch_benchmark_returns import (
    BenchmarkComponent,
    _fetch_or_reuse_component_returns,
    _compose_returns,
    _daily_return_from_annual,
    load_local_component_returns,
    parse_benchmark_components,
    resolve_benchmark,
    upsert_component_returns,
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


def test_parse_components_maps_hsi_to_local_hsi():
    components, audits = parse_benchmark_components(
        "沪深300指数收益率*50%+恒生指数收益率*20%+中证国债指数收益率*30%"
    )

    assert components is not None
    assert [c.benchmark_code for c in components] == ["000300", "HSI", "H11006"]
    assert components[1].secid == "local:HSI"
    assert any(
        audit.status == "resolved"
        and audit.component_code == "HSI"
        and audit.component_name == "恒生指数"
        for audit in audits
    )


def test_parse_components_maps_hsi_with_fx_suffix():
    components, _ = parse_benchmark_components(
        "沪深300指数收益率*80%+恒生指数收益率(使用估值汇率折算)*10%+中债综合指数收益率*10%"
    )
    assert components is not None
    assert components[1].benchmark_code == "HSI"
    assert components[1].secid == "local:HSI"


def test_parse_components_maps_csi_composite_bond_to_h11009():
    components, audits = parse_benchmark_components(
        "中证综合债指数收益率*80%+银行活期存款利率(税后)*20%"
    )

    assert components is not None
    assert components[0].benchmark_code == "H11009"
    assert components[0].benchmark_name == "中证综合债"
    assert any(
        audit.status == "resolved"
        and audit.component_code == "H11009"
        and audit.component_name == "中证综合债"
        for audit in audits
    )


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


def test_parse_maps_verified_hs300_financial_real_estate_index():
    components, audits = parse_benchmark_components(
        "80%×沪深300金融地产行业指数收益率+20%×上证国债指数收益率"
    )

    assert components is not None
    assert [component.benchmark_code for component in components] == ["000914", "000012"]
    assert [component.weight for component in components] == [0.8, 0.2]
    assert all(audit.status == "resolved" for audit in audits)


def test_parse_maps_verified_hs300_anzhong_strategy_index():
    components, audits = parse_benchmark_components(
        "沪深300安中动态策略指数收益率*95%+金融机构人民币活期存款基准利率(税后)*5%"
    )

    assert components is not None
    assert [component.benchmark_code for component in components] == ["H30124", "BANK_CURRENT"]
    assert [component.weight for component in components] == [0.95, 0.05]
    assert all(audit.status == "resolved" for audit in audits)


def test_parse_maps_verified_unresolved_equity_indexes():
    cases = [
        ("中证A500指数收益率*80%+中债-国债总全价(1-3年)指数收益率*20%", "000510"),
        ("上证高端装备60指数收益率*50%+中证综合债指数收益率*50%", "000097"),
        ("国证航天军工指数收益率*50%+中证综合债指数收益率*50%", "399368"),
        ("中证军工指数收益率×95%+银行活期存款利率(税后)×5%", "399967"),
    ]

    for text, expected_code in cases:
        components, audits = parse_benchmark_components(text)
        assert components is not None
        assert components[0].benchmark_code == expected_code
        assert audits[0].status == "resolved"


def test_parse_maps_fixed_annual_additive_component():
    components, audits = parse_benchmark_components(
        "沪深300指数收益率*95%+2.5%(指年收益率,评价时按期间折算)"
    )

    assert components is not None
    assert [component.benchmark_code for component in components] == ["000300", "FIXED_ANNUAL_RETURN"]
    assert [component.weight for component in components] == [0.95, 0.025]
    assert all(audit.status == "resolved" for audit in audits)


def test_compose_treats_fixed_annual_return_as_additive_rate():
    mapping = resolve_benchmark(
        "000172",
        "混合型-偏股",
        "该基金无跟踪标的",
        "沪深300指数收益率*95%+2.5%(指年收益率,评价时按期间折算)",
    )

    assert mapping is not None
    rows = _compose_returns(
        mapping,
        {
            "1.000300": [
                {"trade_date": "2026-01-02", "daily_return": 0.01},
                {"trade_date": "2026-01-03", "daily_return": -0.02},
            ]
        },
    )

    fixed_daily = _daily_return_from_annual(0.025)
    assert rows == [
        {"trade_date": "2026-01-02", "daily_return": 0.01 * 0.95 + fixed_daily},
        {"trade_date": "2026-01-03", "daily_return": -0.02 * 0.95 + fixed_daily},
    ]


def test_parse_keeps_plain_hs300_supported():
    components, audits = parse_benchmark_components(
        "沪深300指数收益率*80%+上证国债指数收益率*20%"
    )

    assert components is not None
    assert [component.benchmark_code for component in components] == ["000300", "000012"]
    assert [component.weight for component in components] == [0.8, 0.2]
    assert all(audit.status == "resolved" for audit in audits)


def test_upsert_component_returns_persists_rows_for_local_source(tmp_path):
    """upsert 必须把成分收益写回 benchmark_component_returns，让 local: 路径非易失。

    之前 fetch_benchmark_returns 合成后只写 benchmark_returns，不写
    benchmark_component_returns；一旦 source DB 被 copy-source 覆盖或
    其他脚本清空 component_returns，这只成分就再无重合成机会。
    修复后，upsert_component_returns 是单一落库入口。
    """
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE benchmark_component_returns (
                component_code TEXT, trade_date TEXT,
                daily_return REAL, source TEXT, fetched_at TEXT
            );
            """
        )

    rows = [
        {"trade_date": "2026-01-02", "daily_return": 0.0012},
        {"trade_date": "2026-01-03", "daily_return": -0.0007},
    ]
    with sqlite3.connect(db) as conn:
        upsert_component_returns(conn, "000300", rows, source="eastmoney:1.000300")

    with sqlite3.connect(db) as conn:
        stored = conn.execute(
            "SELECT trade_date, daily_return, source FROM benchmark_component_returns "
            "WHERE component_code='000300' ORDER BY trade_date"
        ).fetchall()

    assert stored == [
        ("2026-01-02", 0.0012, "eastmoney:1.000300"),
        ("2026-01-03", -0.0007, "eastmoney:1.000300"),
    ]


def test_upsert_component_returns_idempotent_on_trade_date(tmp_path):
    """同一 (component_code, trade_date) 二次写入覆盖为最新 source，不重复堆行。"""
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE benchmark_component_returns ("
            "component_code TEXT, trade_date TEXT, daily_return REAL, source TEXT, fetched_at TEXT);"
        )
        upsert_component_returns(
            conn,
            "000300",
            [{"trade_date": "2026-01-02", "daily_return": 0.001}],
            source="eastmoney:1.000300",
        )
        upsert_component_returns(
            conn,
            "000300",
            [{"trade_date": "2026-01-02", "daily_return": 0.0011}],
            source="eastmoney:1.000300_rev2",
        )
        conn.commit()

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT daily_return, source FROM benchmark_component_returns "
            "WHERE component_code='000300' AND trade_date='2026-01-02'"
        ).fetchall()
    assert rows == [(0.0011, "eastmoney:1.000300_rev2")]


def test_fetch_or_reuse_writes_to_component_returns_when_missing(tmp_path, monkeypatch):
    """当 component_returns 表里没有该成分时，fetch_or_reuse 必须把 fetch 结果落库。

    这样下次重跑（即使 fetch 网络抖动）也能从本地表读出历史日收益。
    """
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE benchmark_component_returns ("
            "component_code TEXT, trade_date TEXT, daily_return REAL, source TEXT, fetched_at TEXT);"
        )

    fetched = [
        {"trade_date": "2026-01-02", "daily_return": 0.0009},
        {"trade_date": "2026-01-03", "daily_return": 0.0011},
    ]
    monkeypatch.setattr(
        "scripts.fetch_benchmark_returns.fetch_component_returns",
        lambda secid, start_date, end_date: fetched,
    )

    component = BenchmarkComponent(
        benchmark_code="000300",
        secid="1.000300",
        benchmark_name="沪深300",
        weight=1.0,
        kind="index",
        source_text="沪深300",
    )
    with sqlite3.connect(db) as conn:
        rows = _fetch_or_reuse_component_returns(
            conn, component, "2026-01-02", "2026-01-03"
        )
        conn.commit()

    assert rows == fetched
    with sqlite3.connect(db) as conn:
        stored = conn.execute(
            "SELECT trade_date, daily_return, source FROM benchmark_component_returns "
            "WHERE component_code='000300' ORDER BY trade_date"
        ).fetchall()
    assert stored == [
        ("2026-01-02", 0.0009, "eastmoney:1.000300"),
        ("2026-01-03", 0.0011, "eastmoney:1.000300"),
    ]


def test_fetch_or_reuse_reuses_local_cache_without_network(tmp_path, monkeypatch):
    """当 component_returns 已有数据时，禁止再走网络 fetch（这是这次修复的核心保证）。"""
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE benchmark_component_returns ("
            "component_code TEXT, trade_date TEXT, daily_return REAL, source TEXT, fetched_at TEXT);"
        )
        conn.execute(
            "INSERT INTO benchmark_component_returns(component_code, trade_date, daily_return, source) "
            "VALUES (?, ?, ?, ?)",
            ("000300", "2026-01-02", 0.0005, "eastmoney:1.000300"),
        )
        conn.commit()

    def explode(*a, **k):
        raise AssertionError("network fetch should not be called when local cache is present")

    monkeypatch.setattr("scripts.fetch_benchmark_returns.fetch_component_returns", explode)

    component = BenchmarkComponent(
        benchmark_code="000300",
        secid="1.000300",
        benchmark_name="沪深300",
        weight=1.0,
        kind="index",
        source_text="沪深300",
    )
    with sqlite3.connect(db) as conn:
        rows = _fetch_or_reuse_component_returns(
            conn, component, "2026-01-02", "2026-01-03"
        )
    assert rows == [{"trade_date": "2026-01-02", "daily_return": 0.0005}]
