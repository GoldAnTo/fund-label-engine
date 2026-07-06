"""Phase 5 股票因子接入测试：窄表优先 + 宽表 fallback。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.batch import run_batch
from app.data_access import FundDataRepository, FundRepository
from app.data_access.stock_factors import load_stock_factors
from app.persistence import LabelRunReader


def _make_db_with_holdings(tmp_path: Path) -> Path:
    """造一个最小化的 fundData 风格库，含 1 只基金 + 2 只持仓股票。"""
    db = tmp_path / "phase5.sqlite"
    sql = """
    CREATE TABLE fund_profiles (
        fund_code TEXT PRIMARY KEY,
        fund_name TEXT,
        fund_type TEXT,
        asset_size REAL
    );
    CREATE TABLE nav_history (
        fund_code TEXT, nav_date TEXT, daily_growth_rate REAL,
        PRIMARY KEY (fund_code, nav_date)
    );
    CREATE TABLE stock_holdings (
        fund_code TEXT, stock_code TEXT, stock_name TEXT,
        report_period TEXT, net_value_ratio REAL
    );
    CREATE TABLE industry_allocations (
        fund_code TEXT, industry_name TEXT, report_period TEXT, net_value_ratio REAL
    );
    CREATE TABLE fund_manager_links (
        fund_code TEXT, manager_id TEXT, tenure_days INTEGER
    );
    CREATE TABLE fee_structures (
        fund_code TEXT, fee_type TEXT, condition_name TEXT, fee REAL
    );
    INSERT INTO fund_profiles VALUES ('000001','测试基金','股票型',12.0);
    INSERT INTO stock_holdings VALUES
        ('000001','600519','贵州茅台','2025-12-31',0.40),
        ('000001','601398','工商银行','2025-12-31',0.30);
    INSERT INTO industry_allocations VALUES
        ('000001','食品饮料','2025-12-31',0.60);
    INSERT INTO fund_manager_links VALUES ('000001','M1', 2200);
    INSERT INTO fee_structures VALUES
        ('000001','运作费用','管理费率',0.012),
        ('000001','运作费用','托管费率',0.002),
        ('000001','运作费用','销售服务费率',0.0);
    """
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    # 几天的 NAV，避免数据不足
    for i in range(30):
        conn.execute(
            "INSERT INTO nav_history VALUES (?,?,?)",
            ("000001", f"2025-12-{i+1:02d}", 0.0005),
        )
    conn.commit()
    conn.close()
    return db


def _add_narrow_factors(db: Path) -> None:
    sql = """
    CREATE TABLE stock_factor_values (
        stock_code TEXT, factor_code TEXT, factor_value REAL,
        as_of_date TEXT, source TEXT,
        PRIMARY KEY (stock_code, factor_code, as_of_date)
    );
    INSERT INTO stock_factor_values VALUES
        ('600519','pb',1.0,'2025-12-31','fundamentals'),
        ('600519','valuation_percentile',0.10,'2025-12-31','fundamentals'),
        ('600519','roe',0.20,'2025-12-31','fundamentals'),
        ('600519','revenue_growth',0.18,'2025-12-31','fundamentals'),
        ('600519','dividend_yield',0.04,'2025-12-31','fundamentals'),
        ('601398','pb',0.8,'2025-12-31','fundamentals'),
        ('601398','valuation_percentile',0.15,'2025-12-31','fundamentals'),
        ('601398','roe',0.16,'2025-12-31','fundamentals'),
        ('601398','revenue_growth',0.16,'2025-12-31','fundamentals'),
        ('601398','dividend_yield',0.05,'2025-12-31','fundamentals');
    """
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    conn.commit()
    conn.close()


def _add_wide_factors(db: Path) -> None:
    sql = """
    CREATE TABLE stock_factors (
        stock_code TEXT, factor_date TEXT, pb REAL, roe REAL,
        dividend_yield REAL, revenue_growth REAL, profit_growth REAL,
        market_cap_bucket TEXT, valuation_percentile REAL, style TEXT,
        PRIMARY KEY (stock_code, factor_date)
    );
    INSERT INTO stock_factors VALUES
        ('600519','2025-12-31',1.0,0.20,0.04,0.18,0.20,'large',0.10,'value'),
        ('601398','2025-12-31',0.8,0.16,0.05,0.16,0.10,'large',0.15,'value');
    """
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    conn.commit()
    conn.close()


def test_funddata_repository_loads_attached_stock_industry_map(tmp_path: Path) -> None:
    source_db = tmp_path / "source.sqlite"
    factor_db = tmp_path / "factor.sqlite"
    sqlite3.connect(source_db).close()
    with sqlite3.connect(factor_db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.execute(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            ("601398", "801780", "银行", "financial", "fixture", "2026-06-30"),
        )

    repo = FundDataRepository(source_db, factor_db_path=factor_db)
    rows = repo.load_stock_industry_map(["601398"], None)

    assert rows["601398"]["sector_group"] == "financial"


def test_load_stock_factors_returns_empty_when_neither_table_exists(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    sqlite3.connect(db).close()  # 建空库
    with sqlite3.connect(db) as conn:
        rows = load_stock_factors(conn, ["600519"], "2025-12-31")
    assert rows == []


def test_load_stock_factors_prefers_narrow_table(tmp_path: Path) -> None:
    db = _make_db_with_holdings(tmp_path)
    _add_narrow_factors(db)
    # 同时也插入宽表，但内容不同（pb=99 用来证明没被使用）
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE stock_factors (stock_code TEXT, factor_date TEXT, pb REAL,"
            " roe REAL, dividend_yield REAL, revenue_growth REAL, profit_growth REAL,"
            " market_cap_bucket TEXT, valuation_percentile REAL, style TEXT,"
            " PRIMARY KEY (stock_code, factor_date));"
            "INSERT INTO stock_factors VALUES "
            "('600519','2025-12-31',99,0,0,0,0,'large',1.0,'x');"
        )
        rows = load_stock_factors(conn, ["600519", "601398"], "2025-12-31")
    by_code = {r["stock_code"]: r for r in rows}
    # 走的是窄表，所以 pb=1.0 而不是 99
    assert by_code["600519"]["pb"] == 1.0
    assert by_code["600519"]["roe"] == 0.20


def test_load_stock_factors_falls_back_to_wide_when_narrow_missing(
    tmp_path: Path,
) -> None:
    db = _make_db_with_holdings(tmp_path)
    _add_wide_factors(db)  # 只装宽表
    with sqlite3.connect(db) as conn:
        rows = load_stock_factors(conn, ["600519", "601398"], "2025-12-31")
    by_code = {r["stock_code"]: r for r in rows}
    assert by_code["600519"]["pb"] == 1.0
    assert by_code["601398"]["pb"] == 0.8


def test_repository_loads_multi_period_factor_exposures(tmp_path: Path) -> None:
    db = tmp_path / "exposures.sqlite"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE fund_factor_exposures (
                fund_code TEXT,
                report_date TEXT,
                factor_code TEXT,
                exposure_value REAL,
                coverage_weight REAL,
                holding_total_weight REAL,
                stock_count INTEGER,
                covered_stock_count INTEGER,
                source TEXT,
                as_of_date TEXT,
                computed_at TEXT
            );
            INSERT INTO fund_factor_exposures VALUES
                ('000001','2025-03-31','deep_value_weight',0.62,0.85,0.70,2,2,'test','2025-03-31','now'),
                ('000001','2025-06-30','quality_growth_weight',0.58,0.86,0.70,2,2,'test','2025-06-30','now');
            """
        )

        rows = FundRepository._load_factor_exposures(conn, "000001", None)

    assert {row["report_date"] for row in rows} == {"2025-03-31", "2025-06-30"}


