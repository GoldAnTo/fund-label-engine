"""SQLite 备份脚本测试。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.backup_sqlite import backup_database


def test_backup_creates_file_with_data(tmp_path: Path) -> None:
    """备份文件应包含源数据库的所有数据。"""
    src = tmp_path / "src.sqlite"
    with sqlite3.connect(src) as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'a'), (2, 'b')")
        conn.commit()

    backup_dir = tmp_path / "backups"
    bak = backup_database(src, backup_dir)

    assert bak.exists()
    with sqlite3.connect(bak) as conn:
        rows = conn.execute("SELECT v FROM t ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["a", "b"]


def test_backup_cleans_old_files(tmp_path: Path) -> None:
    """超过 max_backups 的旧备份应被自动删除。"""
    src = tmp_path / "src.sqlite"
    with sqlite3.connect(src) as conn:
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()

    backup_dir = tmp_path / "backups"
    # 创建 5 个备份
    for _ in range(5):
        backup_database(src, backup_dir, max_backups=3)

    bak_files = sorted(backup_dir.glob("*.sqlite"))
    assert len(bak_files) <= 3


def test_backup_raises_for_missing_source(tmp_path: Path) -> None:
    """源数据库不存在应报错。"""
    with pytest.raises(FileNotFoundError):
        backup_database(tmp_path / "missing.sqlite", tmp_path / "backups")


def test_backup_creates_unique_filenames(tmp_path: Path) -> None:
    """多次备份应产生不同的文件名（基于时间戳）。"""
    src = tmp_path / "src.sqlite"
    with sqlite3.connect(src) as conn:
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()

    backup_dir = tmp_path / "backups"
    files = set()
    for _ in range(3):
        bak = backup_database(src, backup_dir, max_backups=10)
        files.add(bak.name)
    assert len(files) == 3  # 三次备份产生 3 个不同文件名
