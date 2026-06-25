# Phase1 基准收益补齐与相对基准标签结果

- run_id: `671a6917740844368a6d90ad3dd3748d`
- processed: **142**
- 数据源：东方财富指数 K 线 `push2his.eastmoney.com/api/qt/stock/kline/get`
- 补齐范围：严格映射的指数型基金跟踪标的、可解析的「权益指数 + 上证国债」复合基准，以及存款利率/固定收益率基准。

## 1. 补齐结果

- 成功映射并写入 `benchmark_returns`：**33 只**
- 仍缺基准收益：**109 只**

| fund_code | fund_name | benchmark | rows | relative labels |
|---|---|---|---:|---|
| `000006` | 西部利得量化成长混合A | 中证50075%+银行活期存款利率25% | 243 | `alpha_positive, beta_low, tracking_error_high` |
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
| `000433` | 安信鑫发优选混合A | 一年期存款利率+3.00%100% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000458` | 英大领先回报A | 沪深30050%+上证国债50% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000459` | 英大领先回报B | 沪深30050%+上证国债50% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000478` | 建信中证500指数增强A | 中证500 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000512` | 国泰沪深300指数增强A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000520` | 上银新兴价值成长混合A | 沪深30050%+上证国债50% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000527` | 南方新优享灵活配置混合A | 沪深30060%+上证国债40% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000530` | 招商丰盛稳定增长混合A | 一年期存款利率+3.00%100% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000541` | 华商创新成长混合发起式A | 沪深30055%+上证国债45% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000545` | 中邮核心竞争力灵活配置混合 | 一年期存款利率+2.00%100% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000554` | 南方中国梦灵活配置混合A | 沪深30060%+上证国债40% | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000595` | 嘉实泰和混合 | 沪深30070%+上证国债30% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000601` | 华宝创新优选混合 | 中证80080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000609` | 华商新量化混合A | 沪深30060%+上证国债40% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000612` | 华宝生态中国混合A | 中证80080%+上证国债20% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000654` | 华商新锐产业混合 | 沪深30065%+上证国债35% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `000656` | 前海开源沪深300指数A | 沪深300 | 243 | `alpha_positive, beta_low, tracking_error_high` |
| `000679` | 招商丰利灵活配置混合A | 一年期存款利率+3.00%100% | 243 | `alpha_positive, beta_low, excess_return_strong, information_ratio_high, tracking_error_high` |
| `100038` | 富国沪深300指数增强A | 沪深300 | 243 | `alpha_positive, information_ratio_high` |

## 2. 相对基准标签分布

| label_code | status | fund_count |
|---|---|---:|
| `benchmark_data_missing` | observe | 109 |
| `beta_low` | active | 32 |
| `tracking_error_high` | active | 32 |
| `alpha_positive` | active | 31 |
| `excess_return_strong` | active | 22 |
| `information_ratio_high` | active | 22 |

## 3. 解读

- 33 只指数/指数增强/可解析复合基准基金已经可以产出正式相对基准特征。
- 109 只仍保留 `benchmark_data_missing`，原因是基准文本包含尚未接入的中债/中证债券指数、行业/主题指数或港股指数。
- `tracking_error_high` 对指数增强/指数基金是有解释意义的；主动权益基金应等待复合基准收益补齐后再计算。
- 目前没有用文本 benchmark 硬近似主动基金基准，避免制造伪 Alpha。

## 4. 下一步

1. 优先寻找中债/中证债券指数的可用日收益源，覆盖 `中债综合`、`中证全债`、`中国债券总指数`。
2. 再接行业/主题指数和港股指数，覆盖医药、TMT、环保、红利、恒生等 benchmark。
3. 重跑后再评估 `alpha_positive`、`tracking_error_high` 等相对基准标签阈值是否过宽。
