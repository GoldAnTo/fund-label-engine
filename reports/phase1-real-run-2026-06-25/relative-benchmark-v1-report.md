# 相对基准标签 v1 最小闭环报告

- run_id: `ffc30eed772c48f490397afc712cb4aa`
- processed: **142**
- 结论：代码层已支持相对基准计算，但当前真实 fundData 只有 `benchmark/tracking_target` 文本字段，没有可对齐的基准收益序列。

## 1. 已补的能力

当 `FundInput.benchmark_returns` 存在且样本满足 1Y/3Y 窗口时，引擎会计算：

- `annualized_excess_return`：年化超额收益
- `tracking_error`：年化跟踪误差
- `information_ratio`：信息比率
- `alpha`：Alpha（零无风险利率近似）
- `beta`：Beta

并支持这些标签：

- `excess_return_strong`
- `information_ratio_high`
- `tracking_error_high`
- `alpha_positive`
- `beta_high`
- `beta_low`
- `benchmark_data_missing`（观察标签）

## 2. 当前真实数据结果

| label_code | status | fund_count |
|---|---|---:|
| `benchmark_data_missing` | observe | 142 |

- benchmark 相关 feature 数：**0**
- 说明：当前没有 `benchmark_returns` 表或同等可用数据，所以正式相对基准标签不会硬触发。

## 3. 无法计算原因

| reason_code | calculation_count | fund_count |
|---|---:|---:|
| `benchmark_data_missing` | 852 | 142 |

## 4. 下一步数据要求

要让相对基准标签正式可用，需要补一张可按基金对齐的基准日收益表，最小字段：

```text
benchmark_returns(
  fund_code TEXT,
  trade_date TEXT,
  daily_return REAL,
  benchmark_code TEXT,
  benchmark_name TEXT,
  source TEXT
)
```

其中 `fund_code + trade_date` 要能和基金 `nav_history` 对齐。

## 5. 建议

短期先保留 `benchmark_data_missing` 作为数据缺口标签；下一步优先做 benchmark 文本解析和指数行情补齐，而不是继续扩更多投研标签。
