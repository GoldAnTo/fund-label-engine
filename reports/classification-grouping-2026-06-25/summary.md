# 基金分类和分组真实跑批验证

## 跑批信息

- 运行时间：2026-06-25
- run_id：`1a58c59883b8471f86ed76a59409e826`
- 输出库：`/tmp/fle-run/output.sqlite`
- 状态：`succeeded`
- 处理基金数：161

## 结果规模

| 项目 | 数量 |
|---|---:|
| 基金数 | 161 |
| 标签结果 | 1329 |
| 标签计算状态 | 3542 |
| 分类结果 | 644 |
| 分组结果 | 744 |

## 分类分布

| 维度 | 分类 | 基金数 |
|---|---|---:|
| asset_class | equity_related | 161 |
| management_style | active | 142 |
| management_style | passive_index | 19 |
| calculation_eligibility | label_ready | 138 |
| calculation_eligibility | data_gap | 23 |
| style_clarity | style_pending | 147 |
| style_clarity | style_clear | 14 |

## 分组分布

| 分组类型 | 分组 | 基金数 |
|---|---|---:|
| scope | phase1_active_equity_scope | 161 |
| data_quality | label_ready_pool | 138 |
| data_quality | data_gap_pool | 23 |
| business | active_equity_candidate_pool | 77 |
| business | passive_tool_pool | 19 |
| style | style_factor_ready_pool | 161 |
| style | quality_growth_group | 9 |
| style | deep_value_group | 3 |
| style | dividend_steady_group | 3 |
| risk_watch | industry_concentration_watch | 137 |
| risk_watch | high_return_high_drawdown_watch | 13 |

## 结论

分类和分组链路已经能在真实基金数据上跑通：每只基金都有身份分类，业务池也能解释为什么进入对应池子。当前最有价值的输出是把 161 只基金拆成主动权益候选池、被动指数工具池、数据缺口池和风格相关分组，后续前端可以直接按这些池子筛选。

## 下一步

- 固定 5-10 只样例基金，导出每只基金的标签、证据、未触发原因、无法计算原因、分类、分组。
- 对 `data_gap_pool` 的 23 只基金做缺口归因，决定是补 NAV、补持仓穿透，还是从第一版清单剔除。
- 对 `industry_concentration_watch` 的 137 只基金检查阈值是否过宽，避免观察池过大。
- 对风格组的 14 只基金抽样核对股票因子，确认 `quality_growth_group`、`deep_value_group`、`dividend_steady_group` 的解释是否符合投研直觉。
