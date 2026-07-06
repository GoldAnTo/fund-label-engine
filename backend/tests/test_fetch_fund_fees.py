import sqlite3

from scripts.fetch_fund_fees import (
    backfill_operation_fees,
    parse_eastmoney_fee_page,
    select_fee_only_gap_codes,
    select_operation_fee_targets,
    upsert_fee_rows,
)


def test_parse_eastmoney_operation_fee_table():
    html = """
    <html><body>
      <h4 class="t">运作费用</h4>
      <table>
        <tr><th>费用类别</th><th>费率</th></tr>
        <tr><td>管理费率</td><td>1.20%（每年）</td></tr>
        <tr><td>托管费率</td><td>0.20%（每年）</td></tr>
        <tr><td>销售服务费率</td><td>0.00%（每年）</td></tr>
      </table>
    </body></html>
    """

    rows = parse_eastmoney_fee_page(html, indicators=["运作费用"])

    by_name = {row["condition_name"]: row for row in rows}
    assert by_name["管理费率"]["fee"] == 0.012
    assert by_name["托管费率"]["fee"] == 0.002
    assert by_name["销售服务费率"]["fee"] == 0.0
    assert by_name["管理费率"]["source"] == "eastmoney.fund_fee_page"


def test_upsert_fee_rows_matches_funddata_schema(tmp_path):
    db = tmp_path / "fees.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
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
            )
            """
        )
        upserted = upsert_fee_rows(
            conn,
            "000001",
            [
                {
                    "fee_type": "运作费用",
                    "condition_name": "管理费率",
                    "fee": 0.012,
                    "fee_text": "1.20%（每年）",
                    "discount_fee": None,
                    "discount_fee_text": "",
                    "source": "eastmoney.fund_fee_page",
                }
            ],
        )
        row = conn.execute(
            "SELECT fund_code, fee_type, condition_name, fee, fee_text, source "
            "FROM fee_structures WHERE fund_code='000001'"
        ).fetchone()

    assert upserted == 1
    assert row == (
        "000001",
        "运作费用",
        "管理费率",
        0.012,
        "1.20%（每年）",
        "eastmoney.fund_fee_page",
    )


def test_select_operation_fee_targets_includes_placeholder_only_funds(tmp_path):
    db = tmp_path / "targets.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_profiles (fund_code TEXT PRIMARY KEY, fund_type TEXT);
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
            INSERT INTO fund_profiles VALUES
                ('000001', '混合型-偏股'),
                ('000002', '混合型-偏股'),
                ('000003', '股票型');
            INSERT INTO fee_structures VALUES
                ('000001', '运作费用', '场内ETF-无费率信息', NULL, 'old', 'now', '', NULL, ''),
                ('000002', '运作费用', '管理费率', 0.012, 'old', 'now', '1.20%', NULL, ''),
                ('000002', '运作费用', '托管费率', 0.002, 'old', 'now', '0.20%', NULL, '');
            """
        )

        targets = select_operation_fee_targets(conn)

    assert targets == ["000001", "000003"]


def test_backfill_operation_fees_fetches_in_parallel_and_writes_on_main_thread(
    tmp_path,
    monkeypatch,
):
    db = tmp_path / "parallel.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_profiles (fund_code TEXT PRIMARY KEY, fund_type TEXT);
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
            INSERT INTO fund_profiles VALUES ('000001', '混合型-偏股'), ('000002', '股票型');
            """
        )

    def fake_fetch(code, *, timeout):
        return """
        <h4 class="t">运作费用</h4>
        <table>
          <tr><th>费用类别</th><th>费率</th></tr>
          <tr><td>管理费率</td><td>1.20%（每年）</td></tr>
          <tr><td>托管费率</td><td>0.20%（每年）</td></tr>
        </table>
        """

    monkeypatch.setattr("scripts.fetch_fund_fees.fetch_eastmoney_fee_page", fake_fetch)

    stats = backfill_operation_fees(db, concurrency=2)

    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM fee_structures").fetchone()[0]
        remaining = select_operation_fee_targets(conn)

    assert stats.attempted == 2
    assert stats.with_rows == 2
    assert stats.rows_upserted == 4
    assert stats.failed == 0
    assert count == 4
    assert remaining == []


def test_select_fee_only_gap_codes_uses_latest_run_and_limit(tmp_path):
    db = tmp_path / "coverage.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE label_runs (
                run_id TEXT PRIMARY KEY,
                run_at TEXT NOT NULL,
                data_as_of TEXT,
                rule_version TEXT NOT NULL,
                status TEXT NOT NULL,
                rule_snapshot_json TEXT
            );
            CREATE TABLE fund_run_coverage (
                run_id TEXT NOT NULL,
                fund_code TEXT NOT NULL,
                field TEXT NOT NULL,
                present INTEGER NOT NULL,
                review_action TEXT NOT NULL,
                fund_type TEXT,
                PRIMARY KEY (run_id, fund_code, field)
            );

            INSERT INTO label_runs VALUES
                ('old', '2026-01-01T00:00:00+00:00', NULL, 'v1', 'success', '{}'),
                ('latest', '2026-01-02T00:00:00+00:00', NULL, 'v1', 'success', '{}');

            INSERT INTO fund_run_coverage VALUES
                ('old', '000009', 'fee_structure', 0, 'manual_review', '混合型-偏股'),
                ('latest', '000001', 'fee_structure', 0, 'manual_review', '混合型-偏股'),
                ('latest', '000001', 'stock_holdings', 1, 'manual_review', '混合型-偏股'),
                ('latest', '000002', 'fee_structure', 0, 'manual_review', '混合型-偏股'),
                ('latest', '000002', 'stock_holdings', 0, 'manual_review', '混合型-偏股'),
                ('latest', '000003', 'fee_structure', 0, 'manual_review', '股票型'),
                ('latest', '000003', 'industry_allocations', 1, 'manual_review', '股票型'),
                ('latest', '000004', 'stock_holdings', 0, 'manual_review', '股票型');
            """
        )

    assert select_fee_only_gap_codes(db, limit=1) == ["000001"]
    assert select_fee_only_gap_codes(db) == ["000001", "000003"]
    assert select_fee_only_gap_codes(db, run_id="old") == ["000009"]