def test_funddata_repository_emits_style_labels_when_narrow_factors_provided(
    tmp_path: Path,
) -> None:
    """端到端：funddata schema + 窄表股票因子 → deep_value / quality_growth / dividend_steady 同时出。"""
    db = _make_db_with_holdings(tmp_path)
    _add_narrow_factors(db)

    run_id, processed = run_batch(db, source="funddata")
    assert processed == 1

    report = LabelRunReader(db).get_fund_report(run_id, "000001")
    assert report is not None
    label_codes = {item["label_code"] for item in report["labels"]}
    # 两只股票 weight=0.4 + 0.3 = 0.7 同时满足三类阈值
    assert "deep_value" in label_codes
    assert "quality_growth" in label_codes
    assert "dividend_steady" in label_codes
    assert "style_unlabeled_stock_factors_missing" not in label_codes


def test_run_batch_persists_equity_style_contributions(tmp_path: Path) -> None:
    """端到端：跑标签时同步写入股票级风格贡献明细。"""
    db = _make_db_with_holdings(tmp_path)
    _add_narrow_factors(db)

    run_id, processed = run_batch(db, source="funddata")
    assert processed == 1

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT stock_code, style_code, contribution_weight "
            "FROM fund_equity_style_contributions "
            "WHERE fund_code='000001' AND matched=1 "
            "ORDER BY stock_code, style_code"
        ).fetchall()

    pairs = {(r["stock_code"], r["style_code"]) for r in rows}
    # 600519 命中三类，601398 命中三类（按测试因子数据）
    assert ("600519", "deep_value") in pairs
    assert ("601398", "dividend_steady") in pairs
    assert all(r["contribution_weight"] > 0 for r in rows)


