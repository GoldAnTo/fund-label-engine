# Phase1 基准收益补齐与相对基准标签结果

- run_id: `dd7e3cb0436d48e9903e17801d6b8d98`
- processed: **142**
- 数据源：东方财富指数 K 线 `push2his.eastmoney.com/api/qt/stock/kline/get`
- 补齐范围：仅对可严格映射的指数型基金跟踪标的补 1Y 日收益。

## 1. 补齐结果

- 成功映射并写入 `benchmark_returns`：**8 只**
- 仍缺基准收益：**134 只**

| fund_code | fund_name | benchmark | rows | relative labels |
|---|---|---|---:|---|
| `000176` | 嘉实沪深300指数研究增强A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000311` | 景顺长城沪深300指数增强A | 沪深300 | 243 | `alpha_positive, beta_low, excess_return_strong, tracking_error_high` |
| `000312` | 华安沪深300增强A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000313` | 华安沪深300增强C | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000478` | 建信中证500指数增强A | 中证500 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000512` | 国泰沪深300指数增强A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000656` | 前海开源沪深300指数A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `100038` | 富国沪深300指数增强A | 沪深300 | 243 | `alpha_positive, information_ratio_high` |

## 2. 相对基准标签分布

| label_code | status | fund_count |
|---|---|---:|
| `benchmark_data_missing` | observe | 134 |
| `alpha_positive` | active | 8 |
| `beta_low` | active | 7 |
| `tracking_error_high` | active | 7 |
| `excess_return_strong` | active | 1 |
| `information_ratio_high` | active | 1 |

## 3. 解读

- 8 只指数/指数增强基金已经可以产出正式相对基准特征。
- 134 只仍保留 `benchmark_data_missing`，原因是主动权益基金大多是复合基准，不能直接用单一指数近似。
- `tracking_error_high` 对指数增强/指数基金是有解释意义的；主动权益基金应等待复合基准收益补齐后再计算。
- 目前没有用文本 benchmark 硬近似主动基金基准，避免制造伪 Alpha。

## 4. 下一步

1. 解析复合 benchmark 权重，例如 `沪深300*80% + 中债综合*20%`。
2. 补债券指数、行业指数、主题指数、存款利率等收益序列。
3. 生成复合 `benchmark_returns` 后，再覆盖主动权益基金。
