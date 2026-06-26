# 风格因子覆盖 v2 归因与修复报告

- run_at: `2026-06-26`
- 输入库: `/tmp/fle-run/source.sqlite`
- before 输出库: `/tmp/fle-run/output-v1-style-stability.sqlite`
- after 输出库: `/tmp/fle-run/output-v2-style-lookup-fix.sqlite`
- 因子库: `data/stock_factors.sqlite`
- 批处理参数: `--source funddata --style-history-periods 4`
- processed: **14407**

## 1. 结论

本轮针对 `style_exposure_low_coverage=6932` 的排查发现，最大缺口不是先扩充 `stock_factors.sqlite`，而是一个多期暴露选择逻辑 bug：

- 多期暴露使用同一份最新因子快照作为稳定“透镜”，所以 4 个报告期的 `as_of_date` 通常相同。
- 引擎当前期风格标签使用 `_factor_exposure_lookup` 按 `as_of_date` 选“最新”暴露。
- batch 计算多期暴露时按报告期降序计算，后写入的历史期在 `as_of_date` 相同的情况下覆盖最新期。
- 结果：当前风格标签大量误用了**最老报告期**的覆盖率，历史/退市/旧代码更多，导致 `style_exposure_low_coverage` 被显著放大。

修复后，当前风格标签按 `report_date` 优先选择最新报告期；稳定性分析仍使用完整多期序列。

## 2. 标签变化

| label_code | before | after | Δ |
|---|---:|---:|---:|
| `style_exposure_low_coverage` | 6932 | **1358** | **-5574** |
| `style_exposure_observe` | 2383 | 1172 | -1211 |
| `style_pending_rule_definition` | 664 | 6768 | +6104 |
| `deep_value` | 58 | 320 | +262 |
| `quality_growth` | 3 | 19 | +16 |
| `dividend_steady` | 131 | 718 | +587 |
| `style_stable` | 5065 | 5065 | 0 |
| `style_drift` | 1542 | 1542 | 0 |
| `style_recent_shift` | 1659 | 1659 | 0 |

解释：

- 当前期覆盖率不再被历史期覆盖率污染，因此 5574 只基金从“覆盖不足”恢复为可解释状态。
- `style_pending_rule_definition` 大幅上升，是因为这些基金现在覆盖率达标，但三类正式风格阈值未命中；这是比“低覆盖”更准确的业务状态。
- 三类稳定性标签不变，说明修复只影响“当前期风格标签选用哪一期 exposure”，不改变 `_style_history_periods` 的多期序列判定。

## 3. stock_factors.sqlite 覆盖现状

`data/stock_factors.sqlite` 当前为 2026-06-23 单日横截面：

| 指标 | 数量 |
|---|---:|
| stock_factor_values distinct stocks | 5866 |
| 持仓中 distinct stock_code | 8524 |
| 持仓中合法 A 股形态代码 | 6030 |
| 合法 A 股被因子库覆盖 | 5360 |
| 合法 A 股覆盖率 | **88.9%** |
| 合法 A 股缺失 | 670 |

缺失的 670 只里包含大量历史/退市/港股左补 0 形成的 6 位数字代码（例如 `000083 信和置业`、`000270 粤海投资/KIA CORP`），不能简单等同于“当前 A 股因子库缺口”。

持仓代码还存在 2494 个非标准/海外代码，典型样本：

- `00MSFT` 微软
- `00AAPL` 苹果
- `00NVDA` 英伟达
- `0GOOGL` 谷歌-A
- `0BRK_B` 伯克希尔哈撒韦-B

这说明后续还需要把“海外/港股因子不适用 A 股风格体系”和“真实 A 股因子缺失”区分开，而不是统一落到 `style_exposure_low_coverage`。

## 4. 修复内容

代码修复位于 [backend/app/label_engine/engine.py](file:///Users/xiongjiali/Desktop/code/fund-label-engine/backend/app/label_engine/engine.py)：

- `_factor_exposure_lookup` 从只按 `as_of_date` 选最新，改为按 `(report_date, as_of_date)` 选最新。
- 因为多期暴露的 `as_of_date` 常相同，`report_date` 才是当前期风格标签应使用的主排序键。
- 新增 `_factor_exposure_key`，兼容没有 `report_date` 的旧 exposure 行（回退到 `as_of_date`）。

回归测试位于 [backend/tests/test_label_engine.py](file:///Users/xiongjiali/Desktop/code/fund-label-engine/backend/tests/test_label_engine.py)：

- `test_factor_exposure_lookup_uses_latest_report_date_when_as_of_ties`
- 构造两个报告期 `as_of_date` 相同、历史期覆盖低、最新期覆盖高的 exposure 序列，验证引擎输出最新期正式风格标签而非误打 `style_exposure_low_coverage`。

测试结果：`backend/tests/test_label_engine.py` **41 passed**。

## 5. 剩余问题与下一步

`style_exposure_low_coverage` 修复后仍有 1358 只，下一步应分两类处理：

1. **真实 A 股因子缺失**：补全 670 个合法 A 股形态代码中仍可从东财/交易所获取的当前成分，尤其是北交所与少数旧代码。
2. **非 A 股/海外持仓口径**：对 `00MSFT`、`00AAPL`、`0GOOGL` 等海外代码，以及港股左补 0 的代码，新增市场识别与 `style_exposure_scope_not_applicable` 类标签，避免继续把“风格体系不适用”误报为“因子库缺失”。

优先级建议：先做第 2 类口径治理，再补真实 A 股因子。因为当前因子库对合法 A 股的覆盖已达 88.9%，而低覆盖余量里仍混有较多海外/历史代码噪声。
