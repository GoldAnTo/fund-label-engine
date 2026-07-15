"""数据源抽象层：支持 akshare -> efinance -> baostock 三级回退。

借鉴 FundCrawler 的智能速率控制和指数退避重试，
借鉴 Hedge Fund Tracker 的多级回退策略。

用法::

    from scripts.data_source import DataSourceManager
    mgr = DataSourceManager()
    holdings = mgr.get_fund_holdings("161725", "2024")
    nav = mgr.get_fund_nav("161725")
    valuation = mgr.get_stock_valuation("000001")
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ── 速率控制器（借鉴 FundCrawler RateControl） ──────────────────────────

@dataclass
class RateController:
    """动态速率控制：根据失败率自动调整请求间隔。

    - 失败率超过 threshold 时，间隔翻倍（最高 max_interval）
    - 成功率恢复后，间隔逐步缩小（最低 min_interval）
    """

    min_interval: float = 0.3
    max_interval: float = 5.0
    threshold: float = 0.3          # 失败率阈值
    window_size: int = 20           # 滑动窗口大小
    _interval: float = field(init=False)
    _results: list[bool] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._interval = self.min_interval

    def wait(self) -> None:
        time.sleep(self._interval + random.uniform(0, 0.1))

    def record(self, success: bool) -> None:
        self._results.append(success)
        if len(self._results) > self.window_size:
            self._results.pop(0)
        if len(self._results) >= 5:
            fail_rate = 1 - sum(self._results) / len(self._results)
            if fail_rate > self.threshold:
                self._interval = min(self._interval * 1.5, self.max_interval)
                logger.warning("速率控制：失败率 %.0f%%，间隔升至 %.1fs", fail_rate * 100, self._interval)
            elif fail_rate < self.threshold * 0.3:
                self._interval = max(self._interval * 0.8, self.min_interval)


# ── 指数退避重试 ──────────────────────────────────────────────────────

def retry_with_backoff(
    func: Any,
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs: Any,
) -> Any:
    """指数退避重试：每次失败后等待 base_delay * 2^attempt 秒。"""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 0.5), max_delay)
                logger.warning("第 %d 次失败: %s，%.1fs 后重试", attempt + 1, exc, delay)
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ── 数据源基类 ────────────────────────────────────────────────────────

class DataSource:
    """数据源基类，子类需实现具体获取方法。"""

    name: str = "base"

    def __init__(self) -> None:
        self.rate = RateController()

    def get_fund_holdings(self, fund_code: str, year: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_fund_info(self, fund_code: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_fund_nav(self, fund_code: str, limit: int = 60) -> pd.DataFrame:
        raise NotImplementedError

    def get_stock_valuation(self, stock_code: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_fund_list(self) -> pd.DataFrame:
        raise NotImplementedError


# ── AKShare 数据源（主力） ────────────────────────────────────────────

class AkshareSource(DataSource):
    name = "akshare"

    def __init__(self) -> None:
        super().__init__()
        os_env_setup()
        import akshare as ak
        self._ak = ak

    def get_fund_holdings(self, fund_code: str, year: str) -> pd.DataFrame:
        self.rate.wait()
        df = retry_with_backoff(self._ak.fund_portfolio_hold_em, symbol=fund_code, date=year)
        self.rate.record(True)
        return df

    def get_fund_info(self, fund_code: str) -> dict[str, Any]:
        self.rate.wait()
        df = retry_with_backoff(self._ak.fund_individual_basic_info_xq, symbol=f"SZ{fund_code}" if fund_code.startswith("1") or fund_code.startswith("0") else f"SH{fund_code}")
        self.rate.record(True)
        return df.to_dict("records")[0] if len(df) > 0 else {}

    def get_fund_nav(self, fund_code: str, limit: int = 60) -> pd.DataFrame:
        self.rate.wait()
        df = retry_with_backoff(self._ak.fund_open_fund_info_em, symbol=fund_code, indicator="单位净值走势")
        self.rate.record(True)
        return df.tail(limit)

    def get_stock_valuation(self, stock_code: str) -> pd.DataFrame:
        self.rate.wait()
        df = retry_with_backoff(self._ak.stock_zh_valuation_baidu, symbol=stock_code, indicator="总市值", period="近一年")
        self.rate.record(True)
        return df

    def get_fund_list(self) -> pd.DataFrame:
        self.rate.wait()
        df = retry_with_backoff(self._ak.fund_name_em)
        self.rate.record(True)
        return df


# ── efinance 数据源（备份） ───────────────────────────────────────────

class EfinanceSource(DataSource):
    name = "efinance"

    def __init__(self) -> None:
        super().__init__()
        import efinance as ef
        self._ef = ef

    def get_fund_holdings(self, fund_code: str, year: str) -> pd.DataFrame:
        self.rate.wait()
        df = retry_with_backoff(self._ef.fund.get_invest_position, fund_code)
        self.rate.record(True)
        return df

    def get_fund_info(self, fund_code: str) -> dict[str, Any]:
        self.rate.wait()
        info = retry_with_backoff(self._ef.fund.get_base_info, fund_code)
        self.rate.record(True)
        return info if isinstance(info, dict) else {}

    def get_fund_nav(self, fund_code: str, limit: int = 60) -> pd.DataFrame:
        self.rate.wait()
        df = retry_with_backoff(self._ef.fund.get_quote_history, fund_code)
        self.rate.record(True)
        return df.tail(limit)

    def get_stock_valuation(self, stock_code: str) -> pd.DataFrame:
        """efinance 不直接提供 PE/PB 历史数据，返回空。"""
        return pd.DataFrame()

    def get_fund_list(self) -> pd.DataFrame:
        self.rate.wait()
        df = retry_with_backoff(self._ef.fund.get_realtime_estimate)
        self.rate.record(True)
        return df


# ── baostock 数据源（二级备份，仅股票估值） ──────────────────────────

class BaostockSource(DataSource):
    name = "baostock"

    def __init__(self) -> None:
        super().__init__()
        import baostock as bs
        self._bs = bs
        self._logged_in = False

    def _ensure_login(self) -> None:
        if not self._logged_in:
            self._bs.login()
            self._logged_in = True

    def get_stock_valuation(self, stock_code: str) -> pd.DataFrame:
        """baostock 提供 PE(TTM)/PB(MRQ) 日频数据，稳定性最好。"""
        self._ensure_login()
        code = _to_baostock_code(stock_code)
        self.rate.wait()
        rs = retry_with_backoff(
            self._bs.query_history_k_data_plus,
            code,
            "date,code,peTTM,pbMRQ,psTTM,pcfNcfTTM",
            start_date=_recent_start_date(),
            end_date=_today_str(),
            frequency="d",
        )
        self.rate.record(True)
        data_list: list[list[str]] = []
        while (rs.error_code == "0") and rs.next():
            data_list.append(rs.get_row_data())
        if not data_list:
            return pd.DataFrame()
        df = pd.DataFrame(data_list, columns=rs.fields)
        for col in ["peTTM", "pbMRQ", "psTTM", "pcfNcfTTM"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def get_fund_holdings(self, fund_code: str, year: str) -> pd.DataFrame:
        """baostock 不支持基金持仓。"""
        return pd.DataFrame()

    def get_fund_info(self, fund_code: str) -> dict[str, Any]:
        return {}

    def get_fund_nav(self, fund_code: str, limit: int = 60) -> pd.DataFrame:
        return pd.DataFrame()

    def get_fund_list(self) -> pd.DataFrame:
        return pd.DataFrame()


# ── 数据源管理器（多级回退） ──────────────────────────────────────────

class DataSourceManager:
    """多级回退数据源管理器。

    依次尝试 akshare -> efinance -> baostock，
    任一源成功即返回，全部失败才抛异常。
    """

    def __init__(self, sources: list[DataSource] | None = None) -> None:
        if sources is None:
            sources = []
            for cls in (AkshareSource, EfinanceSource, BaostockSource):
                try:
                    sources.append(cls())
                    logger.info("数据源 %s 初始化成功", cls.name)
                except Exception as exc:
                    logger.warning("数据源 %s 初始化失败: %s", cls.name, exc)
        self.sources = sources

    def _try_sources(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for source in self.sources:
            method = getattr(source, method_name, None)
            if method is None:
                continue
            try:
                result = method(*args, **kwargs)
                if result is not None and not (isinstance(result, pd.DataFrame) and result.empty):
                    logger.debug("通过 %s 获取 %s 成功", source.name, method_name)
                    return result
                logger.debug("数据源 %s 返回空数据，尝试下一个", source.name)
            except Exception as exc:
                last_exc = exc
                logger.warning("数据源 %s.%s 失败: %s", source.name, method_name, exc)
        if last_exc:
            raise last_exc
        return pd.DataFrame()

    def get_fund_holdings(self, fund_code: str, year: str) -> pd.DataFrame:
        return self._try_sources("get_fund_holdings", fund_code, year)

    def get_fund_info(self, fund_code: str) -> dict[str, Any]:
        return self._try_sources("get_fund_info", fund_code)

    def get_fund_nav(self, fund_code: str, limit: int = 60) -> pd.DataFrame:
        return self._try_sources("get_fund_nav", fund_code, limit)

    def get_stock_valuation(self, stock_code: str) -> pd.DataFrame:
        return self._try_sources("get_stock_valuation", stock_code)

    def get_fund_list(self) -> pd.DataFrame:
        return self._try_sources("get_fund_list")


# ── 辅助函数 ──────────────────────────────────────────────────────────

def os_env_setup() -> None:
    """避免环境代理干扰 akshare 接口。"""
    import os
    os.environ.setdefault("NO_PROXY", "*")


def _to_baostock_code(stock_code: str) -> str:
    """将普通股票代码转为 baostock 格式。"""
    code = stock_code.strip()
    if code.startswith(("sh", "sz", "SH", "SZ")):
        return f"{code[:2].lower()}.{code[2:]}"
    if code.startswith(("6", "5", "9")):
        return f"sh.{code}"
    return f"sz.{code}"


def _today_str() -> str:
    from datetime import date
    return date.today().strftime("%Y-%m-%d")


def _recent_start_date(days: int = 365) -> str:
    from datetime import date, timedelta
    return (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