def test_run_batch_persists_dividend_sector_mix_exposures(tmp_path: Path) -> None:
    db = _make_db_with_holdings(tmp_path)
    _add_narrow_factors(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.executemany(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("600519", "801120", "食品饮料", "consumer", "fixture", "2025-12-31"),
                ("601398", "801780", "银行", "financial", "fixture", "2025-12-31"),
            ],
        )

    run_id, processed = run_batch(db, source="funddata")
    assert processed == 1

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT factor_code, exposure_value, coverage_weight "
            "FROM fund_factor_exposures "
            "WHERE factor_code LIKE 'dividend_sector_%' "
            "ORDER BY factor_code"
        ).fetchall()

    assert run_id
    assert {row[0] for row in rows} == {
        "dividend_sector_consumer_ratio",
        "dividend_sector_coverage",
        "dividend_sector_energy_utility_ratio",
        "dividend_sector_financial_ratio",
    }


def test_run_batch_dividend_split_gate_maps_to_dividend_steady_contributions(
    tmp_path: Path,
) -> None:
    """Gate：分红风格拆分标签需能映射回 dividend_steady 贡献行（单库 + stock_industry_map）。"""
    db = _make_db_with_holdings(tmp_path)
    _add_narrow_factors(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.executemany(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("600519", "801120", "食品饮料", "consumer", "fixture", "2025-12-31"),
                ("601398", "801780", "银行", "financial", "fixture", "2025-12-31"),
            ],
        )

    run_id, processed = run_batch(db, source="funddata")
    assert processed == 1

    with sqlite3.connect(db) as conn:
        missing = conn.execute(
            """
            WITH style_labels AS (
              SELECT fund_code, label_code FROM fund_label_results
              WHERE run_id = ?
                AND label_code IN ('dividend_steady', 'high_dividend_financial', 'consumer_quality')
            ),
            contribs AS (
              SELECT fund_code, COUNT(*) AS n FROM fund_equity_style_contributions
              WHERE matched=1 AND style_code='dividend_steady'
              GROUP BY fund_code
            )
            SELECT COUNT(*) FROM style_labels l
            LEFT JOIN contribs c ON c.fund_code=l.fund_code
            WHERE COALESCE(c.n, 0)=0
            """,
            (run_id,),
        ).fetchone()[0]

    assert missing == 0


