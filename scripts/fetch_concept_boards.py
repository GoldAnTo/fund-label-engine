"""抓取东方财富概念板块及其成分股，存入 factor cache DB。

数据源：东方财富公开 push2 接口（无 cookie / JS）。
- 概念板块列表: fs=m:90+t:3（约 300+ 个板块）
- 板块成分股:   fs=b:BK0xxx

写入到 ``data/stock_factors.sqlite`` 的 ``concept_board_stocks`` 表。

用法：
    # 抓取全部概念板块
    python scripts/fetch_concept_boards.py --db data/stock_factors.sqlite

    # 只抓取名称包含关键词的板块（减少请求量）
    python scripts/fetch_concept_boards.py --db data/stock_factors.sqlite --filter AI,芯片,创新药,消费,红利,新能源,游戏

    # 只抓取指定板块代码
    python scripts/fetch_concept_boards.py --db data/stock_factors.sqlite --codes BK0800,BK0473
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS concept_board_stocks (
    concept_code TEXT NOT NULL,
    concept_name TEXT NOT NULL,
    stock_code   TEXT NOT NULL,
    stock_name   TEXT NOT NULL,
    PRIMARY KEY (concept_code, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_concept_board_stocks_stock
    ON concept_board_stocks (stock_code);
CREATE INDEX IF NOT EXISTS idx_concept_board_stocks_name
    ON concept_board_stocks (concept_name);
"""


def _curl_get(url: str, retries: int = 3) -> dict:
    """用 curl 调东方财富接口，返回 JSON dict。"""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            out = subprocess.run(
                ["curl", "-s", "--max-time", "25", "-A", "Mozilla/5.0", url],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            if not out.strip():
                raise ValueError("empty body")
            return json.loads(out)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2 + attempt * 2)
    assert last_exc is not None
    raise last_exc


def fetch_concept_board_list() -> list[dict[str, str]]:
    """获取全部概念板块列表。

    返回: [{"code": "BK0800", "name": "人工智能"}, ...]
    """
    url = (
        "http://push2.eastmoney.com/api/qt/clist/get"
        "?fs=m:90+t:3"
        "&fields=f12,f14"
        "&pn=1&pz=500"
    )
    data = _curl_get(url)
    if not data or data.get("data") is None:
        return []
    rows = data["data"].get("diff", []) or []
    return [
        {"code": r.get("f12", ""), "name": r.get("f14", "")}
        for r in rows
        if r.get("f12") and r.get("f14")
    ]


def fetch_board_stocks(board_code: str) -> list[dict[str, str]]:
    """获取某概念板块的成分股列表。

    返回: [{"code": "300308", "name": "中际旭创"}, ...]
    """
    url = (
        f"http://push2.eastmoney.com/api/qt/clist/get"
        f"?fs=b:{board_code}"
        f"&fields=f12,f14"
        f"&pn=1&pz=500"
    )
    data = _curl_get(url)
    if not data or data.get("data") is None:
        return []
    rows = data["data"].get("diff", []) or []
    return [
        {"code": r.get("f12", ""), "name": r.get("f14", "")}
        for r in rows
        if r.get("f12") and r.get("f14")
    ]


def filter_boards(
    boards: list[dict[str, str]],
    keywords: str | None,
    codes: str | None,
) -> list[dict[str, str]]:
    """按关键词或板块代码过滤。"""
    if not keywords and not codes:
        return boards

    result = boards
    if keywords:
        kws = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        result = [
            b for b in result
            if any(kw in b["name"].lower() for kw in kws)
        ]
    if codes:
        code_set = {c.strip() for c in codes.split(",") if c.strip()}
        result = [b for b in result if b["code"] in code_set]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取东方财富概念板块及成分股")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 数据库路径")
    parser.add_argument(
        "--filter",
        default=None,
        help="按名称关键词过滤板块（逗号分隔，如 AI,芯片,创新药）",
    )
    parser.add_argument(
        "--codes",
        default=None,
        help="只抓取指定板块代码（逗号分隔，如 BK0800,BK0473）",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="每次请求间隔秒数（避免被限流）",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 建表
    with sqlite3.connect(db_path) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()

    # 1. 获取板块列表
    print("正在获取概念板块列表...", flush=True)
    boards = fetch_concept_board_list()
    print(f"共 {len(boards)} 个概念板块", flush=True)

    # 过滤
    boards = filter_boards(boards, args.filter, args.codes)
    print(f"过滤后 {len(boards)} 个板块待抓取", flush=True)

    if not boards:
        print("没有匹配的板块，退出")
        return 0

    # 2. 逐个抓取成分股
    total_stocks = 0
    with sqlite3.connect(db_path) as conn:
        for i, board in enumerate(boards):
            code = board["code"]
            name = board["name"]
            try:
                stocks = fetch_board_stocks(code)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{i+1}/{len(boards)}] {name}({code}) 失败: {exc}", flush=True)
                time.sleep(args.delay)
                continue

            if stocks:
                conn.executemany(
                    "INSERT OR REPLACE INTO concept_board_stocks "
                    "(concept_code, concept_name, stock_code, stock_name) "
                    "VALUES (?, ?, ?, ?)",
                    [(code, name, s["code"], s["name"]) for s in stocks],
                )
                conn.commit()

            total_stocks += len(stocks)
            print(
                f"  [{i+1}/{len(boards)}] {name}({code}): {len(stocks)} 只成分股",
                flush=True,
            )
            time.sleep(args.delay)

    # 3. 统计
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM concept_board_stocks"
        ).fetchone()[0]
        board_count = conn.execute(
            "SELECT COUNT(DISTINCT concept_code) FROM concept_board_stocks"
        ).fetchone()[0]

    print(f"\n完成: {board_count} 个板块, {count} 条成分股记录")
    print(f"数据库: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
