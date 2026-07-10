"""轻量 SQLite migration runner。

- backend/app/persistence/migrations/*.sql 按文件名排序顺序执行。
- schema_migrations 表记录已执行的脚本，幂等。
- ensure_schema 调用前先跑 pending migration；writer.SCHEMA_STATEMENTS 是
  fallback（首次空库时也能拉起 baseline 表结构）。
"""
from __future__ import annotations

import sqlite3
from datetime import UTC
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def list_migrations() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def applied_ids(conn: sqlite3.Connection) -> set[str]:
    _ensure_migrations_table(conn)
    return {
        row[0]
        for row in conn.execute("SELECT id FROM schema_migrations").fetchall()
    }


def run_migrations(db_path: str) -> list[str]:
    """对一个 SQLite 文件运行所有未执行的 migration。返回新执行的 id 列表。

    每条 SQL 单独执行；遇到 "duplicate column name" 视为幂等，跳过该语句
    但仍把整个 migration 标记为已执行。这样允许 ALTER TABLE 在已有列的
    新库上安全运行。
    """
    from datetime import datetime

    conn = sqlite3.connect(db_path)
    try:
        _ensure_migrations_table(conn)
        already = applied_ids(conn)
        executed: list[str] = []
        for path in list_migrations():
            mig_id = path.stem
            if mig_id in already:
                continue
            sql = path.read_text(encoding="utf-8")
            for stmt in _split_statements(sql):
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    msg = str(exc).lower()
                    if "duplicate column name" in msg:
                        continue
                    raise
            conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (mig_id, datetime.now(UTC).isoformat(timespec="seconds")),
            )
            conn.commit()
            executed.append(mig_id)
        return executed
    finally:
        conn.close()


def _split_statements(sql: str) -> list[str]:
    """简单的 ; 分隔，忽略空行/注释。

    增强:识别 CREATE TRIGGER ... BEGIN ... END; 结构,内部的 ; 不切分。
    这是为了支持 governance_core 等需要数据库级不可变约束的 migration。
    """
    statements: list[str] = []
    buf: list[str] = []
    in_trigger = False
    trigger_buf: list[str] = []

    def _flush_buf() -> None:
        if buf:
            statements.append("\n".join(buf))
            buf.clear()

    def _flush_trigger() -> None:
        if trigger_buf:
            statements.append("\n".join(trigger_buf))
            trigger_buf.clear()

    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            # 注释行:append 到当前 buffer
            if in_trigger:
                trigger_buf.append(line)
            else:
                buf.append(line)
            continue
        upper = stripped.upper()
        if not in_trigger and upper.startswith("CREATE TRIGGER"):
            in_trigger = True
            trigger_buf.append(line)
            # 触发器体在 BEGIN ... END 块内
            if "END;" in stripped.upper() or stripped.upper().endswith("END"):
                _flush_trigger()
                in_trigger = False
            continue
        if in_trigger:
            trigger_buf.append(line)
            if "END;" in stripped.upper():
                _flush_trigger()
                in_trigger = False
            continue
        # 普通语句
        buf.append(line)
        if stripped.endswith(";"):
            _flush_buf()
    _flush_buf()
    return statements
