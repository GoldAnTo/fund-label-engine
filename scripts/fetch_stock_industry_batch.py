"""批量拉取股票的行业分类，写入 stock_industry_map 表。

数据源：东财 F10 公司概况接口（emweb.securities.eastmoney.com），
返回个股的 EM2016 行业分类（东财行业，类似申万二级）。

该接口按股票代码逐只查询，每只约 0.3 秒，804 只持仓股票约需 4 分钟。

行业分组（sector_group）按 EM2016 行业关键词映射到 8 个大类：
- financial: 银行、非银金融、券商、保险
- energy_utility: 公用事业、电力、燃气、交通运输
- consumer: 食品饮料、家电、商贸、纺织、社服、美容、农业、轻工
- tech: 电子、计算机、通信、传媒、半导体、软件
- healthcare: 医药、生物、医疗
- cyclical: 钢铁、有色、煤炭、化工、石油、石化
- infrastructure: 建筑、机械、环保、综合
- other: 房地产、军工、汽车、电力设备、其他

用法：
    python scripts/fetch_stock_industry_batch.py \\
        --db data/stock_factors.sqlite \\
        --source-db ~/.cache/fund-data/releases/2026-06-03T214600Z/fund_data_query.sqlite \\
        --as-of-date 2026-06-26
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"

# 东财 EM2016 行业关键词 → sector_group 映射
# 按顺序匹配，命中即归类
SECTOR_KEYWORD_RULES: list[tuple[list[str], str]] = [
    # 金融
    (["银行", "券商", "保险", "多元金融", "非银金融"], "financial"),
    # 能源公用
    (["电力", "燃气", "水务", "环保", "公共交通", "港口", "高速", "铁路", "航运", "航空", "物流", "交通运输", "公用事业"], "energy_utility"),
    # 消费
    (["食品", "饮料", "白酒", "啤酒", "乳品", "调味", "家电", "小家电", "厨卫", "商贸", "零售", "纺织", "服装", "社服", "餐饮", "酒店", "旅游", "美容", "护理", "农业", "牧渔", "种植", "养殖", "轻工", "造纸", "包装", "家居", "文具", "日化"], "consumer"),
    # 科技
    (["电子", "半导体", "芯片", "集成电路", "消费电子", "光学", "光电子", "计算机", "软件", "IT服务", "通信", "传媒", "游戏", "影视", "广告", "出版", "互联网"], "tech"),
    # 医药
    (["医药", "生物", "医疗", "器械", "中药", "化学制药", "疫苗", "血液制品"], "healthcare"),
    # 周期
    (["钢铁", "有色", "煤炭", "化工", "石油", "石化", "塑料", "橡胶", "化纤", "建材", "玻璃", "水泥"], "cyclical"),
    # 基建
    (["建筑", "装饰", "机械", "设备", "综合", "工程咨询", "工程"], "infrastructure"),
]


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_industry_map (
    stock_code TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    industry_name TEXT NOT NULL,
    sector_group TEXT NOT NULL CHECK (
        sector_group IN (
            'financial',
            'energy_utility',
            'consumer',
            'tech',
            'healthcare',
            'cyclical',
            'infrastructure',
            'other'
        )
    ),
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    PRIMARY KEY (stock_code, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_stock_industry_map_sector
    ON stock_industry_map (sector_group, as_of_date);
"""


def classify_sector(industry_name: str) -> str:
    """把东财行业名映射到 sector_group。"""
    for keywords, sector in SECTOR_KEYWORD_RULES:
        for kw in keywords:
            if kw in industry_name:
                return sector
    return "other"


def get_holding_stock_codes(source_db: str) -> list[str]:
    """从 fundData 库读取所有基金的持仓股票代码。"""
    conn = sqlite3.connect(source_db)
    try:
        rows = conn.execute(
            "SELECT DISTINCT stock_code FROM stock_holdings WHERE stock_code IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows if row[0]]


def make_secid(stock_code: str) -> str:
    """根据股票代码前缀判断交易所，返回东财 secid 格式。"""
    if stock_code.startswith(("0", "3")):
        return f"SZ{stock_code}"
    return f"SH{stock_code}"


def fetch_stock_industry(stock_code: str) -> tuple[str, str] | None:
    """通过东财 F10 公司概况接口拉取 EM2016 行业分类。

    返回 (industry_name, sector_group)，失败返回 None。
    """
    secid = make_secid(stock_code)
    url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={secid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        jbzl = data.get("jbzl") or []
        if not jbzl:
            return None
        industry_name = jbzl[0].get("EM2016") or ""
        if not industry_name:
            return None
        sector_group = classify_sector(industry_name)
        return (industry_name, sector_group)
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument(
        "--source-db",
        default=str(
            Path.home()
            / ".cache/fund-data/releases/2026-06-03T214600Z/fund_data_query.sqlite"
        ),
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--source", default="eastmoney.em2016_industry")
    args = parser.parse_args()

    # 获取持仓股票代码
    stock_codes = get_holding_stock_codes(args.source_db)
    sys.stderr.write(f"Found {len(stock_codes)} holding stock codes\n")

    conn = sqlite3.connect(args.db)
    conn.executescript(CREATE_TABLE_SQL)

    # 已有映射的股票跳过（同 as_of_date）
    existing = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT stock_code FROM stock_industry_map WHERE as_of_date = ?",
            (args.as_of_date,),
        )
    }
    todo = [c for c in stock_codes if c not in existing]
    sys.stderr.write(f"Already mapped: {len(existing)}, to fetch: {len(todo)}\n")

    inserted = 0
    failed = 0
    for i, code in enumerate(todo):
        result = fetch_stock_industry(code)
        if result is None:
            failed += 1
            time.sleep(0.1)
            continue
        industry_name, sector_group = result
        try:
            conn.execute(
                "INSERT OR REPLACE INTO stock_industry_map "
                "(stock_code, industry_code, industry_name, sector_group, source, as_of_date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (code, code, industry_name, sector_group, args.source, args.as_of_date),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass

        if (i + 1) % 50 == 0:
            conn.commit()
            sys.stderr.write(
                f"  Progress: {i+1}/{len(todo)}, inserted={inserted}, failed={failed}\n"
            )
        time.sleep(0.2)

    conn.commit()

    # 统计分组分布
    rows = conn.execute(
        "SELECT sector_group, COUNT(*) FROM stock_industry_map GROUP BY sector_group ORDER BY COUNT(*) DESC"
    ).fetchall()
    conn.close()

    print(f"Inserted {inserted} industry mappings, failed {failed}")
    print("Sector distribution:")
    for sector, count in rows:
        print(f"  {sector}: {count}")


if __name__ == "__main__":
    main()
