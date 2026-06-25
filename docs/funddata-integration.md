# fundData 接入说明

## 本地验证路径

### 单库模式（简单）
结果表混写在同一个 SQLite 中：

```bash
python -m app.batch --db /path/to/fund_data.sqlite --source funddata
```

### 双库模式（推荐）
源库只读打开，结果写到独立的 output 库：

```bash
python -m app.batch \
  --source-db /path/to/fundData.sqlite \
  --output-db /path/to/label_results.sqlite \
  --source funddata
```

## 字段映射

| fundData 字段 | 引擎字段 | 说明 |
|---|---|---|
| `fund_profiles.fund_code` | `fund_code` | 基金代码 |
| `fund_profiles.fund_name` | `fund_name` | 基金名称 |
| `fund_profiles.fund_type` | `fund_type` | 基金类型 |
| `fund_profiles.asset_size` | `fund_size` | 基金规模，亿元 |
| `nav_history.daily_growth_rate` | `nav_returns` | 日收益率序列 |
| `stock_holdings.report_period` | `holding_report_date` | 持仓报告期 |
| `stock_holdings.net_value_ratio` | `stock_holdings.weight` | 股票持仓占净值比例 |
| `industry_allocations.report_period` | `industry_report_date` | 行业报告期 |
| `industry_allocations.industry_name` | `industry_allocations.industry` | 行业名称 |
| `industry_allocations.net_value_ratio` | `industry_allocations.weight` | 行业占净值比例 |
| `fund_manager_links.tenure_days` | `manager_tenure_years` | 用 `tenure_days / 365.25` 转换 |
| `fee_structures` 运作费用 | 费率字段 | 管理费率、托管费率、销售服务费率 |
| 最新股票持仓合计 | `equity_position` | fundData 暂无独立仓位表时的近似权益仓位 |

## 当前完整结果

单只基金 report 包含：

- `coverage`：数据覆盖率。
- `missing_fields`：缺失字段。
- `features`：收益风险、持仓、行业、经理、费率、规模特征。
- `labels`：基础标签、收益风险标签、持仓结构标签、风格边界标签。
- `evidence`：每个标签的指标值、阈值、来源和解释。
- `reviews`：人工复核记录。
- `summary`：标签数、特征数、证据数、缺失字段数、复核动作。

API：

```bash
GET /v1/runs/{run_id}/funds/{fund_code}/report
```

## 仍然缺失

- `fundData` 当前没有 `stock_factors` / `stock_labels`，所以不能输出正式高级风格标签。
- 当前权益仓位来自最新股票持仓合计，后续如果有正式仓位表，应优先使用正式仓位表。
- 当前收益风险特征使用可用净值窗口，不代表完整 1 年/3 年评价；后续需要按窗口和基准补齐。
- 双库模式下源库以 `mode=ro` 打开，引擎不会写源库；单库模式只建议在样例和开发时使用。
