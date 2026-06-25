# 相对基准覆盖补齐 v2 报告

- run_id: `253e68518ab04f939b34648b1013ae42`
- run_at: `2026-06-25T08:11:16+00:00`
- rule_version: `v1`
- 输入库: `/tmp/fle-run/source.sqlite`
- 输出库: `/tmp/fle-run/output-v1-benchmark-v2.sqlite`
- processed: **142**

## 1. 覆盖结果

| status | fund_count |
|---|---:|
| `benchmark_returns_missing` | 103 |
| `benchmark_returns_ready` | 39 |

说明：v2 解析出 45 只候选，但本轮外部指数源对部分指数断连，实际写入 benchmark_returns 的基金数为 36。

## 2. 组件解析审计

| status | reason | component_count | fund_count |
|---|---|---:|---:|
| `resolved` | `index` | 203 | 129 |
| `unresolved` | `unsupported_component_or_missing_source` | 58 | 55 |
| `resolved` | `synthetic` | 8 | 8 |
| `resolved` | `synthetic_fixed_return` | 6 | 6 |
| `unresolved` | `benchmark_missing` | 1 | 1 |

## 3. 相对基准标签分布

| label_code | status | fund_count |
|---|---|---:|
| `benchmark_data_missing` | observe | 103 |
| `beta_low` | active | 38 |
| `tracking_error_high` | active | 38 |
| `alpha_positive` | active | 35 |
| `excess_return_strong` | active | 26 |
| `information_ratio_high` | active | 24 |

## 4. 主要剩余缺口

| component_name | reason | component_count | fund_count |
|---|---|---:|---:|
| 中债综合指数 | `unsupported_component_or_missing_source` | 21 | 21 |
| 中债总指数 | `unsupported_component_or_missing_source` | 12 | 12 |
| 中国债券总指数 | `unsupported_component_or_missing_source` | 6 | 6 |
| 中债-综合指数 | `unsupported_component_or_missing_source` | 2 | 2 |
| 标普中国债券指数 | `unsupported_component_or_missing_source` | 2 | 2 |
|  | `benchmark_missing` | 1 | 1 |
| (指年,评价时按期间折算) | `unsupported_component_or_missing_source` | 1 | 1 |
| MSCI中国A股指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 上证高端装备60指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中债-国债总(1-3年)指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中债-总指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中债国债总指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中国债券综合指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中证A500指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中证军工指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中证服务业指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 中证财通中国可持续发展100(ECPIESG)指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 国证航天军工指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 富时中国A600指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 新华富时中国A200指数 | `unsupported_component_or_missing_source` | 1 | 1 |
| 新华富时中国国债指数 | `unsupported_component_or_missing_source` | 1 | 1 |

## 5. 结论

- v2 已新增 `benchmark_components` 审计表，142 只全部有组件解析记录。
- 可解析候选从上一轮 33 只提升到 45 只。
- 实际 `benchmark_returns` 覆盖为 36 只，主要受上证国债、行业/主题指数、港股指数行情源断连或缺失影响。
- 中债综合、中证全债、中国债券总指数、中证综合债等仍没有可靠日收益源，继续保留缺口，不做上证国债替代。
- 下一步若要冲到 80-100 只，关键不是继续写解析规则，而是接入稳定债券指数和行业/主题指数日收益源。
