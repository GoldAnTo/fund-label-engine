# Phase1 基准收益补齐与相对基准标签结果

- run_id: `f267ac1c83454dbea7b6d6b7a1c64d6c`
- processed: **142**
- 数据源：东方财富指数 K 线 `push2his.eastmoney.com/api/qt/stock/kline/get`
- 补齐范围：严格映射的指数型基金跟踪标的，以及可解析为「沪深300/中证500/中证800 + 上证国债」的复合基准。

## 1. 补齐结果

- 成功映射并写入 `benchmark_returns`：**30 只**
- 仍缺基准收益：**112 只**

| fund_code | fund_name | benchmark | rows | relative labels |
|---|---|---|---:|---|
| `000006` | 西部利得量化成长混合A | 中证50075% | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000017` | 财通可持续混合 | 沪深30080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000031` | 华夏复兴混合A | 沪深30080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000061` | 华夏盛世混合 | 沪深30080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000176` | 嘉实沪深300指数研究增强A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000241` | 宝盈核心优势混合C | 沪深30065%+上证国债35% | 243 | `beta_low, tracking_error_high` |
| `000251` | 工银金融地产混合A | 沪深30080%+上证国债20% | 243 | `beta_low, tracking_error_high` |
| `000311` | 景顺长城沪深300指数增强A | 沪深300 | 243 | `alpha_positive, beta_low, excess_return_strong, tracking_error_high` |
| `000312` | 华安沪深300增强A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000313` | 华安沪深300增强C | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000362` | 国泰聚信价值优势混合A | 沪深30080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000363` | 国泰聚信价值优势混合C | 沪深30080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000390` | 华商优势行业混合A | 沪深30055%+上证国债45% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000398` | 华富灵活配置混合A | 沪深30060%+上证国债40% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000458` | 英大领先回报A | 沪深30050%+上证国债50% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000459` | 英大领先回报B | 沪深30050%+上证国债50% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000478` | 建信中证500指数增强A | 中证500 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000512` | 国泰沪深300指数增强A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000520` | 上银新兴价值成长混合A | 沪深30050%+上证国债50% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000527` | 南方新优享灵活配置混合A | 沪深30060%+上证国债40% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000541` | 华商创新成长混合发起式A | 沪深30055%+上证国债45% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000550` | 广发新动力混合A | 沪深30080% | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000554` | 南方中国梦灵活配置混合A | 沪深30060%+上证国债40% | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000595` | 嘉实泰和混合 | 沪深30070%+上证国债30% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000601` | 华宝创新优选混合 | 中证80080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000609` | 华商新量化混合A | 沪深30060%+上证国债40% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000612` | 华宝生态中国混合A | 中证80080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000654` | 华商新锐产业混合 | 沪深30065%+上证国债35% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000656` | 前海开源沪深300指数A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `100038` | 富国沪深300指数增强A | 沪深300 | 243 | `alpha_positive, information_ratio_high` |

## 2. 相对基准标签分布

| label_code | status | fund_count |
|---|---|---:|
| `benchmark_data_missing` | observe | 112 |
| `beta_low` | active | 29 |
| `tracking_error_high` | active | 29 |
| `alpha_positive` | active | 28 |
| `excess_return_strong` | active | 18 |
| `information_ratio_high` | active | 18 |

## 3. 解读

- 30 只指数/指数增强/可解析复合基准基金已经可以产出正式相对基准特征。
- 112 只仍保留 `benchmark_data_missing`，原因是基准文本包含尚未接入的债券/行业/主题指数或存款利率成分。
- `tracking_error_high` 对指数增强/指数基金是有解释意义的；主动权益基金应等待复合基准收益补齐后再计算。
- 目前没有用文本 benchmark 硬近似主动基金基准，避免制造伪 Alpha。

## 4. 下一步

1. 解析复合 benchmark 权重，例如 `沪深300*80% + 中债综合*20%`。
2. 补债券指数、行业指数、主题指数、存款利率等收益序列。
3. 生成复合 `benchmark_returns` 后，再覆盖主动权益基金。