def _make_multi_period_db(tmp_path: Path) -> Path:
    """两只基金股票 V(纯价值) / G(纯成长)，两期持仓权重反转 → 主导风格漂移。

    - 2025-06-30: V 权重 0.70, G 权重 0.10 → 主导 deep_value
    - 2025-12-31: V 权重 0.10, G 权重 0.70 → 主导 quality_growth
    两期 coverage_weight 均为 0.80（≥ formal 阈值 0.70），可进入稳定性评估。
    """
    db = tmp_path / "style-history.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE fund_profiles (fund_code TEXT PRIMARY KEY, fund_name TEXT, fund_type TEXT, asset_size REAL);
        CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL,
            PRIMARY KEY (fund_code, nav_date));
        CREATE TABLE stock_holdings (fund_code TEXT, stock_code TEXT, stock_name TEXT,
            report_period TEXT, net_value_ratio REAL);
        CREATE TABLE industry_allocations (fund_code TEXT, industry_name TEXT,
            report_period TEXT, net_value_ratio REAL);
        CREATE TABLE fund_manager_links (fund_code TEXT, manager_id TEXT, tenure_days INTEGER);
        CREATE TABLE fee_structures (fund_code TEXT, fee_type TEXT, condition_name TEXT, fee REAL);
        CREATE TABLE stock_factor_values (stock_code TEXT, factor_code TEXT, factor_value REAL,
            as_of_date TEXT, source TEXT, PRIMARY KEY (stock_code, factor_code, as_of_date));
        INSERT INTO fund_profiles VALUES ('000001','风格漂移样例','股票型',12.0);
        INSERT INTO stock_holdings VALUES
            ('000001','600001','纯价值','2025-06-30',0.70),
            ('000001','600002','纯成长','2025-06-30',0.10),
            ('000001','600001','纯价值','2025-12-31',0.10),
            ('000001','600002','纯成长','2025-12-31',0.70);
        INSERT INTO industry_allocations VALUES ('000001','综合','2025-12-31',0.80);
        INSERT INTO fund_manager_links VALUES ('000001','M1', 2200);
        INSERT INTO fee_structures VALUES
            ('000001','运作费用','管理费率',0.012),
            ('000001','运作费用','托管费率',0.002),
            ('000001','运作费用','销售服务费率',0.0);
        -- 纯价值股：低 pb / 低估值分位 / 低 roe / 低成长 / 高股息
        INSERT INTO stock_factor_values VALUES
            ('600001','pb',0.8,'2025-12-31','fundamentals'),
            ('600001','valuation_percentile',0.10,'2025-12-31','fundamentals'),
            ('600001','roe',0.05,'2025-12-31','fundamentals'),
            ('600001','revenue_growth',0.02,'2025-12-31','fundamentals'),
            ('600001','dividend_yield',0.06,'2025-12-31','fundamentals'),
            ('600002','pb',5.0,'2025-12-31','fundamentals'),
            ('600002','valuation_percentile',0.90,'2025-12-31','fundamentals'),
            ('600002','roe',0.25,'2025-12-31','fundamentals'),
            ('600002','revenue_growth',0.30,'2025-12-31','fundamentals'),
            ('600002','dividend_yield',0.005,'2025-12-31','fundamentals');
        """
    )
    for i in range(30):
        conn.execute(
            "INSERT INTO nav_history VALUES (?,?,?)",
            ("000001", f"2025-12-{i+1:02d}", 0.0005),
        )
    conn.commit()
    conn.close()
    return db


def test_list_recent_holding_periods_returns_descending(tmp_path: Path) -> None:
    db = _make_multi_period_db(tmp_path)
    repo = FundDataRepository(db)
    assert repo.list_recent_holding_periods("000001", 5) == ["2025-12-31", "2025-06-30"]
    assert repo.list_recent_holding_periods("000001", 1) == ["2025-12-31"]
    assert repo.list_recent_holding_periods("000001", 0) == []


def test_load_holdings_for_period_returns_period_specific_weights(tmp_path: Path) -> None:
    db = _make_multi_period_db(tmp_path)
    repo = FundDataRepository(db)
    by_code = {h["stock_code"]: h["weight"] for h in repo.load_holdings_for_period("000001", "2025-06-30")}
    assert by_code == {"600001": 0.70, "600002": 0.10}
    by_code = {h["stock_code"]: h["weight"] for h in repo.load_holdings_for_period("000001", "2025-12-31")}
    assert by_code == {"600001": 0.10, "600002": 0.70}


def test_run_batch_style_history_periods_persists_multi_period_exposures(
    tmp_path: Path,
) -> None:
    db = _make_multi_period_db(tmp_path)
    run_id, processed = run_batch(db, source="funddata", style_history_periods=2)
    assert processed == 1

    with sqlite3.connect(db) as conn:
        periods = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT report_date FROM fund_factor_exposures WHERE fund_code='000001'"
            )
        }
    assert periods == {"2025-06-30", "2025-12-31"}


def _make_latest_period_uncovered_db(tmp_path: Path) -> Path:
    """最新持仓期不命中深度价值，主导风格标签来自历史期。

    - 2025-12-31（最新）: 持仓 600099（高 pb/高估值，不命中 deep_value）
    - 2025-06-30（历史）: 持仓 600001（低 pb/低估值，命中 deep_value，权重 0.70）
    主导风格标签来自历史期，贡献明细必须覆盖历史期，否则与标签对不上。
    """
    db = tmp_path / "latest-uncovered.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE fund_profiles (fund_code TEXT PRIMARY KEY, fund_name TEXT, fund_type TEXT, asset_size REAL);
        CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL,
            PRIMARY KEY (fund_code, nav_date));
        CREATE TABLE stock_holdings (fund_code TEXT, stock_code TEXT, stock_name TEXT,
            report_period TEXT, net_value_ratio REAL);
        CREATE TABLE industry_allocations (fund_code TEXT, industry_name TEXT,
            report_period TEXT, net_value_ratio REAL);
        CREATE TABLE fund_manager_links (fund_code TEXT, manager_id TEXT, tenure_days INTEGER);
        CREATE TABLE fee_structures (fund_code TEXT, fee_type TEXT, condition_name TEXT, fee REAL);
        CREATE TABLE stock_factor_values (stock_code TEXT, factor_code TEXT, factor_value REAL,
            as_of_date TEXT, source TEXT, PRIMARY KEY (stock_code, factor_code, as_of_date));
        INSERT INTO fund_profiles VALUES ('000001','最新期不命中样例','股票型',12.0);
        INSERT INTO stock_holdings VALUES
            ('000001','600001','深度价值股','2025-06-30',0.70),
            ('000001','600099','高估值成长股','2025-12-31',0.70);
        INSERT INTO industry_allocations VALUES ('000001','综合','2025-12-31',0.80);
        INSERT INTO fund_manager_links VALUES ('000001','M1', 2200);
        INSERT INTO fee_structures VALUES
            ('000001','运作费用','管理费率',0.012),
            ('000001','运作费用','托管费率',0.002),
            ('000001','运作费用','销售服务费率',0.0);
        -- 历史期 600001 命中 deep_value；最新期 600099 有因子但高 pb/高估值不命中
        INSERT INTO stock_factor_values VALUES
            ('600001','pb',0.8,'2025-12-31','fundamentals'),
            ('600001','valuation_percentile',0.10,'2025-12-31','fundamentals'),
            ('600001','roe',0.05,'2025-12-31','fundamentals'),
            ('600001','revenue_growth',0.02,'2025-12-31','fundamentals'),
            ('600001','dividend_yield',0.06,'2025-12-31','fundamentals'),
            ('600099','pb',6.0,'2025-12-31','fundamentals'),
            ('600099','valuation_percentile',0.95,'2025-12-31','fundamentals'),
            ('600099','roe',0.10,'2025-12-31','fundamentals'),
            ('600099','revenue_growth',0.05,'2025-12-31','fundamentals'),
            ('600099','dividend_yield',0.005,'2025-12-31','fundamentals');
        """
    )
    for i in range(30):
        conn.execute(
            "INSERT INTO nav_history VALUES (?,?,?)",
            ("000001", f"2025-12-{i+1:02d}", 0.0005),
        )
    conn.commit()
    conn.close()
    return db


