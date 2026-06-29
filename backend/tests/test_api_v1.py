from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.batch import run_batch
from app.main import create_app
from scripts.seed_sample_db import seed


@pytest.fixture()
def seeded_run(tmp_path: Path) -> tuple[Path, str]:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    return db, run_id


def test_list_runs_returns_succeeded_run(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get("/v1/runs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["run_id"] == run_id
    assert payload["runs"][0]["status"] == "succeeded"


def test_get_run_includes_processed_fund_codes(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["fund_codes"] == ["000001", "000002"]


def test_get_run_fund_returns_labels_and_evidence(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/funds/000001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["fund_code"] == "000001"
    label_codes = {item["label_code"] for item in payload["labels"]}
    assert "holding_concentration_high" in label_codes
    assert "fee_low" in label_codes
    assert payload["coverage"]["stock_holdings"] is True
    assert any(
        item["label_code"] == "holding_concentration_high"
        for item in payload["evidence"]
    )
    assert payload["reviews"] == []


def test_get_run_fund_report_returns_complete_payload(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/funds/000001/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["fund_code"] == "000001"
    assert payload["missing_fields"] == []
    assert payload["summary"]["label_count"] == len(payload["labels"])
    assert payload["summary"]["evidence_count"] == len(payload["evidence"])
    feature_codes = {item["feature_code"] for item in payload["features"]}
    assert "top_10_holding_weight" in feature_codes
    assert "total_annual_fee" in feature_codes


def test_fund_report_includes_equity_style_contributions(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/funds/000001/report")

    assert response.status_code == 200
    payload = response.json()
    assert "equity_style_contributions" in payload
    assert isinstance(payload["equity_style_contributions"], list)
    assert "equity_style_contribution_count" in payload["summary"]


def test_get_run_fund_404_for_unknown_fund(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/funds/999999")

    assert response.status_code == 404


def test_get_latest_fund_labels_uses_latest_run(seeded_run) -> None:
    db, _ = seeded_run
    # 再跑一遍，确认接口能拿到最新的那次
    new_run_id, _ = run_batch(db)
    client = TestClient(create_app(db_path=db))

    response = client.get("/v1/funds/000002/labels")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == new_run_id
    label_codes = {item["label_code"] for item in payload["labels"]}
    assert "data_insufficient" in label_codes
    assert payload["review_action"] == "manual_review"


def test_post_review_persists_manual_decision(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.post(
        f"/v1/runs/{run_id}/funds/000001/labels/holding_concentration_high/reviews",
        json={
            "decision": "confirm",
            "reviewer": "researcher-a",
            "comment": "证据充分，确认标签。",
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["decision"] == "confirm"
    assert created["label_code"] == "holding_concentration_high"

    detail = client.get(f"/v1/runs/{run_id}/funds/000001").json()
    assert detail["reviews"] == [created]


def test_api_returns_503_when_db_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLE_DB_PATH", raising=False)
    monkeypatch.delenv("FLE_SOURCE_DB", raising=False)
    monkeypatch.delenv("FLE_OUTPUT_DB", raising=False)
    client = TestClient(create_app())

    response = client.get("/v1/runs")

    assert response.status_code == 503


def test_post_run_triggers_batch_and_returns_run_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("FLE_SOURCE_DB", raising=False)
    monkeypatch.delenv("FLE_OUTPUT_DB", raising=False)
    db = tmp_path / "fund.sqlite"
    seed(db)
    client = TestClient(create_app(db_path=db))

    response = client.post("/v1/runs", json={"source": "auto"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["processed"] >= 1
    run_id = body["run_id"]
    detail = client.get(f"/v1/runs/{run_id}").json()
    assert detail["run_id"] == run_id
    assert detail["status"] == "succeeded"


def test_post_run_with_separated_dbs_keeps_source_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("FLE_DB_PATH", raising=False)
    source = tmp_path / "fundData.sqlite"
    output = tmp_path / "results.sqlite"
    seed(source)
    monkeypatch.setenv("FLE_SOURCE_DB", str(source))
    monkeypatch.setenv("FLE_OUTPUT_DB", str(output))
    # output db 用于 reader（查询批次），所以同时把 db_path 指到 output
    client = TestClient(create_app(db_path=output))

    response = client.post("/v1/runs")

    assert response.status_code == 201
    body = response.json()
    assert body["processed"] >= 1
    # output db 必须有 label_runs；source db 不应该有
    import sqlite3

    with sqlite3.connect(source) as conn:
        source_tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "label_runs" not in source_tables
    with sqlite3.connect(output) as conn:
        output_tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "label_runs" in output_tables


def test_post_run_with_only_source_and_output_env_can_be_queried(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("FLE_DB_PATH", raising=False)
    source = tmp_path / "fundData.sqlite"
    output = tmp_path / "results.sqlite"
    seed(source)
    monkeypatch.setenv("FLE_SOURCE_DB", str(source))
    monkeypatch.setenv("FLE_OUTPUT_DB", str(output))
    client = TestClient(create_app())

    response = client.post("/v1/runs")

    assert response.status_code == 201
    runs = client.get("/v1/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == response.json()["run_id"]


def test_post_run_503_without_source_or_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FLE_DB_PATH", raising=False)
    monkeypatch.delenv("FLE_SOURCE_DB", raising=False)
    monkeypatch.delenv("FLE_OUTPUT_DB", raising=False)
    client = TestClient(create_app())

    response = client.post("/v1/runs")

    assert response.status_code == 503


def test_frontend_dist_is_mounted_when_provided(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("FLE_FRONTEND_DIST", raising=False)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><html><body><div id=root></div></body></html>"
    )
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hi');")

    db = tmp_path / "fund.sqlite"
    seed(db)
    client = TestClient(create_app(db_path=db, frontend_dist=dist))

    # API 仍然可用
    assert client.get("/health").status_code == 200
    # 根路径和前端路由都返回 index.html
    root = client.get("/")
    assert root.status_code == 200
    assert b"id=root" in root.content
    ready_pool = client.get("/ready-pool")
    assert ready_pool.status_code == 200
    assert b"id=root" in ready_pool.content
    fund_report = client.get("/runs/run-1/funds/000001")
    assert fund_report.status_code == 200
    assert b"id=root" in fund_report.content
    # 静态资源也能拿到
    js = client.get("/assets/app.js")
    assert js.status_code == 200
    assert b"console.log" in js.content


def test_create_app_without_dist_does_not_mount(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("FLE_FRONTEND_DIST", raising=False)
    # 指向一个不存在的目录，create_app 不应该抛错，而是跳过 mount
    bogus = tmp_path / "no-such-dir"
    db = tmp_path / "fund.sqlite"
    seed(db)
    client = TestClient(create_app(db_path=db, frontend_dist=bogus))

    # 没 mount 静态时，根路径应返回 404（不是 SPA 入口）
    root = client.get("/")
    assert root.status_code == 404
    # API 不受影响
    assert client.get("/health").status_code == 200


def test_get_run_returns_failure_count_and_rule_snapshot(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    payload = client.get(f"/v1/runs/{run_id}").json()
    # 默认 sample 没有失败
    assert payload["failure_count"] == 0
    assert payload["failures"] == []
    # 规则快照已落库
    assert payload["rule_snapshot"]["holding_concentration_threshold"] == 0.55


def test_get_run_rules_endpoint_returns_snapshot(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/rules")

    assert response.status_code == 200
    body = response.json()
    assert body["rule_version"] == "v1"
    assert "long_term_return_threshold" in body["rule_snapshot"]
    assert "fund_size_moderate_min" in body["rule_snapshot"]


def test_get_run_summary_aggregates_counts_and_distributions(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["run_id"] == run_id
    assert summary["status"] == "succeeded"
    counts = summary["counts"]
    # 样例 db 里 2 只基金都被处理；000002 数据不足 + manual_review
    assert counts["processed"] == 2
    assert counts["failed"] == 0
    assert counts["data_insufficient"] == 1
    assert counts["manual_review"] == 1
    # 标签分布按 fund_count 倒序
    distribution = {item["label_code"]: item for item in summary["label_distribution"]}
    assert "data_sufficient" in distribution
    assert distribution["data_sufficient"]["fund_count"] == 1
    review_dist = {
        item["review_action"]: item["fund_count"]
        for item in summary["review_action_distribution"]
    }
    assert review_dist.get("manual_review") == 1
    assert review_dist.get("observe") == 1
    state_dist = {
        item["state"]: item["calculation_count"]
        for item in summary["calculation_state_distribution"]
    }
    assert state_dist["triggered"] > 0
    assert state_dist["not_triggered"] > 0
    assert state_dist["not_computed"] > 0
    reason_dist = {
        item["reason_code"]: item["calculation_count"]
        for item in summary["not_computed_reason_distribution"]
    }
    assert reason_dist["return_window_insufficient"] > 0


def test_label_definitions_endpoint_returns_thresholds(seeded_run) -> None:
    db, _ = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get("/v1/label-definitions")

    assert response.status_code == 200
    defs = {d["label_code"]: d for d in response.json()["definitions"]}
    fee_low = defs["fee_low"]
    assert fee_low["category"] == "fee_size"
    assert fee_low["thresholds"]["total_annual_fee_max"] == 0.012
    fund_size_moderate = defs["fund_size_moderate"]
    assert fund_size_moderate["thresholds"]["fund_size_min"] == 5.0
    assert fund_size_moderate["thresholds"]["fund_size_max"] == 100.0


def test_rule_versions_endpoint_lists_versions_with_run_counts(seeded_run) -> None:
    db, _ = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get("/v1/rule-versions")

    assert response.status_code == 200
    versions = response.json()["rule_versions"]
    assert len(versions) == 1
    assert versions[0]["rule_version"] == "v1"
    assert versions[0]["run_count"] == 1


def test_style_endpoint_returns_distribution(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/style")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert set(payload["styles"].keys()) == {
        "deep_value",
        "quality_growth",
        "dividend_steady",
    }
    # 每个风格都有 count + funds 数组
    for style in payload["styles"].values():
        assert "count" in style
        assert isinstance(style["funds"], list)
    # sample DB 没数据时三个 count 都为 0；边界标签计数都暴露出来
    assert "stock_factors_missing" in payload["boundary_counts"]
    assert "style_pending_rule_definition" in payload["boundary_counts"]


def test_style_endpoint_404_for_unknown_run(seeded_run) -> None:
    db, _ = seeded_run
    client = TestClient(create_app(db_path=db))
    response = client.get("/v1/runs/does-not-exist/style")
    assert response.status_code == 404


def test_search_run_funds_supports_filters(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(
        f"/v1/runs/{run_id}/search",
        params={"label_code": "holding_concentration_high"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    fund_codes = [item["fund_code"] for item in payload["results"]]
    assert fund_codes == ["000001"]
    assert "holding_concentration_high" in payload["available_labels"]


def test_search_run_funds_filters_by_group_code(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(
        f"/v1/runs/{run_id}/search",
        params={"group_code": "data_gap_pool"},
    )

    assert response.status_code == 200
    payload = response.json()
    fund_codes = [item["fund_code"] for item in payload["results"]]
    assert payload["filters"]["group_code"] == "data_gap_pool"
    assert fund_codes == ["000002"]
    assert "data_gap_pool" in payload["available_groups"]


def test_search_run_funds_filters_by_classification_code(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(
        f"/v1/runs/{run_id}/search",
        params={"classification_code": "data_gap"},
    )

    assert response.status_code == 200
    payload = response.json()
    fund_codes = [item["fund_code"] for item in payload["results"]]
    assert payload["filters"]["classification_code"] == "data_gap"
    assert fund_codes == ["000002"]
    assert "data_gap" in payload["available_classifications"]


def test_review_queue_lists_manual_review_funds(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/review-queue")

    assert response.status_code == 200
    fund_codes = [item["fund_code"] for item in response.json()["results"]]
    assert fund_codes == ["000002"]


def test_search_unknown_run_returns_404(seeded_run) -> None:
    db, _ = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get("/v1/runs/does_not_exist/search")

    assert response.status_code == 404


def test_relative_label_eligibility_endpoint_lists_ready_and_blocked(seeded_run) -> None:
    db, run_id = seeded_run
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE benchmark_components (
                fund_code TEXT,
                component_order INTEGER,
                component_code TEXT,
                component_name TEXT,
                weight REAL,
                source_text TEXT,
                status TEXT,
                reason TEXT,
                secid TEXT
            );
            CREATE TABLE benchmark_returns (
                fund_code TEXT,
                benchmark_code TEXT,
                trade_date TEXT,
                daily_return REAL
            );
            CREATE TABLE benchmark_component_returns (
                component_code TEXT,
                trade_date TEXT,
                daily_return REAL
            );
            ALTER TABLE fund_profiles ADD COLUMN benchmark TEXT;
            ALTER TABLE fund_profiles ADD COLUMN tracking_target TEXT;
            """
        )
        conn.executemany(
            "INSERT INTO benchmark_components VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("000001", 1, "000300", "沪深300", 1.0, "沪深300", "resolved", "exact", "1.000300"),
                ("000002", 1, "LOCAL_CBOND_TOTAL", "中债总", 1.0, "中债总", "resolved", "exact", "LOCAL_CBOND_TOTAL"),
            ],
        )
        for i in range(200):
            conn.execute(
                "INSERT INTO nav_history (fund_code, nav_date, daily_return) VALUES ('000001', ?, 0.001)",
                (f"2026-01-{i:03d}",),
            )
            conn.execute(
                "INSERT INTO benchmark_returns VALUES ('000001', '000300', ?, 0.001)",
                (f"2026-01-{i:03d}",),
            )
        conn.commit()
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/relative-label-eligibility")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_funds"] == 2
    assert payload["ready_count"] == 1
    assert payload["blocked_count"] == 1
    assert payload["blocker_groups"] == [
        {
            "key": "benchmark_source_missing|LOCAL_CBOND_TOTAL:中债总",
            "status": "benchmark_source_missing",
            "component": "LOCAL_CBOND_TOTAL:中债总",
            "count": 1,
            "sample_fund_codes": ["000002"],
        }
    ]
    by_code = {row["fund_code"]: row for row in payload["results"]}
    assert by_code["000001"]["relative_label_status"] == "relative_label_ready"
    assert by_code["000002"]["relative_label_status"] == "benchmark_source_missing"


def test_relative_label_eligibility_endpoint_filters_blocked(seeded_run) -> None:
    db, run_id = seeded_run
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE benchmark_components (
                fund_code TEXT,
                component_order INTEGER,
                component_code TEXT,
                component_name TEXT,
                weight REAL,
                source_text TEXT,
                status TEXT,
                reason TEXT,
                secid TEXT
            );
            CREATE TABLE benchmark_returns (
                fund_code TEXT,
                benchmark_code TEXT,
                trade_date TEXT,
                daily_return REAL
            );
            CREATE TABLE benchmark_component_returns (
                component_code TEXT,
                trade_date TEXT,
                daily_return REAL
            );
            ALTER TABLE fund_profiles ADD COLUMN benchmark TEXT;
            ALTER TABLE fund_profiles ADD COLUMN tracking_target TEXT;
            """
        )
        conn.execute(
            "INSERT INTO benchmark_components VALUES ('000001', 1, '000300', '沪深300', 1.0, '沪深300', 'resolved', 'exact', '1.000300')"
        )
        conn.execute(
            "INSERT INTO benchmark_components VALUES ('000002', 1, 'LOCAL_CBOND_TOTAL', '中债总', 1.0, '中债总', 'resolved', 'exact', 'LOCAL_CBOND_TOTAL')"
        )
        for i in range(200):
            conn.execute(
                "INSERT INTO nav_history (fund_code, nav_date, daily_return) VALUES ('000001', ?, 0.001)",
                (f"2026-01-{i:03d}",),
            )
            conn.execute(
                "INSERT INTO benchmark_returns VALUES ('000001', '000300', ?, 0.001)",
                (f"2026-01-{i:03d}",),
            )
        conn.commit()
    client = TestClient(create_app(db_path=db))

    response = client.get(
        f"/v1/runs/{run_id}/relative-label-eligibility",
        params={"status": "blocked"},
    )

    assert response.status_code == 200
    rows = response.json()["results"]
    assert [row["fund_code"] for row in rows] == ["000002"]


def test_benchmark_components_endpoint_returns_structure(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(
        f"/v1/runs/{run_id}/funds/000001/benchmark-components"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fund_code"] == "000001"
    assert "components" in payload
    assert isinstance(payload["components"], list)
    assert "has_benchmark_returns" in payload
    assert "unresolved_count" in payload
    assert payload["unresolved_count"] == len(
        [c for c in payload["components"] if c["status"] != "resolved" or not c["has_returns"]]
    )


def test_benchmark_components_endpoint_503_without_source_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FLE_SOURCE_DB", raising=False)
    monkeypatch.delenv("FLE_DB_PATH", raising=False)
    client = TestClient(create_app())

    response = client.get("/v1/runs/x/funds/000001/benchmark-components")
    assert response.status_code == 503
