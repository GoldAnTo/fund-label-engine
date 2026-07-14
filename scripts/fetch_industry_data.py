"""抓取申万行业分类数据，写入 SQLite 数据库。

用 akshare 获取申万一级行业分类及其成分股，存入 sw_industry_stocks 表，
供 IndustryDB 加载使用。

表结构:
    sw_industry_stocks(
        industry_code TEXT,      -- 行业代码
        industry_name TEXT,      -- 行业名称
        industry_level INTEGER,  -- 行业层级（1=一级, 2=二级, 3=三级）
        stock_code TEXT,         -- 股票代码
        stock_name TEXT          -- 股票名称
    )

用法:
    python scripts/fetch_industry_data.py [db_path]

    默认写入 /tmp/fle-p0/industry.sqlite

依赖:
    pip install akshare
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# 处理代理问题：akshare 内部用 requests，避免走代理导致连接失败
os.environ.setdefault("NO_PROXY", "*")

DEFAULT_DB = "/tmp/fle-p0/industry.sqlite"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sw_industry_stocks (
    industry_code TEXT NOT NULL,
    industry_name TEXT NOT NULL,
    industry_level INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    PRIMARY KEY (industry_code, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_sw_industry_stocks_name
    ON sw_industry_stocks (industry_name);
CREATE INDEX IF NOT EXISTS idx_sw_industry_stocks_code
    ON sw_industry_stocks (stock_code);
"""


def fetch_industry_data(db_path: str) -> None:
    """抓取申万行业分类和成分股，写入数据库。

    依次抓取一、二、三级行业及其成分股。某级行业抓取失败时跳过并继续。
    """
    import akshare as ak

    # 确保目录存在
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(CREATE_TABLE_SQL)
        conn.execute("DELETE FROM sw_industry_stocks")
        conn.commit()

        total_rows = 0

        # --- 一级行业 ---
        print("抓取申万一级行业...")
        sw_first = ak.sw_index_first_info()
        for _, row in sw_first.iterrows():
            ind_code = str(row["行业代码"])
            ind_name = str(row["行业名称"])
            print(f"  一级 {ind_code} {ind_name}")
            try:
                stocks = ak.index_component_sw(symbol=ind_code)
                for _, s in stocks.iterrows():
                    conn.execute(
                        "INSERT OR REPLACE INTO sw_industry_stocks "
                        "VALUES (?, ?, 1, ?, ?)",
                        (ind_code, ind_name, str(s["股票代码"]), str(s["股票名称"])),
                    )
                    total_rows += 1
                conn.commit()
            except Exception as e:
                print(f"    WARN: {e}")

        # --- 二级行业 ---
        print("抓取申万二级行业...")
        try:
            sw_second = ak.sw_index_second_info()
            for _, row in sw_second.iterrows():
                ind_code = str(row["行业代码"])
                ind_name = str(row["行业名称"])
                print(f"  二级 {ind_code} {ind_name}")
                try:
                    stocks = ak.index_component_sw(symbol=ind_code)
                    for _, s in stocks.iterrows():
                        conn.execute(
                            "INSERT OR REPLACE INTO sw_industry_stocks "
                            "VALUES (?, ?, 2, ?, ?)",
                            (ind_code, ind_name, str(s["股票代码"]), str(s["股票名称"])),
                        )
                        total_rows += 1
                    conn.commit()
                except Exception as e:
                    print(f"    WARN: {e}")
        except Exception as e:
            print(f"  二级行业抓取失败，跳过: {e}")

        # --- 三级行业 ---
        print("抓取申万三级行业...")
        try:
            sw_third = ak.sw_index_third_info()
            for _, row in sw_third.iterrows():
                ind_code = str(row["行业代码"])
                ind_name = str(row["行业名称"])
                print(f"  三级 {ind_code} {ind_name}")
                try:
                    stocks = ak.index_component_sw(symbol=ind_code)
                    for _, s in stocks.iterrows():
                        conn.execute(
                            "INSERT OR REPLACE INTO sw_industry_stocks "
                            "VALUES (?, ?, 3, ?, ?)",
                            (ind_code, ind_name, str(s["股票代码"]), str(s["股票名称"])),
                        )
                        total_rows += 1
                    conn.commit()
                except Exception as e:
                    print(f"    WARN: {e}")
        except Exception as e:
            print(f"  三级行业抓取失败，跳过: {e}")

        print(f"\n完成：共写入 {total_rows} 条记录到 {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    fetch_industry_data(target)
