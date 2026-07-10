"""smoke --persist 正式测试:首次运行、重复运行、报告反查。

覆盖:
    1. 首次运行:3 个场景全部落库,verify 全部 OK
    2. 重复运行(同 run-id):零重复,DB 计数不变
    3. 报告展示真实落库 ID(非内存 ID)
    4. 快照 ID 统一(snap_smoke 贯穿报告和 DB)
    5. API 反查可获取完整链路
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SMOKE_SCRIPT = _REPO_ROOT / "scripts" / "p0" / "smoke_e2e_private_fund.py"
_REPORT_PATH = _REPO_ROOT / "reports" / "p0" / "smoke-e2e-report.md"


def _run_smoke(gov_db: Path, run_id: str) -> subprocess.CompletedProcess:
    """跑 smoke --persist,返回结果。"""
    return subprocess.run(
        [
            sys.executable, "scripts/p0/smoke_e2e_private_fund.py",
            "--persist",
            "--governance-db", str(gov_db),
            "--run-id", run_id,
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _db_counts(gov_db: Path, run_id: str) -> dict[str, int]:
    """查 DB 中指定 run_id 的记录数。"""
    pattern = f"ri_{run_id}%"
    conn = sqlite3.connect(str(gov_db))
    try:
        return {
            "research_inputs": conn.execute(
                "SELECT COUNT(*) FROM research_inputs WHERE user_input_id LIKE ?", (pattern,)
            ).fetchone()[0],
            "theses": conn.execute(
                "SELECT COUNT(*) FROM investment_theses WHERE user_input_id LIKE ?", (pattern,)
            ).fetchone()[0],
            "candidates": conn.execute(
                "SELECT COUNT(*) FROM candidate_sets WHERE user_input_id LIKE ?", (pattern,)
            ).fetchone()[0],
            "audit_logs": conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE target_id LIKE ?", (pattern,)
            ).fetchone()[0],
        }
    finally:
        conn.close()


@pytest.fixture()
def gov_db(tmp_path: Path) -> Path:
    return tmp_path / "governance.sqlite"


@pytest.fixture()
def source_db_cleanup():
    """确保 source DB 在测试前不存在(让 smoke 自己创建)。"""
    source_db = Path("/tmp/fle-p0/source.sqlite")
    if source_db.exists():
        source_db.unlink()
    yield
    # 测试后不清理(让其他测试复用)


class TestSmokeFirstRun:
    """首次运行 smoke --persist。"""

    def test_first_run_succeeds(self, gov_db: Path, source_db_cleanup):
        """首次运行应成功,3 个场景全部 verify OK。"""
        result = _run_smoke(gov_db, "test_first")
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "verify: A" in result.stdout and "OK" in result.stdout
        assert "verify: B" in result.stdout and "OK" in result.stdout
        assert "verify: C" in result.stdout and "OK" in result.stdout

    def test_first_run_creates_records(self, gov_db: Path, source_db_cleanup):
        """首次运行应在 DB 中创建 3 条 research_inputs、3 条 theses、3 条 candidates。"""
        _run_smoke(gov_db, "test_count")
        counts = _db_counts(gov_db, "test_count")
        assert counts["research_inputs"] == 3
        assert counts["theses"] == 3
        assert counts["candidates"] == 3

    def test_report_shows_persisted_ids(self, gov_db: Path, source_db_cleanup):
        """报告应展示真实的落库 ID,不是内存生成的随机 ID。"""
        _run_smoke(gov_db, "test_report")
        report = _REPORT_PATH.read_text(encoding="utf-8")
        # 报告应包含 ri_test_report_a(确定性 ID)
        assert "ri_test_report_a" in report
        assert "ri_test_report_b" in report
        assert "ri_test_report_c" in report
        # 报告应包含 thesis_id(以 th_ 开头)
        assert "thesis_id:`th_" in report
        # 报告应包含 candidate_set_id(以 cs_ 开头)
        assert "candidate_set_id:`cs_" in report
        # 报告应包含 persist_status
        assert "persist_status:`created`" in report

    def test_report_uses_unified_snapshot(self, gov_db: Path, source_db_cleanup):
        """报告应展示统一的 snap_smoke,不是随机快照 ID。"""
        _run_smoke(gov_db, "test_snap")
        report = _REPORT_PATH.read_text(encoding="utf-8")
        assert "snap_smoke" in report
        # 不应出现 snap_ 后面跟随机 hex(内存模式才会生成)
        # 允许 snap_smoke 出现,但不允许 snap_a1b2c3d4 这种随机 ID
        import re
        random_snaps = re.findall(r"snap_[0-9a-f]{8}", report)
        assert len(random_snaps) == 0, f"报告中有随机快照 ID: {random_snaps}"


class TestSmokeRepeatRun:
    """重复运行(同 run-id)。"""

    def test_repeat_run_no_duplicates(self, gov_db: Path, source_db_cleanup):
        """重跑同 run-id 不应产生重复记录。"""
        # 第一次
        r1 = _run_smoke(gov_db, "test_repeat")
        assert r1.returncode == 0
        counts1 = _db_counts(gov_db, "test_repeat")
        assert counts1["research_inputs"] == 3

        # 第二次(同 run-id)
        r2 = _run_smoke(gov_db, "test_repeat")
        assert r2.returncode == 0
        counts2 = _db_counts(gov_db, "test_repeat")
        # 零重复
        assert counts2 == counts1, f"重复运行产生了新记录: {counts1} -> {counts2}"

    def test_repeat_run_verify_still_ok(self, gov_db: Path, source_db_cleanup):
        """重跑后 verify 仍全部 OK(用的是第一次创建的数据)。"""
        _run_smoke(gov_db, "test_reverify")
        r2 = _run_smoke(gov_db, "test_reverify")
        assert r2.returncode == 0
        assert "verify: A" in r2.stdout and "OK" in r2.stdout
        assert "verify: B" in r2.stdout and "OK" in r2.stdout
        assert "verify: C" in r2.stdout and "OK" in r2.stdout


class TestSmokeApiReverseLookup:
    """通过 API 反查候选集合。"""

    def test_candidate_set_has_full_chain(self, gov_db: Path, source_db_cleanup):
        """每个 candidate_set 都能反查到 thesis / research_input / policy / snapshot。"""
        from fastapi.testclient import TestClient
        from app.main import create_app

        _run_smoke(gov_db, "test_api")

        app = create_app(source_db_path=str(gov_db), output_db_path=str(gov_db))
        if hasattr(app.state, "governance_service"):
            del app.state.governance_service
        client = TestClient(app)

        # 查 DB 获取 candidate_set_ids
        conn = sqlite3.connect(str(gov_db))
        cs_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT candidate_set_id FROM candidate_sets WHERE user_input_id LIKE 'ri_test_api%'"
        ).fetchall()]
        conn.close()

        assert len(cs_ids) == 3

        for cs_id in cs_ids:
            resp = client.get(f"/v1/governance/candidate-sets/{cs_id}")
            assert resp.status_code == 200
            data = resp.json()
            # 完整反查链路
            assert data["candidate_set_id"] == cs_id
            assert data["thesis_id"] is not None
            assert data["user_input_id"] is not None
            assert data["strategy_policy_id"] == "private_equity_growth"
            assert data["strategy_policy_version"] == 1
            assert data["data_snapshot_id"] == "snap_smoke"
            assert len(data["candidates"]) >= 1
