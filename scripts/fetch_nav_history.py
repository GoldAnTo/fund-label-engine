"""分页拉取 Eastmoney F10 NAV 历史，写入 nav_history 表。

为什么需要这个脚本：
- fundData 自带的 ``batch-sync`` 调底层 ``client.nav_history(per=N)``，但 Eastmoney F10
  API 实际把 per 截到 20，所以一次只拿到 ~20 行；而 1Y 收益风险标签的 gate 需要
  >=180 个 daily_growth_rate 样本。
- 这里用 page=1,2,3,... 轮询直到一页 <20 条，可以完整拿到指定区间的 NAV。

数据源：
    https://fundf10.eastmoney.com/F10DataApi.aspx?type=lsjz&code={code}&page={p}&per=20
    &sdate={start}&edate={end}
返回内容里嵌套 `var apidata={ content: "<table>...", records: N, pages: P, ... };`，
正则解析 `<tr><td>nav_date</td><td>unit_nav</td><td>...</td><td>daily_growth_rate</td>`。

写入：
    INSERT OR REPLACE INTO nav_history
        (fund_code, nav_date, unit_nav, daily_growth_rate, source, fetched_at)

用法：
    python scripts/fetch_nav_history.py \
        --fund-code 000199 \
        --start-date 2025-06-24 --end-date 2026-06-24

    python scripts/fetch_nav_history.py \
        --codes-file data/phase1_fund_codes.txt \
        --start-date 2025-06-01 --end-date 2026-06-23
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEFAULT_DB = (
    Path.home() / ".cache" / "fund-data" / "releases"
    / "2026-06-03T214600Z" / "fund_data_query.sqlite"
)

# Eastmoney F10 NAV 接口模板
_NAV_URL = "https://fundf10.eastmoney.com/F10DataApi.aspx"

_TR_PATTERN = re.compile(
    r"<tr><td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?"
    r"<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>",
    re.DOTALL,
)
_APIDATA_PATTERN = re.compile(r"var apidata=\{(.*?)\};", re.DOTALL)
_CONTENT_PATTERN = re.compile(r'content:"(.*?)"', re.DOTALL)


def _fetch_one_fund(
    code: str, start: str, end: str, max_pages: int = 100
) -> list[dict]:
    """对一只基金分页拉满指定区间的 NAV。"""
    all_rows: list[dict] = []
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode(
            {
                "type": "lsjz",
                "code": code,
                "page": page,
                "per": 20,
                "sdate": start,
                "edate": end,
            }
        )
        url = f"{_NAV_URL}?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://fundf10.eastmoney.com/",
                },
            )
            resp = urllib.request.urlopen(req, timeout=10)
            text = resp.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - 单页失败终止该基金
            sys.stderr.write(f"  [ERR] {code} page={page}: {exc}\n")
            break

        m = _APIDATA_PATTERN.search(text)
        if not m:
            break
        content_m = _CONTENT_PATTERN.search(m.group(1))
        if not content_m:
            break
        html = content_m.group(1)
        rows = _TR_PATTERN.findall(html)
        if not rows:
            break
        for row in rows:
            growth_text = row[3].replace("%", "").strip()
            try:
                daily_growth = float(growth_text) / 100.0 if growth_text else None
            except (ValueError, IndexError):
                daily_growth = None
            all_rows.append(
                {
                    "nav_date": row[0].strip(),
                    "unit_nav": row[1].strip(),
                    "daily_growth_rate": daily_growth,
                }
            )
        # 一页满 20 条就继续翻，否则到底
        if len(rows) < 20:
            break
        time.sleep(0.15)
    return all_rows


def _read_codes(path: str) -> list[str]:
    codes: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        code = line.strip()
        if code and not code.startswith("#"):
            codes.append(code)
    return codes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codes-file",
        help="每行一个 fund_code，要拉 NAV 的基金清单。",
    )
    parser.add_argument(
        "--fund-code",
        help="只拉一只基金，便于单基金标签测试。",
    )
    parser.add_argument(
        "--start-date", required=True, help="区间起点，例如 2025-06-01"
    )
    parser.add_argument(
        "--end-date", required=True, help="区间终点，例如 2026-06-23"
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"目标 SQLite（fundData cache DB），默认 {DEFAULT_DB}",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="并发线程数（HTTP 抓取），默认 4。",
    )
    args = parser.parse_args(argv)

    if bool(args.codes_file) == bool(args.fund_code):
        parser.error("必须且只能提供 --codes-file 或 --fund-code 之一。")
    codes = [args.fund_code] if args.fund_code else _read_codes(args.codes_file)
    code_source = args.fund_code if args.fund_code else args.codes_file
    sys.stderr.write(
        f"db: {args.db}\nfunds: {len(codes)} from {code_source}\n"
        f"range: {args.start_date} ~ {args.end_date}\n"
    )

    conn = sqlite3.connect(args.db)
    total = 0
    done = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(_fetch_one_fund, c, args.start_date, args.end_date): c
            for c in codes
        }
        for fut in as_completed(futures):
            code = futures[fut]
            done += 1
            try:
                rows = fut.result(timeout=120)
            except Exception as exc:  # noqa: BLE001 - 失败计数后继续
                sys.stderr.write(
                    f"[{done}/{len(codes)}] {code}: ERROR {exc}\n"
                )
                errors += 1
                continue
            if rows:
                for row in rows:
                    conn.execute(
                        "INSERT OR REPLACE INTO nav_history "
                        "(fund_code, nav_date, unit_nav, daily_growth_rate, "
                        " source, fetched_at) "
                        "VALUES (?, ?, ?, ?, 'eastmoney.paginated', datetime('now'))",
                        (
                            code,
                            row["nav_date"],
                            row["unit_nav"],
                            row["daily_growth_rate"],
                        ),
                    )
                conn.commit()
                total += len(rows)
            sys.stderr.write(
                f"[{done}/{len(codes)}] {code}: {len(rows)} rows, total={total}\n"
            )

    # 把 WAL pending 写回主库，避免后续拷贝看到旧快照
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    print(f"\nDone. total NAV rows upserted={total}, errors={errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
