# data_gap_pool 缺口归因报告

- 数据来源：source=`/tmp/fle-run/source.sqlite`，output=`/tmp/fle-run/output-v3-style-scope.sqlite`
- 基金总数：14407
- label_ready_pool：5287（36.7%）
- **data_gap_pool：9120（63.3%）**

## 1. 单字段失败计数

| 字段 | 失败基金数 | 占 gap_pool |
|---|---:|---:|
| `fee_structure` | 6638 | 72.8% |
| `stock_holdings` | 4272 | 46.8% |
| `equity_position` | 4272 | 46.8% |
| `industry_allocations` | 4261 | 46.7% |
| `nav_returns` | 554 | 6.1% |
| `fund_size` | 219 | 2.4% |
| `manager_tenure_years` | 201 | 2.2% |

> 注意：单字段计数会重叠（一只基金可能多字段失败），合计 > gap_pool 总数。

## 2. 字段组合失败（互斥桶）

| 组合 | 基金数 | 占 gap_pool |
|---|---:|---:|
| fee_structure | 4758 | 52.2% |
| equity_position, industry_allocations, stock_holdings | 2210 | 24.2% |
| equity_position, fee_structure, industry_allocations, stock_holdings | 1507 | 16.5% |
| equity_position, fee_structure, industry_allocations, manager_tenure_years, nav_returns, stock_holdings | 147 | 1.6% |
| equity_position, fund_size, industry_allocations, nav_returns, stock_holdings | 119 | 1.3% |
| equity_position, industry_allocations, nav_returns, stock_holdings | 86 | 0.9% |
| equity_position, fee_structure, fund_size, industry_allocations, nav_returns, stock_holdings | 83 | 0.9% |
| equity_position, fee_structure, industry_allocations, nav_returns, stock_holdings | 80 | 0.9% |
| manager_tenure_years | 24 | 0.3% |
| fee_structure, manager_tenure_years | 23 | 0.3% |
| fee_structure, nav_returns | 20 | 0.2% |
| nav_returns | 14 | 0.2% |
| equity_position, stock_holdings | 9 | 0.1% |
| equity_position, fee_structure, stock_holdings | 8 | 0.1% |
| industry_allocations | 8 | 0.1% |

## 3. 根因分析

### 3.1 fee_structure 单独缺失（4758 只）

- fee_structures 表有行：4758
- 其中只有 `申购费率`、缺 `运作费用`（管理费/托管费）：**4758 只**
- 根因：数据采集只抓了申购费率，未抓运作费用类。
- 修复方向：补 `运作费用` 采集（fee_type=运作费用，condition_name=管理费率/托管费率）。

### 3.2 持仓三件套缺失（2210 只）

- stock_holdings + industry_allocations + equity_position 同时缺失
- stock_holdings 表零行：2210 只
- fund_type 分布：

| fund_type | 数量 |
|---|---:|
| 指数型-股票 | 1553 |
| 混合型-偏股 | 490 |
| 混合型-灵活 | 90 |
| 股票型 | 77 |

- 根因：持仓数据从未采集（非加载 bug，stock_holdings 表无行）。
- 修复方向：补持仓采集；其中指数型股票基金（被动）可考虑走 ETF 成分股替代路径。

### 3.3 fee + 持仓双重缺失（1507 只）

- 同时缺运作费用和持仓数据，需两路同时修。

### 3.4 nav_returns 单独缺失（14 只）

- 极小量，多为混合型基金净值未采集。

## 4. 可执行优先级

| 优先级 | 修复项 | 受益基金 | gap_pool 降幅 | 难度 |
|---|---|---:|---:|---|
| P0 | 补 `运作费用` 采集（管理费/托管费） | 4758 | 52.2% | 低（单表补抓） |
| P1 | 补持仓采集（指数型优先走 ETF 成分股） | 2210 | 24.2% | 中 |
| P2 | 补 nav_returns 采集 | 14 | 0.2% | 低 |
| — | fee+持仓双重缺失 | 1507 | — | 随 P0+P1 一起解决 |

### 预期效果

- 完成 P0（运作费用采集）：gap_pool 9120 → 4362
- 完成 P0+P1：gap_pool → 645
- 完成 P0+P1+P2：gap_pool → ~631