def test_run_batch_contributions_cover_historical_period_when_latest_uncovered(
    tmp_path: Path,
) -> None:
    """多期模式下，贡献明细必须与因子暴露同口径覆盖所有期次（含历史期）。"""
    db = _make_latest_period_uncovered_db(tmp_path)
    run_id, processed = run_batch(db, source="funddata", style_history_periods=2)
    assert processed == 1

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        # 因子暴露覆盖了哪些期次
        exposure_periods = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT report_date FROM fund_factor_exposures "
                "WHERE fund_code='000001'"
            )
        }
        # 历史期 deep_value 命中股票 600001 必须出现在贡献明细里
        rows = conn.execute(
            "SELECT report_date, stock_code, style_code, contribution_weight "
            "FROM fund_equity_style_contributions "
            "WHERE fund_code='000001' AND style_code='deep_value' AND matched=1"
        ).fetchall()

    # 修复前：贡献明细只用最新期 2025-12-31，历史期 deep_value 命中丢失（rows 为空）
    assert rows, "deep_value 命中应被记录到贡献明细（修复前会丢失历史期）"
    contrib_periods = {r["report_date"] for r in rows}
    assert "2025-06-30" in contrib_periods
    assert "2025-06-30" in exposure_periods
    assert {r["stock_code"] for r in rows} == {"600001"}


def test_run_batch_style_history_periods_emits_style_drift(tmp_path: Path) -> None:
    """两期主导风格 deep_value → quality_growth，应触发 style_drift（observe）。"""
    db = _make_multi_period_db(tmp_path)
    run_id, _ = run_batch(db, source="funddata", style_history_periods=2)

    report = LabelRunReader(db).get_fund_report(run_id, "000001")
    assert report is not None
    label_codes = {item["label_code"] for item in report["labels"]}
    assert "style_drift" in label_codes
    assert "style_stable" not in label_codes


def test_run_batch_single_period_does_not_emit_style_stability(tmp_path: Path) -> None:
    """默认 style_history_periods=1：只算一期，风格稳定性标签不应触发。"""
    db = _make_multi_period_db(tmp_path)
    run_id, _ = run_batch(db, source="funddata")

    report = LabelRunReader(db).get_fund_report(run_id, "000001")
    assert report is not None
    label_codes = {item["label_code"] for item in report["labels"]}
    assert "style_drift" not in label_codes
    assert "style_stable" not in label_codes
    assert "style_recent_shift" not in label_codes
