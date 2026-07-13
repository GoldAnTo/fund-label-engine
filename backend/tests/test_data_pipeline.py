import sqlite3
from pathlib import Path

import pytest
from app.batch import run_batch
from app.data_access import FundDataRepository, FundRepository

from scripts.seed_sample_db import seed


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    db = tmp_path / "fund.sqlite"
    seed(db)
    return db


@pytest.fixture()
def funddata_style_db(tmp_path: Path) -> Path:
    db = tmp_path / "funddata.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_profiles (
                fund_code TEXT PRIMARY KEY,
                fund_name TEXT,
                full_name TEXT,
                fund_type TEXT,
                issue_date TEXT,
                establishment_date TEXT,
                asset_size REAL,
                asset_size_date TEXT,
                fund_company TEXT,
                custodian TEXT,
                manager TEXT,
                benchmark TEXT,
                tracking_target TEXT,
                source TEXT,
                fetched_at TEXT NOT NULL
            );
            CREATE TABLE nav_history (
                fund_code TEXT NOT NULL,
                nav_date TEXT NOT NULL,
                unit_nav REAL,
                accumulated_nav REAL,
                daily_growth_rate REAL,
                subscribe_status TEXT,
                redeem_status TEXT,
                dividend TEXT,
                source TEXT,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (fund_code, nav_date)
            );
            CREATE TABLE stock_holdings (
                fund_code TEXT NOT NULL,
                report_period TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                net_value_ratio REAL,
                shares REAL,
                market_value REAL,
                source TEXT,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (fund_code, report_period, stock_code)
            );
            CREATE TABLE industry_allocations (
                fund_code TEXT NOT NULL,
                report_period TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                net_value_ratio REAL,
                source TEXT,
                fetched_at TEXT NOT NULL,
                market_value REAL,
                PRIMARY KEY (fund_code, report_period, industry_name)
            );
            CREATE TABLE fund_manager_links (
                fund_code TEXT NOT NULL,
                manager_name TEXT NOT NULL,
                company TEXT,
                current_funds TEXT,
                tenure_days INTEGER,
                current_aum REAL,
                best_return REAL,
                source TEXT,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (fund_code, manager_name, company)
            );
            CREATE TABLE fee_structures (
                fund_code TEXT NOT NULL,
                fee_type TEXT NOT NULL,
                condition_name TEXT NOT NULL,
                fee REAL,
                source TEXT,
                fetched_at TEXT NOT NULL,
                fee_text TEXT,
                discount_fee REAL,
                discount_fee_text TEXT,
                PRIMARY KEY (fund_code, fee_type, condition_name)
            );
            """
        )
        conn.executemany(
            "INSERT INTO fund_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "000001",
                    "真实样例混合",
                    "真实样例混合型证券投资基金",
                    "混合型-偏股",
                    "2015-01-01",
                    "2015-02-01",
                    26.44,
                    "2026-06-17",
                    "样例基金公司",
                    "样例托管行",
                    "张三",
                    "沪深300",
                    "",
                    "fundData",
                    "2026-06-17T00:00:00",
                ),
                (
                    "000003",
                    "真实样例债券",
                    "真实样例债券型证券投资基金",
                    "债券型-长债",
                    "2018-01-01",
                    "2018-02-01",
                    50.0,
                    "2026-06-17",
                    "样例基金公司",
                    "样例托管行",
                    "李四",
                    "",
                    "",
                    "fundData",
                    "2026-06-17T00:00:00",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("000001", "2026-06-10", 1.00, 1.00, 0.010, "", "", "", "fundData", "now"),
                ("000001", "2026-06-11", 0.98, 0.98, -0.020, "", "", "", "fundData", "now"),
                ("000001", "2026-06-12", 1.01, 1.01, 0.030, "", "", "", "fundData", "now"),
                ("000001", "2026-06-15", 1.02, 1.02, 0.010, "", "", "", "fundData", "now"),
                ("000001", "2026-06-16", 1.00, 1.00, -0.015, "", "", "", "fundData", "now"),
                ("000001", "2026-06-17", 1.02, 1.02, 0.020, "", "", "", "fundData", "now"),
            ],
        )
        conn.executemany(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("000001", "2025-12-31", "600001", "股票1", 0.11, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600002", "股票2", 0.09, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600003", "股票3", 0.08, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600004", "股票4", 0.07, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600005", "股票5", 0.06, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600006", "股票6", 0.05, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600007", "股票7", 0.04, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600008", "股票8", 0.04, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600009", "股票9", 0.035, None, None, "fundData", "now"),
                ("000001", "2025-12-31", "600010", "股票10", 0.035, None, None, "fundData", "now"),
            ],
        )
        conn.executemany(
            "INSERT INTO industry_allocations VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("000001", "2025-12-31", "电子", 0.42, "fundData", "now", None),
                ("000001", "2025-12-31", "食品饮料", 0.16, "fundData", "now", None),
                ("000001", "2025-12-31", "银行", 0.08, "fundData", "now", None),
            ],
        )
        conn.executemany(
            "INSERT INTO fund_manager_links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("000001", "张三", "样例基金公司", "", 3652, 20.0, 1.2, "fundData", "now"),
            ],
        )
        conn.executemany(
            "INSERT INTO fee_structures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("000001", "运作费用", "管理费率", 0.012, "fundData", "now", "1.20%（每年）", None, None),
                ("000001", "运作费用", "托管费率", 0.002, "fundData", "now", "0.20%（每年）", None, None),
                ("000001", "运作费用", "销售服务费率", 0.0, "fundData", "now", "0.00%（每年）", None, None),
            ],
        )
        conn.commit()
    return db


def test_repository_lists_only_supported_fund_types(seeded_db: Path) -> None:
    repo = FundRepository(seeded_db)

    codes = repo.list_supported_fund_codes()

    assert codes == ["000001", "000002", "000004", "000005", "000006", "000007", "000008"]


def test_repository_loads_fund_input_with_holdings_and_fees(seeded_db: Path) -> None:
    repo = FundRepository(seeded_db)

    fund = repo.load_fund_input("000001")

    assert fund is not None
    assert fund.fund_type == "股票型"
    assert len(fund.stock_holdings) == 10
    assert fund.stock_holdings[0]["weight"] == 0.11
    assert fund.manager_tenure_years == 6.2
    assert fund.management_fee == 0.010
    assert fund.custody_fee == 0.002
    assert fund.equity_position == 0.89
    assert len(fund.stock_factors) == 10  # 10 只持仓股票均有因子数据


def test_repository_loads_stock_factors_no_later_than_holding_report_date(
    seeded_db: Path,
) -> None:
    with sqlite3.connect(seeded_db) as conn:
        conn.executemany(
            "INSERT INTO stock_factors "
            "(stock_code, factor_date, pb, roe, dividend_yield, revenue_growth, "
            "profit_growth, market_cap_bucket, valuation_percentile, style) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("600519", "2026-03-30", 8.1, 0.24, 0.025, 0.08, 0.12, "large", 0.72, "quality"),
                ("600519", "2026-04-30", 9.9, 0.18, 0.015, 0.02, 0.03, "large", 0.91, "future"),
            ],
        )
        conn.commit()

    fund = FundRepository(seeded_db).load_fund_input("000001")

    assert fund is not None
    assert fund.holding_report_date == "2026-03-31"
    # seed 数据中 600519 的 factor_date 为 "2026-03-31"，比测试插入的 "2026-03-30" 更晚
    # 但不晚于 report_date "2026-03-31"，所以应取 "2026-03-31"（seed 数据）
    # 而 "2026-04-30" 晚于 report_date，不应被加载
    factor_600519 = next(
        f for f in fund.stock_factors if f["stock_code"] == "600519"
    )
    assert factor_600519["factor_date"] == "2026-03-31"
    # 确认 "2026-04-30" 的数据未被加载
    assert all(f["factor_date"] != "2026-04-30" for f in fund.stock_factors)


def test_repository_returns_none_for_unknown_fund(seeded_db: Path) -> None:
    repo = FundRepository(seeded_db)

    assert repo.load_fund_input("999999") is None


def test_batch_persists_run_results_and_evidence(seeded_db: Path) -> None:
    run_id, processed = run_batch(seeded_db)

    assert processed == 7  # 7 只支持类型的基金：000001, 000002, 000004-000008

    with sqlite3.connect(seeded_db) as conn:
        conn.row_factory = sqlite3.Row
        run_row = conn.execute(
            "SELECT status, rule_version FROM label_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert run_row["status"] == "succeeded"
        assert run_row["rule_version"] == "v1"

        labels_000001 = {
            row["label_code"]
            for row in conn.execute(
                "SELECT label_code FROM fund_label_results "
                "WHERE run_id = ? AND fund_code = ?",
                (run_id, "000001"),
            ).fetchall()
        }
        assert "data_sufficient" in labels_000001
        assert "holding_concentration_high" in labels_000001
        assert "manager_tenure_long" in labels_000001
        assert "fee_low" in labels_000001
        assert "style_exposure_observe" in labels_000001

        labels_000002 = {
            row["label_code"]
            for row in conn.execute(
                "SELECT label_code FROM fund_label_results "
                "WHERE run_id = ? AND fund_code = ?",
                (run_id, "000002"),
            ).fetchall()
        }
        assert "data_insufficient" in labels_000002
        assert "manual_review_required" in labels_000002
        assert "manager_tenure_long" not in labels_000002

        definitions = {
            row["label_code"]: row["rule_version"]
            for row in conn.execute(
                "SELECT label_code, rule_version FROM label_definitions"
            ).fetchall()
        }
        assert definitions["data_sufficient"] == "v1"
        assert definitions["holding_concentration_high"] == "v1"

        evidence_count = conn.execute(
            "SELECT COUNT(*) AS c FROM fund_label_evidence WHERE run_id = ?",
            (run_id,),
        ).fetchone()["c"]
        assert evidence_count > 0

        coverage_rows = conn.execute(
            "SELECT field, present FROM fund_run_coverage "
            "WHERE run_id = ? AND fund_code = ?",
            (run_id, "000001"),
        ).fetchall()
        assert {row["field"] for row in coverage_rows}.issuperset(
            {
                "supported_fund_type",
                "nav_returns",
                "stock_holdings",
                "industry_allocations",
                "manager_tenure_years",
                "fee_structure",
                "fund_size",
                "equity_position",
            }
        )


def test_review_records_are_persisted_and_queryable(seeded_db: Path) -> None:
    run_id, _ = run_batch(seeded_db)

    from app.persistence import LabelRunReader, LabelRunWriter

    writer = LabelRunWriter(seeded_db)
    review_id = writer.write_review(
        run_id=run_id,
        fund_code="000001",
        label_code="holding_concentration_high",
        decision="confirm",
        reviewer="researcher-a",
        comment="证据充分，确认标签。",
    )

    reviews = LabelRunReader(seeded_db).list_reviews(run_id, "000001")

    assert reviews == [
        {
            "review_id": review_id,
            "run_id": run_id,
            "fund_code": "000001",
            "label_code": "holding_concentration_high",
            "decision": "confirm",
            "reviewer": "researcher-a",
            "comment": "证据充分，确认标签。",
        }
    ]


def test_funddata_repository_maps_real_schema_to_engine_input(
    funddata_style_db: Path,
) -> None:
    repo = FundDataRepository(funddata_style_db)

    assert repo.list_supported_fund_codes() == ["000001"]
    fund = repo.load_fund_input("000001")

    assert fund is not None
    assert fund.fund_name == "真实样例混合"
    assert fund.fund_size == 26.44
    assert fund.nav_returns == [0.010, -0.020, 0.030, 0.010, -0.015, 0.020]
    assert fund.stock_holdings[0]["stock_code"] == "600001"
    assert fund.stock_holdings[0]["weight"] == 0.11
    assert fund.industry_allocations[0] == {"industry": "电子", "weight": 0.42}
    assert fund.manager_tenure_years == pytest.approx(10.0, abs=0.01)
    assert fund.management_fee == 0.012
    assert fund.custody_fee == 0.002
    assert fund.sales_service_fee == 0.0
    assert fund.equity_position == pytest.approx(0.61)
    assert fund.holding_report_date == "2025-12-31"
    assert fund.industry_report_date == "2025-12-31"
    assert fund.stock_factors == []


def test_funddata_repository_treats_no_fee_placeholder_as_missing_fee_data(
    funddata_style_db: Path,
) -> None:
    with sqlite3.connect(funddata_style_db) as conn:
        conn.execute("DELETE FROM fee_structures WHERE fund_code = '000001'")
        conn.execute(
            "INSERT INTO fee_structures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "000001",
                "运作费用",
                "场内ETF-无费率信息",
                None,
                "fundData",
                "now",
                None,
                None,
                None,
            ),
        )
        conn.commit()

    fund = FundDataRepository(funddata_style_db).load_fund_input("000001")

    assert fund is not None
    assert fund.management_fee is None
    assert fund.custody_fee is None
    assert fund.sales_service_fee is None

    run_id, _ = run_batch(funddata_style_db, source="funddata")
    with sqlite3.connect(funddata_style_db) as conn:
        conn.row_factory = sqlite3.Row
        labels = {
            row["label_code"]
            for row in conn.execute(
                "SELECT label_code FROM fund_label_results "
                "WHERE run_id = ? AND fund_code = '000001'",
                (run_id,),
            ).fetchall()
        }
        fee_low_state = conn.execute(
            "SELECT state, reason_code FROM label_calculation_states "
            "WHERE run_id = ? AND fund_code = '000001' AND label_code = 'fee_low'",
            (run_id,),
        ).fetchone()

    assert "fee_low" not in labels
    assert fee_low_state["state"] == "not_computed"
    assert fee_low_state["reason_code"] == "fee_structure_missing"


def test_batch_accepts_funddata_source_and_persists_full_feature_set(
    funddata_style_db: Path,
) -> None:
    run_id, processed = run_batch(funddata_style_db, source="funddata")

    assert processed == 1

    from app.persistence import LabelRunReader

    payload = LabelRunReader(funddata_style_db).get_fund_report(run_id, "000001")
    assert payload is not None
    feature_codes = {item["feature_code"] for item in payload["features"]}
    # 不足 180 个交易日，1Y/3Y 窗口产不出，但 full 窗口必有
    assert {
        "annualized_return_full",
        "annualized_volatility_full",
        "max_drawdown_full",
        "sharpe_ratio_full",
        "top_10_holding_weight",
        "industry_top1_weight",
        "industry_top3_weight",
        "equity_position",
        "manager_tenure_years",
        "total_annual_fee",
    }.issubset(feature_codes)
    label_codes = {item["label_code"] for item in payload["labels"]}
    assert "data_sufficient" in label_codes
    assert "holding_concentration_high" in label_codes
    assert "industry_concentration_high" not in label_codes
    assert "style_unlabeled_stock_factors_missing" in label_codes
    assert payload["missing_fields"] == []
    assert payload["summary"]["feature_count"] >= 10


def test_single_fund_failure_does_not_abort_batch(
    seeded_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """模拟一只基金在 evaluate 时抛错，整批不中断。"""
    from app.label_engine.engine import LabelEngine
    from app.persistence import LabelRunReader

    original_evaluate = LabelEngine.evaluate

    def evaluate_with_failure(self, fund):
        if fund.fund_code == "000001":
            raise RuntimeError("synthetic failure for testing")
        return original_evaluate(self, fund)

    monkeypatch.setattr(LabelEngine, "evaluate", evaluate_with_failure)

    run_id, processed = run_batch(seeded_db)

    # 000001 失败，其余 6 只仍被处理
    assert processed == 6

    reader = LabelRunReader(seeded_db)
    run = reader.get_run(run_id)
    assert run["status"] == "completed_with_errors"
    assert run["failure_count"] == 1
    failures = reader.list_failures(run_id)
    assert len(failures) == 1
    assert failures[0]["fund_code"] == "000001"
    assert failures[0]["stage"] == "evaluate"
    assert failures[0]["error_type"] == "RuntimeError"
    assert "synthetic failure" in failures[0]["message"]


def test_rule_snapshot_is_persisted_with_run(seeded_db: Path) -> None:
    from app.label_engine.engine import RuleConfig
    from app.persistence import LabelRunReader

    custom = RuleConfig(holding_concentration_threshold=0.99)
    run_id, _ = run_batch(seeded_db, rule_config=custom)

    run = LabelRunReader(seeded_db).get_run(run_id)
    assert run["rule_snapshot"]["holding_concentration_threshold"] == 0.99
