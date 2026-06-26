"""Fetch and persist fund operation fee structures.

This script fills the specific fee rows the label engine needs:
``fee_type='运作费用'`` with ``管理费率`` and ``托管费率`` (and optional
``销售服务费率``). It treats placeholder rows such as ``场内ETF-无费率信息``
as missing evidence and writes only source-backed fee rows.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger("fetch_fund_fees")

OPERATION_FEE = "运作费用"
OPERATION_FEE_CONDITIONS = ("管理费率", "托管费率", "销售服务费率")
SOURCE = "eastmoney.fund_fee_page"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_fund_code(value: str) -> str:
    match = re.search(r"\d{6}", str(value))
    if not match:
        raise ValueError(f"fund code must contain 6 digits: {value!r}")
    return match.group(0)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).strip())
    return "" if text.lower() in {"", "-", "--", "---", "nan", "暂无数据"} else text


def _rate_to_decimal(value: Any) -> float | None:
    text = _clean_text(value)
    if "%" not in text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    return float(match.group(0)) / 100


def _fee_indicator_alias(value: Any) -> str:
    text = _clean_text(value)
    aliases = {
        "认购费率（前端）": "认购费率",
        "认购费率（后端）": "认购费率",
        "申购费率（前端）": "申购费率",
        "申购费率（后端）": "申购费率",
        "赎回费率（前端）": "赎回费率",
        "赎回费率（后端）": "赎回费率",
    }
    return aliases.get(text, text)


class _EastmoneyFeeParser(HTMLParser):
    def __init__(self, wanted: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._wanted = wanted
        self._in_title = False
        self._title_parts: list[str] = []
        self._pending_title = ""
        self._table_title = ""
        self._in_table = False
        self._in_cell = False
        self._cell_parts: list[str] = []
        self._row: list[str] | None = None
        self.tables: list[tuple[str, list[list[str]]]] = []
        self._current_rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag.lower() == "h4" and "t" in attrs_dict.get("class", "").split():
            self._in_title = True
            self._title_parts = []
            return
        if tag.lower() == "table" and self._pending_title:
            title = _fee_indicator_alias(self._pending_title)
            if not self._wanted or title in self._wanted:
                self._in_table = True
                self._table_title = title
                self._current_rows = []
            self._pending_title = ""
            return
        if self._in_table and tag.lower() == "tr":
            self._row = []
            return
        if self._in_table and self._row is not None and tag.lower() in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_cell:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "h4" and self._in_title:
            self._pending_title = _clean_text("".join(self._title_parts))
            self._in_title = False
            return
        if self._in_table and self._in_cell and lower in {"td", "th"}:
            if self._row is not None:
                self._row.append(_clean_text("".join(self._cell_parts)))
            self._in_cell = False
            self._cell_parts = []
            return
        if self._in_table and lower == "tr":
            if self._row and any(self._row):
                self._current_rows.append(self._row)
            self._row = None
            return
        if self._in_table and lower == "table":
            self.tables.append((self._table_title, self._current_rows))
            self._in_table = False
            self._table_title = ""
            self._current_rows = []


def _is_header_row(row: list[str]) -> bool:
    if any("%" in cell for cell in row):
        return False
    header_cells = {
        "费用类别",
        "费率",
        "费用",
        "项目",
        "名称",
        "条件或名称",
        "适用金额",
        "适用期限",
        "原费率",
        "优惠费率",
    }
    return any(cell in header_cells for cell in row)


def _row_to_fee_rows(title: str, header: list[str] | None, row: list[str]) -> list[dict[str, Any]]:
    if header and len(header) == len(row):
        by_header = dict(zip(header, row, strict=False))
        condition = _clean_text(
            by_header.get("费用类别")
            or by_header.get("项目")
            or by_header.get("名称")
            or by_header.get("条件或名称")
            or by_header.get("适用金额")
            or by_header.get("适用期限")
            or row[0]
        )
        fee_text = _clean_text(
            by_header.get("费率")
            or by_header.get("费用")
            or by_header.get("原费率")
            or by_header.get("赎回费率")
            or (row[1] if len(row) > 1 else "")
        )
        discount_text = _clean_text(
            by_header.get("优惠费率")
            or by_header.get("天天基金优惠费率")
            or by_header.get("天天基金优惠费率-银行卡购买")
            or by_header.get("天天基金优惠费率-活期宝购买")
        )
        return [_fee_row(title, condition, fee_text, discount_text)]

    rows: list[dict[str, Any]] = []
    for index in range(0, len(row) - 1, 2):
        rows.append(_fee_row(title, row[index], row[index + 1], ""))
    return rows


def _fee_row(
    fee_type: str,
    condition: Any,
    fee_text: Any,
    discount_text: Any,
) -> dict[str, Any]:
    return {
        "fee_type": _fee_indicator_alias(fee_type),
        "condition_name": _clean_text(condition),
        "fee": _rate_to_decimal(fee_text),
        "fee_text": _clean_text(fee_text),
        "discount_fee": _rate_to_decimal(discount_text),
        "discount_fee_text": _clean_text(discount_text),
        "source": SOURCE,
    }


def parse_eastmoney_fee_page(
    html: str,
    *,
    indicators: list[str] | tuple[str, ...] = (OPERATION_FEE,),
) -> list[dict[str, Any]]:
    """Parse Eastmoney fund fee HTML into normalized fee rows."""
    wanted = {_fee_indicator_alias(item) for item in indicators}
    parser = _EastmoneyFeeParser(wanted)
    parser.feed(html)

    rows: list[dict[str, Any]] = []
    for title, table_rows in parser.tables:
        header: list[str] | None = None
        for row in table_rows:
            if _is_header_row(row):
                header = row
                continue
            for fee_row in _row_to_fee_rows(title, header, row):
                if not fee_row["condition_name"]:
                    continue
                if not fee_row["fee_text"] and not fee_row["discount_fee_text"]:
                    continue
                rows.append(fee_row)
    return rows


def fetch_eastmoney_fee_page(code: str, *, timeout: float = 20.0) -> str:
    fund_code = _normalize_fund_code(code)
    url = f"https://fundf10.eastmoney.com/jjfl_{fund_code}.html"
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed public data URL
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _fund_universe_table(conn: sqlite3.Connection) -> str:
    if _table_exists(conn, "fund_profiles"):
        return "fund_profiles"
    if _table_exists(conn, "funds"):
        return "funds"
    raise ValueError("source DB must contain fund_profiles or funds")


def select_operation_fee_targets(
    conn: sqlite3.Connection,
    *,
    codes: list[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    """Select funds missing management or custody operation fee rows."""
    table = _fund_universe_table(conn)
    params: list[Any] = []
    where = ""
    if codes:
        normalized = [_normalize_fund_code(code) for code in codes]
        placeholders = ",".join("?" for _ in normalized)
        where = f"WHERE u.fund_code IN ({placeholders})"
        params.extend(normalized)
    limit_sql = " LIMIT ?" if limit is not None else ""
    if limit is not None:
        params.append(limit)

    sql = f"""
        WITH universe AS (
            SELECT fund_code FROM {table}
        )
        SELECT u.fund_code
        FROM universe u
        LEFT JOIN fee_structures fs
          ON fs.fund_code = u.fund_code
         AND fs.fee_type = ?
         AND fs.condition_name IN ('管理费率', '托管费率')
         AND fs.fee IS NOT NULL
        {where}
        GROUP BY u.fund_code
        HAVING
            SUM(CASE WHEN fs.condition_name = '管理费率' THEN 1 ELSE 0 END) = 0
            OR SUM(CASE WHEN fs.condition_name = '托管费率' THEN 1 ELSE 0 END) = 0
        ORDER BY u.fund_code
        {limit_sql}
    """
    return [
        row[0]
        for row in conn.execute(sql, [OPERATION_FEE, *params]).fetchall()
    ]


def _resolve_coverage_run_id(
    conn: sqlite3.Connection,
    run_id: str | None,
) -> str:
    if run_id:
        return run_id
    if _table_exists(conn, "label_runs"):
        row = conn.execute(
            """
            SELECT run_id
            FROM label_runs
            ORDER BY run_at DESC, run_id DESC
            LIMIT 1
            """
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT run_id
            FROM fund_run_coverage
            GROUP BY run_id
            ORDER BY run_id DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise ValueError("coverage DB does not contain any runs")
    return str(row[0])


def select_fee_only_gap_codes(
    coverage_db_path: str | Path,
    *,
    run_id: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Select funds whose only failed coverage field is fee_structure."""
    with sqlite3.connect(coverage_db_path) as conn:
        if not _table_exists(conn, "fund_run_coverage"):
            raise ValueError("coverage DB must contain fund_run_coverage")
        resolved_run_id = _resolve_coverage_run_id(conn, run_id)
        params: list[Any] = [resolved_run_id]
        limit_sql = " LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        sql = f"""
            WITH missing AS (
                SELECT fund_code, field
                FROM fund_run_coverage
                WHERE run_id = ?
                  AND present = 0
            )
            SELECT fund_code
            FROM missing
            GROUP BY fund_code
            HAVING COUNT(*) = 1
               AND MAX(field) = 'fee_structure'
            ORDER BY fund_code
            {limit_sql}
        """
        return [row[0] for row in conn.execute(sql, params).fetchall()]


def upsert_fee_rows(
    conn: sqlite3.Connection,
    fund_code: str,
    rows: list[dict[str, Any]],
) -> int:
    code = _normalize_fund_code(fund_code)
    fetched_at = _utc_now()
    operation_rows = [
        row
        for row in rows
        if row.get("fee_type") == OPERATION_FEE
        and row.get("condition_name") in OPERATION_FEE_CONDITIONS
    ]
    conn.executemany(
        """
        INSERT INTO fee_structures (
            fund_code, fee_type, condition_name, fee, source, fetched_at,
            fee_text, discount_fee, discount_fee_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fund_code, fee_type, condition_name) DO UPDATE SET
            fee=excluded.fee,
            source=excluded.source,
            fetched_at=excluded.fetched_at,
            fee_text=excluded.fee_text,
            discount_fee=excluded.discount_fee,
            discount_fee_text=excluded.discount_fee_text
        """,
        [
            (
                code,
                row.get("fee_type", ""),
                row.get("condition_name", ""),
                row.get("fee"),
                row.get("source", ""),
                fetched_at,
                row.get("fee_text", ""),
                row.get("discount_fee"),
                row.get("discount_fee_text", ""),
            )
            for row in operation_rows
        ],
    )
    return len(operation_rows)


@dataclass
class BackfillStats:
    attempted: int = 0
    with_rows: int = 0
    rows_upserted: int = 0
    failed: int = 0


def backfill_operation_fees(
    db_path: str | Path,
    *,
    codes: list[str] | None = None,
    limit: int | None = None,
    timeout: float = 20.0,
    sleep_seconds: float = 0.0,
    dry_run: bool = False,
    concurrency: int = 1,
) -> BackfillStats:
    stats = BackfillStats()
    with sqlite3.connect(db_path, timeout=30) as conn:
        targets = select_operation_fee_targets(conn, codes=codes, limit=limit)
        logger.info("targeting %d funds missing operation fees", len(targets))
        if concurrency <= 1:
            iterator = (_fetch_one(code, timeout=timeout) for code in targets)
        else:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=concurrency)
            futures = [
                executor.submit(_fetch_one, code, timeout=timeout)
                for code in targets
            ]
            iterator = (future.result() for future in concurrent.futures.as_completed(futures))

        try:
            for code, rows, error in iterator:
                stats.attempted += 1
                if error is not None:
                    logger.warning("fee backfill failed for %s: %s", code, error)
                    stats.failed += 1
                elif rows:
                    stats.with_rows += 1
                    if not dry_run:
                        stats.rows_upserted += upsert_fee_rows(conn, code, rows)
                        conn.commit()
                else:
                    stats.failed += 1
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
        finally:
            if concurrency > 1:
                executor.shutdown(wait=True)
    return stats


def _fetch_one(
    code: str,
    *,
    timeout: float,
) -> tuple[str, list[dict[str, Any]], Exception | None]:
    try:
        html = fetch_eastmoney_fee_page(code, timeout=timeout)
        rows = parse_eastmoney_fee_page(html, indicators=[OPERATION_FEE])
        return code, rows, None
    except Exception as exc:  # noqa: BLE001 - caller records per-fund failure
        return code, [], exc


def _read_codes_file(path: str | None) -> list[str]:
    if not path:
        return []
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _dedupe_codes(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for code in codes:
        normalized = _normalize_fund_code(code)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill fund operation fees.")
    parser.add_argument("--db", required=True, help="fundData-style SQLite source DB")
    parser.add_argument("--code", action="append", default=[], help="Fund code to fetch")
    parser.add_argument("--codes-file", default=None, help="Optional fund-code list")
    parser.add_argument(
        "--coverage-db",
        default=None,
        help="Optional label output DB used with --fee-only-gaps",
    )
    parser.add_argument("--coverage-run-id", default=None, help="Coverage run_id to inspect")
    parser.add_argument(
        "--fee-only-gaps",
        action="store_true",
        help="Target funds whose only failed coverage field is fee_structure",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit target funds")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Pause between funds")
    parser.add_argument("--concurrency", type=int, default=1, help="Parallel HTTP fetches")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse without writing")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(name)s: %(message)s",
    )
    codes = [*args.code, *_read_codes_file(args.codes_file)]
    if args.fee_only_gaps:
        if not args.coverage_db:
            parser.error("--fee-only-gaps requires --coverage-db")
        fee_only_codes = select_fee_only_gap_codes(
            args.coverage_db,
            run_id=args.coverage_run_id,
            limit=args.limit,
        )
        logger.info("selected %d fee-only gap funds from coverage DB", len(fee_only_codes))
        codes.extend(fee_only_codes)
        limit = None
    else:
        limit = args.limit
    codes = _dedupe_codes(codes) or None
    stats = backfill_operation_fees(
        args.db,
        codes=codes,
        limit=limit,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
        dry_run=args.dry_run,
        concurrency=args.concurrency,
    )
    logger.info(
        "DONE attempted=%d with_rows=%d rows_upserted=%d failed=%d dry_run=%s",
        stats.attempted,
        stats.with_rows,
        stats.rows_upserted,
        stats.failed,
        args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
