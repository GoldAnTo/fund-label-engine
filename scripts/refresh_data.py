#!/usr/bin/env python3
"""一键数据刷新脚本：自动接入真实数据 + 刷新因子 + 补充缺失数据。

用法::

    python scripts/refresh_data.py                    # 刷新所有
    python scripts/refresh_data.py --copy-only        # 仅拷贝缓存库
    python scripts/refresh_data.py --factors-only     # 仅刷新股票因子
    python scripts/refresh_data.py --supplement-only  # 仅补充缺失数据

流程：
1. 拷贝 ~/.cache/fund-data 缓存库到 /tmp/fle-run/source.sqlite
2. 导入行业映射数据
3. 刷新股票因子（调用 fetch_stock_factors.py）
4. 补充缺失数据（北向资金/龙虎榜/概念板块）
5. 验证数据完整性
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("refresh_data")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
TARGET_DB = Path("/tmp/fle-run/source.sqlite")
FACTORS_DB = DATA_DIR / "stock_factors.sqlite"


def find_cache_db() -> Path | None:
    """查找最新的缓存基金数据库。"""
    cache_base = Path.home() / ".cache" / "fund-data" / "releases"
    if not cache_base.exists():
        log.warning("缓存目录不存在: %s", cache_base)
        return None
    candidates = sorted(cache_base.glob("*/fund_data_query.sqlite"), reverse=True)
    if not candidates:
        log.warning("缓存目录中未找到 fund_data_query.sqlite")
        return None
    return candidates[0]


def copy_cache_db() -> bool:
    """步骤1：拷贝缓存库到工作位置。"""
    cache_db = find_cache_db()
    if cache_db is None:
        log.error("未找到缓存数据库，请先运行 fund-data 系统同步")
        return False

    log.info("拷贝缓存库: %s (%.1f MB)", cache_db, cache_db.stat().st_size / 1e6)
    TARGET_DB.parent.mkdir(parents=True, exist_ok=True)

    # WAL checkpoint 确保数据一致
    subprocess.run(
        ["sqlite3", str(cache_db), "PRAGMA wal_checkpoint(TRUNCATE);"],
        capture_output=True, check=False,
    )
    shutil.copy2(cache_db, TARGET_DB)
    log.info("已拷贝到: %s (%.1f MB)", TARGET_DB, TARGET_DB.stat().st_size / 1e6)
    return True


def import_industry_map() -> None:
    """步骤2：导入行业映射数据。"""
    if not FACTORS_DB.exists():
        log.warning("因子数据库不存在，跳过行业映射导入: %s", FACTORS_DB)
        return

    log.info("导入行业映射数据...")
    conn = sqlite3.connect(TARGET_DB)
    conn.execute("DROP TABLE IF EXISTS stock_industry_map;")
    conn.commit()
    conn.close()

    # 用 sqlite3 dump + 导入
    subprocess.run(
        f'sqlite3 "{FACTORS_DB}" ".dump stock_industry_map" | sqlite3 "{TARGET_DB}"',
        shell=True, capture_output=True, check=True,
    )
    count = _count_rows(TARGET_DB, "stock_industry_map")
    log.info("行业映射导入完成: %d 条", count)


def create_indexes() -> None:
    """步骤2b：创建关键索引，加速认知引擎查询。"""
    log.info("创建数据库索引...")
    source_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_stock_holdings_stock_code ON stock_holdings(stock_code, fund_code);",
        "CREATE INDEX IF NOT EXISTS idx_stock_industry_map_stock_code ON stock_industry_map(stock_code);",
        "CREATE INDEX IF NOT EXISTS idx_fund_profiles_fund_type ON fund_profiles(fund_type);",
    ]
    conn = sqlite3.connect(str(TARGET_DB))
    for sql in source_indexes:
        conn.execute(sql)
    conn.commit()
    conn.close()

    factor_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_concept_board_stocks_name ON concept_board_stocks(concept_name);",
        "CREATE INDEX IF NOT EXISTS idx_concept_board_stocks_code ON concept_board_stocks(concept_code);",
        "CREATE INDEX IF NOT EXISTS idx_stock_factor_values_stock_code ON stock_factor_values(stock_code, factor_code);",
    ]
    conn = sqlite3.connect(str(FACTORS_DB))
    for sql in factor_indexes:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    log.info("索引创建完成")


def refresh_factors() -> None:
    """步骤3：刷新股票因子数据。"""
    log.info("刷新股票因子数据...")
    script = SCRIPTS_DIR / "fetch_stock_factors.py"
    if not script.exists():
        log.warning("因子抓取脚本不存在: %s", script)
        return

    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    result = subprocess.run(
        [str(venv_python), str(script),
         "--trade-date", _today_str_dash(),
         "--report-date", _latest_report_date()],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    if result.returncode == 0:
        count = _count_rows(FACTORS_DB, "stock_factor_values")
        log.info("因子刷新完成: %d 条", count)
    else:
        log.warning("因子刷新失败（非致命）: %s", result.stderr[:200])


def supplement_missing_data() -> None:
    """步骤4：补充缺失数据（北向资金/龙虎榜/概念板块）。"""
    scripts_to_run = [
        ("fetch_northbound_capital.py", "北向资金"),
        ("fetch_dragon_tiger.py", "龙虎榜"),
        ("fetch_concept_boards.py", "概念板块"),
    ]

    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    for script_name, label in scripts_to_run:
        script = SCRIPTS_DIR / script_name
        if not script.exists():
            log.warning("脚本不存在，跳过 %s: %s", label, script)
            continue

        log.info("补充 %s 数据...", label)
        try:
            result = subprocess.run(
                [str(venv_python), str(script)],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT),
                timeout=300,
            )
            if result.returncode == 0:
                log.info("%s 数据补充完成", label)
            else:
                log.warning("%s 数据补充失败（非致命）: %s", label, result.stderr[:200])
        except subprocess.TimeoutExpired:
            log.warning("%s 数据补充超时（非致命）", label)


def verify_data() -> None:
    """步骤5：验证数据完整性。"""
    log.info("=== 数据验证 ===")
    if not TARGET_DB.exists():
        log.error("目标数据库不存在: %s", TARGET_DB)
        return

    tables = [
        ("fund_profiles", "基金档案"),
        ("stock_holdings", "基金持仓"),
        ("nav_history", "净值历史"),
        ("fund_managers", "基金经理"),
        ("stock_industry_map", "行业映射"),
    ]
    for table, label in tables:
        count = _count_rows(TARGET_DB, table)
        status = "OK" if count > 0 else "EMPTY"
        log.info("  %-12s %-6s %s: %d 行", table, status, label, count)

    if FACTORS_DB.exists():
        factor_count = _count_rows(FACTORS_DB, "stock_factor_values")
        log.info("  stock_factor_values %-6s 股票因子: %d 行", "OK" if factor_count > 0 else "EMPTY", factor_count)


def _count_rows(db_path: Path, table: str) -> int:
    """安全地查询表行数。"""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _today_str_dash() -> str:
    from datetime import date
    return date.today().strftime("%Y-%m-%d")


def _latest_report_date() -> str:
    """返回最近的季报日期。"""
    from datetime import date
    today = date.today()
    year = today.year
    if today.month >= 10:
        return f"{year}-09-30"
    elif today.month >= 7:
        return f"{year}-06-30"
    elif today.month >= 4:
        return f"{year}-03-31"
    else:
        return f"{year - 1}-12-31"


def main() -> None:
    parser = argparse.ArgumentParser(description="一键数据刷新")
    parser.add_argument("--copy-only", action="store_true", help="仅拷贝缓存库")
    parser.add_argument("--factors-only", action="store_true", help="仅刷新股票因子")
    parser.add_argument("--supplement-only", action="store_true", help="仅补充缺失数据")
    args = parser.parse_args()

    if args.copy_only:
        copy_cache_db()
        import_industry_map()
        create_indexes()
        verify_data()
        return

    if args.factors_only:
        refresh_factors()
        verify_data()
        return

    if args.supplement_only:
        supplement_missing_data()
        verify_data()
        return

    # 完整流程
    log.info("=== 开始一键数据刷新 ===")
    if copy_cache_db():
        import_industry_map()
        create_indexes()
    refresh_factors()
    supplement_missing_data()
    verify_data()
    log.info("=== 数据刷新完成 ===")
    log.info("启动后端: FLE_SOURCE_DB=%s .venv/bin/python -m uvicorn app.main:app --port 8000", TARGET_DB)


if __name__ == "__main__":
    main()
