"""SQLite 数据库备份脚本。

用法：
    # 默认备份 output DB 到 backups/output_YYYYMMDD_HHMMSS.sqlite
    python scripts/backup_sqlite.py --db /tmp/fle-run/output.sqlite

    # 备份 source 和 output DB
    python scripts/backup_sqlite.py \\
        --db /tmp/fle-run/output.sqlite --db /tmp/fle-run/source.sqlite

    # 设置 MAX_BACKUPS=7 保留最近 7 份（默认 7）
    python scripts/backup_sqlite.py --db ... --max-backups 30

策略：
- 使用 sqlite3 在线备份 API（conn.backup），允许在被 backup 的 DB 同时被读写。
- 默认按时间戳命名。
- 保留最近 N 份，超过的自动清理。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


def backup_database(
    source_path: Path | str, backup_dir: Path, max_backups: int = 7
) -> Path:
    """备份单个 SQLite 数据库，返回备份文件路径。"""
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"源数据库不存在: {source_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"{source_path.stem}_{ts}.sqlite"

    # 用 sqlite3 的 backup API 在线备份
    src = sqlite3.connect(str(source_path))
    try:
        dst = sqlite3.connect(str(backup_path))
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # 清理过老的备份（仅清理匹配的 stem 模式）
    backups = sorted(
        backup_dir.glob(f"{source_path.stem}_*.sqlite"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[max_backups:]:
        old.unlink()
        print(f"  - 清理过期备份: {old.name}", file=sys.stderr)

    return backup_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="备份 SQLite 数据库")
    parser.add_argument(
        "--db",
        action="append",
        required=True,
        help="要备份的数据库路径（可多次指定）",
    )
    parser.add_argument(
        "--backup-dir",
        default="./backups",
        help="备份目录（默认 ./backups）",
    )
    parser.add_argument(
        "--max-backups",
        type=int,
        default=7,
        help="每个数据库保留的最大备份数（默认 7）",
    )
    args = parser.parse_args(argv)

    backup_dir = Path(args.backup_dir)
    print(
        f"[backup_sqlite] {datetime.now(UTC).isoformat()} 开始备份 {len(args.db)} 个数据库"
    )

    for db_path in args.db:
        try:
            path = backup_database(db_path, backup_dir, args.max_backups)
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"[backup_sqlite] ✓ {db_path} -> {path} ({size_mb:.2f} MB)")
        except Exception as e:
            print(f"[backup_sqlite] ✗ {db_path} 失败: {e}", file=sys.stderr)
            return 1

    print("[backup_sqlite] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
