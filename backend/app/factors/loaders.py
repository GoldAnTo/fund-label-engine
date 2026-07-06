"""SMB / HML 因子加载器。

真实的 SMB / HML 日度数据通常需要付费源（中证/标普/Cn-info），
本项目默认依赖 fundData 真库，本模块提供一个默认 loader：

- SMB 默认从 benchmark_component_returns 读取代理（不存在则返回 None，回退 CAPM）
- HML 同上

接入真实数据源时，只需替换 default_load_smb / default_load_hml 的实现。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# 在 fundData 真库中，约定 SMB / HML 存为 component_code = "FACTOR_SMB" / "FACTOR_HML"
FACTOR_SMB_CODE = "FACTOR_SMB"
FACTOR_HML_CODE = "FACTOR_HML"


def load_smb_returns(source_db: str | Path) -> list[float] | None:
    """从 benchmark_component_returns 读取 SMB 日收益。"""
    return _load_factor_returns(source_db, FACTOR_SMB_CODE)


def load_hml_returns(source_db: str | Path) -> list[float] | None:
    """从 benchmark_component_returns 读取 HML 日收益。"""
    return _load_factor_returns(source_db, FACTOR_HML_CODE)


def _load_factor_returns(source_db: str | Path, code: str) -> list[float] | None:
    """读取因子 component 的日收益（按 trade_date 升序）。"""
    db_path = Path(source_db)
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                "SELECT trade_date, daily_return FROM benchmark_component_returns "
                "WHERE component_code = ? ORDER BY trade_date",
                (code,),
            ).fetchall()
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    return [float(r[1]) for r in rows]
