from scripts.fetch_investoday_index_quotes import (
    ALLOWED_INDEXES,
    InvestodayDataError,
    build_csv_rows,
    validate_basic_info,
)


def test_build_csv_rows_uses_previous_close_and_sorts_dates():
    rows = build_csv_rows(
        "H11001",
        [
            {
                "date": "2025-06-27 00:00:00",
                "previousClosePrice": 101.0,
                "closePrice": 102.01,
            },
            {
                "date": "2025-06-26 00:00:00",
                "previousClosePrice": 100.0,
                "closePrice": 101.0,
            },
        ],
    )

    assert rows == [
        {
            "component_code": "H11001",
            "trade_date": "2025-06-26",
            "daily_return": "0.0100000000",
            "source": "investoday:index/quotes",
        },
        {
            "component_code": "H11001",
            "trade_date": "2025-06-27",
            "daily_return": "0.0100000000",
            "source": "investoday:index/quotes",
        },
    ]


def test_validate_basic_info_accepts_exact_expected_name():
    validate_basic_info(
        "H11009",
        [{"indexCode": "H11009", "indexName": "中证综合债", "indexNameFull": "中证综合债指数"}],
    )


def test_validate_basic_info_rejects_name_mismatch():
    try:
        validate_basic_info(
            "H11009",
            [{"indexCode": "H11009", "indexName": "中证企业债", "indexNameFull": "中证企业债指数"}],
        )
    except InvestodayDataError as exc:
        assert "does not match expected" in str(exc)
    else:
        raise AssertionError("expected InvestodayDataError")


def test_fetch_whitelist_is_intentionally_narrow():
    assert ALLOWED_INDEXES == {
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
