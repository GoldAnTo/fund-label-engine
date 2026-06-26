# 全量权益解释层审计与阈值校准报告

- run_id: `dcce7dcd84ef4345add2a342d8be266d`
- 输出库: `/tmp/fle-run/output-equity-contribution-full.sqlite`
- 源库: `/tmp/fle-run/source-v5.sqlite`，因子库: `data/stock_factors.sqlite`
- 处理基金数: 14407，命中贡献行: 496040
- 配套明细报告: [equity_style_contributions_full_dcce7dcd.md](./equity_style_contributions_full_dcce7dcd.md)

## 0. 本轮先修的一个真实 Bug

全量 batch 第一次跑直接被验证 gate 拦下：

```
batch.py: error: equity factor validation failed: missing equity style contributions for 015558/deep_value
```

**根因**：多期模式（`--style-history-periods 2`）下，基金级因子暴露会逐期聚合，
风格标签可能来自历史报告期；但贡献明细此前只用了「最新持仓期」的持仓/因子。
当最新期不命中、标签来自历史期时，贡献明细为空 → 标签与解释层报告期对不上。

**修复**：抽取 `_collect_period_inputs(repo, fund, style_history_periods)`，让
`_compute_exposures` 和新的 `_compute_equity_contributions` 共用同一份逐期持仓/因子。
015558 修复后在 2024-09-30 期生成 79 条 deep_value + 64 条 dividend_steady 贡献明细，
与标签报告期一致。重跑全量 14407 只全部通过 gate。

> 结论：验证 gate 在第一轮全量就抓到了真实语义不一致，价值已经体现。

## 1. 全市场标签分布

| 风格标签 | 成标签基金数 | 有贡献基金数 | 命中率 |
| --- | ---: | ---: | ---: |
| deep_value 深度价值 | 320 | 9257 | 3.5% |
| quality_growth 质量成长 | 19 | 8913 | 0.2% |
| dividend_steady 红利稳健 | 718 | 9258 | 7.8% |

观察：
- **quality_growth 仅 19 只**，明显偏少。8913 只基金有质量成长贡献股票，但只有 19 只
  能把权重累计到 50%。这说明要么阈值偏严，要么成长股因子覆盖不足，导致成长票贡献被稀释。
- **dividend_steady 718 只最多**，是 deep_value 的 2 倍多。

## 2. 风格重叠分析（核心发现）

| 标签组合 | 重叠基金数 |
| --- | ---: |
| deep_value ∩ dividend_steady | 226 |
| deep_value ∩ quality_growth | 0 |
| quality_growth ∩ dividend_steady | 0 |
| 三者同时 | 0 |

**deep_value ∩ dividend_steady = 226，占 deep_value 标签（320）的 71%。**

即：被打深度价值的基金里，七成同时被打红利稳健。这正是计划里担心的重叠。
进一步看金融主导度（用红利贡献股票名称启发式判断银行/保险/证券）：

- 226 只重叠基金中，红利贡献里金融占比 ≥ 60% 的有 48 只（21%）。
- Top 重叠基金几乎全是**银行 ETF**（512700/512820/515290/159887…），
  deep_value 命中股票 100% 是银行股（招行、兴业、工行…）。

结论：deep_value 和 dividend_steady 的重叠**主要由银行/保险蓝筹驱动**，这在金融上是合理的
（银行股本就是低 PB + 高股息），但当前两个标签无法区分「金融低估」与「泛深度价值」。

## 3. 样本复核（语义对不对）

### 强样本（标签最强）
| 基金 | 名称 | 风格 | 复核判断 |
| --- | --- | --- | --- |
| 512700 | 银行ETF南方 | deep_value(100%) + dividend_steady | ✅ 合理，纯银行持仓低 PB 高股息 |
| 159887 | 银行ETF富国 | deep_value + dividend_steady | ✅ 合理，同上 |
| 001382 | 易方达国企改革混合 | dividend_steady(91%) | ⚠️ 持仓是茅台/五粮液/分众，更像消费蓝筹而非红利 |
| 000522 | 华润元大信息传媒科技混合A | quality_growth(59.7%) | ✅ 持仓中际旭创/沪电股份等光通信成长股，合理 |

### 反直觉样本（重点）
| 基金 | 名称 | 现象 | 判断 |
| --- | --- | --- | --- |
| 159843 | 食品饮料ETF招商 | 被判 dividend_steady | ⚠️ 茅台股息率 4.2%、五粮液 7.7% 确实 ≥3%，规则命中正确，但「食品饮料ETF=红利」违反投研直觉 |
| 001382 | 易方达国企改革混合 | 红利稳健 91% | ⚠️ 白酒蓝筹高股息被算进红利，同上问题 |
| 009710/005290 | 诺德系灵活配置 | 红利贡献 ≥50% 却未成标签 | ✅ 合理，多期风格不稳定/覆盖率门槛拦下，符合预期 |

### 报告口径提醒（非 bug）
明细报告「Top 20 基金」用的是**贡献命中权重**排序（满足风格条件的股票持仓和），
而最终标签由**基金级 `*_weight` 暴露**决定，两者口径不同。例如 000522 出现在
deep_value 命中里，但它的 `deep_value_weight=0`，真实标签是 quality_growth。
解读 Top 表时要以 `fund_factor_exposures` 为准。

## 4. 阈值校准建议

> 原则：先确认语义可靠再扩量。以下建议**不立即改**，需你拍板。

### 4.1 dividend_steady 股息率阈值偏松（优先级最高）
- 现状：`dividend_steady_yield_min = 3%`，把茅台/五粮液等消费蓝筹也算红利。
- 建议候选：
  - 提高到 4%~5%，过滤掉「高股息消费蓝筹」，让红利更接近银行/煤炭/公用事业本意；
  - 或叠加行业约束：红利稳健要求金融/能源/公用事业等高股息行业占比。
- 验证方式：改阈值后重算，看 159843 这类食饮 ETF 是否退出 dividend_steady。

### 4.2 deep_value 与 dividend_steady 重叠（计划已预判）
- 现状：71% 的 deep_value 同时是 dividend_steady，主要是银行股。
- 建议候选（按计划拆分）：
  - `high_dividend_financial` 金融高股息：deep_value ∩ dividend_steady 且金融占比高；
  - `broad_deep_value` 泛深度价值：deep_value 且金融占比低；
  - 保留 deep_value/dividend_steady 作为底层因子，新增组合标签做区分。
- 数据支撑：48/226 金融占比 ≥60%，可先用 60% 作为金融主导阈值试拆。

### 4.3 quality_growth 命中过少（需诊断）
- 现状：仅 19 只成标签，8913 只有贡献但累计不到 50%。
- 可能原因：成长因子（roe + revenue_growth 双条件）太严，或成长股因子覆盖率低
  导致权重被稀释。
- 建议：先看 quality_growth 临界未成标签 Top（48%~50% 一批，如 012617/000845），
  判断是「真的不够成长」还是「因子缺失稀释」，再决定是否放宽到单条件或降低权重阈值。

## 5. 下一步建议顺序

1. 先按 4.1 调 dividend_steady 阈值并重算，确认食饮 ETF 退出红利（语义校准）。
2. 再评估 4.2 是否拆分金融/泛价值标签。
3. 诊断 4.3 quality_growth 偏少根因。
4. **以上语义校准通过后**，再继续补 9032 只 fee-only 缺口、扩大 label_ready_pool。

> 即：先把权益标签语义钉死，再放量。当前重叠和阈值问题若不先解决，
> 放量会把「食饮=红利」「银行=深度价值且红利」这类偏差成倍放大。
