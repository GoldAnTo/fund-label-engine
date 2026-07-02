# Portfolio v1 Acceptance Report

run_id: `50f9b72de7104761869dc3e86e8a36d2`
run_at: `2026-07-02T06:01:33+00:00`
rule_version: `v1`
total_count: 142

> 本报告是 product acceptance 用人话解释，不做评分或自动化决策。
> 每只基金附 alpha_1y / sharpe / IR / drawdown / 优化权重 / max cap，
> 由研究员在『Sign-off Checklist』小节做最终决定。

## Status Breakdown

| status | count |
| --- | ---: |
| eligible | 28 |
| review_required | 4 |
| observe | 110 |

draft.included_rows = 88
draft.excluded_rows = 54
optimized summary = {'total_weight_pct': 99.9996, 'optimized_funds': 88, 'capped_count': 0, 'method': 'cap_redistribute_v1'}
role suggestions generated = 4

## Eligible Funds (28) — Classified

counts: {'core': 9, 'satellite': 11, 'index_tool': 8}

| fund_code | sub_class | bucket | role | alpha_1y | sharpe | IR | vol | max_dd | max_cap | opt_w |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `000308` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | 143.73% | 5.13 | 2.65 | 29.79% | -13.75% | 6.0% | 2.13% |
| `000577` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha, style_quality_growth | 61.44% | 2.91 | 0.88 | 23.15% | -13.78% | 6.0% | 2.13% |
| `000136` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | 59.49% | 2.61 | 1.44 | 20.29% | -8.84% | 6.0% | 1.92% |
| `000006` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor | 46.97% | 2.99 | 0.10 | 14.83% | -9.09% | 8.0% | 1.24% |
| `000172` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha | 45.40% | 2.57 | 0.36 | 15.55% | -7.11% | 8.0% | 2.06% |
| `000457` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | 42.95% | 3.54 | 0.34 | 20.76% | -12.86% | 8.0% | 1.89% |
| `000520` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | 31.43% | 2.13 | 0.79 | 12.55% | -6.83% | 8.0% | 2.09% |
| `000279` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_deep_value | 10.66% | 1.10 | 0.83 | 10.92% | -8.66% | 8.0% | 2.26% |
| `000663` | core | core | active_equity_candidate, core_holding_candidate, defensive_anchor | 10.17% | 1.90 | -0.33 | 17.11% | -15.20% | 6.0% | 0.89% |
| `000017` | satellite | satellite | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | 295.51% | 6.71 | 5.03 | 40.16% | -14.85% | 3.0% | 1.68% |
| `000531` | satellite | satellite | defensive_anchor, satellite_alpha, style_quality_growth | 151.38% | 6.71 | 2.59 | 38.25% | -17.60% | 3.0% | 1.00% |
| `000404` | satellite | satellite | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | 143.42% | 5.63 | 1.89 | 38.08% | -17.15% | 3.0% | 1.85% |
| `000522` | satellite | satellite | active_equity_candidate, satellite_alpha, style_quality_growth | 132.22% | 4.22 | 0.18 | 44.25% | -20.21% | 1.0% | 0.03% |
| `000073` | satellite | satellite | defensive_anchor, satellite_alpha, style_quality_growth | 86.14% | 3.90 | 1.41 | 24.87% | -11.52% | 5.0% | 1.27% |
| `000219` | satellite | satellite | defensive_anchor, satellite_alpha | 39.76% | 2.36 | 1.92 | 15.65% | -7.85% | 5.0% | 1.24% |
| `000398` | satellite | satellite | defensive_anchor, satellite_alpha | 38.79% | 2.29 | 0.87 | 15.05% | -7.96% | 5.0% | 1.41% |
| `000433` | satellite | satellite | defensive_anchor, low_cost, satellite_alpha | 37.58% | 1.88 | 1.70 | 18.31% | -13.19% | 5.0% | 1.58% |
| `000573` | satellite | satellite | defensive_anchor, low_cost, satellite_alpha | 29.95% | 1.70 | 1.80 | 14.52% | -10.83% | 5.0% | 1.58% |
| `000566` | satellite | satellite | defensive_anchor | 12.70% | 1.60 | -0.91 | 21.41% | -14.84% | 5.0% | 0.38% |
| `000083` | satellite | satellite | active_equity_candidate | -13.09% | -1.06 | 0.20 | 13.04% | -22.47% | 1.0% | 0.03% |
| `000368` | index_tool | index_tool | defensive_anchor, index_tool, low_cost | 45.83% | 2.81 | 0.05 | 13.78% | -5.08% | 3.0% | 0.72% |
| `000311` | index_tool | index_tool | defensive_anchor, index_tool, low_cost, satellite_alpha | 43.17% | 2.56 | 0.34 | 14.82% | -7.33% | 3.0% | 1.37% |
| `000312` | index_tool | index_tool | defensive_anchor, index_tool, low_cost, satellite_alpha | 40.34% | 2.27 | 0.25 | 15.64% | -9.58% | 3.0% | 1.37% |
| `000313` | index_tool | index_tool | defensive_anchor, index_tool, satellite_alpha | 39.66% | 2.23 | 0.23 | 15.64% | -9.64% | 3.0% | 1.20% |
| `000656` | index_tool | index_tool | defensive_anchor, index_tool, low_cost | 37.80% | 2.27 | 0.17 | 14.55% | -7.16% | 3.0% | 0.72% |
| `000176` | index_tool | index_tool | defensive_anchor, index_tool, low_cost | 36.12% | 2.11 | 0.10 | 14.68% | -7.40% | 3.0% | 0.72% |
| `000512` | index_tool | index_tool | defensive_anchor, index_tool, low_cost | 29.92% | 1.77 | -0.09 | 14.17% | -7.87% | 3.0% | 0.72% |
| `000059` | index_tool | index_tool | index_tool, low_cost | -9.10% | -0.62 | 0.10 | 16.62% | -22.54% | 3.0% | 0.03% |

<details><summary>含 optimized weight 的扩展表（点击展开）</summary>

| fund_code | sub_class | opt_w | dry_run | max_cap | capped |
| --- | --- | ---: | ---: | ---: | --- |
| `000308` | core | 2.13% | 2.13% | 6.0% | ok |
| `000577` | core | 2.13% | 2.13% | 6.0% | ok |
| `000136` | core | 1.92% | 1.92% | 6.0% | ok |
| `000006` | core | 1.24% | 1.24% | 8.0% | ok |
| `000172` | core | 2.06% | 2.06% | 8.0% | ok |
| `000457` | core | 1.89% | 1.89% | 8.0% | ok |
| `000520` | core | 2.09% | 2.09% | 8.0% | ok |
| `000279` | core | 2.26% | 2.26% | 8.0% | ok |
| `000663` | core | 0.89% | 0.89% | 6.0% | ok |
| `000017` | satellite | 1.68% | 1.68% | 3.0% | ok |
| `000531` | satellite | 1.00% | 1.00% | 3.0% | ok |
| `000404` | satellite | 1.85% | 1.85% | 3.0% | ok |
| `000522` | satellite | 0.03% | 0.03% | 1.0% | ok |
| `000073` | satellite | 1.27% | 1.27% | 5.0% | ok |
| `000219` | satellite | 1.24% | 1.24% | 5.0% | ok |
| `000398` | satellite | 1.41% | 1.41% | 5.0% | ok |
| `000433` | satellite | 1.58% | 1.58% | 5.0% | ok |
| `000573` | satellite | 1.58% | 1.58% | 5.0% | ok |
| `000566` | satellite | 0.38% | 0.38% | 5.0% | ok |
| `000083` | satellite | 0.03% | 0.03% | 1.0% | ok |
| `000368` | index_tool | 0.72% | 0.72% | 3.0% | ok |
| `000311` | index_tool | 1.37% | 1.37% | 3.0% | ok |
| `000312` | index_tool | 1.37% | 1.37% | 3.0% | ok |
| `000313` | index_tool | 1.20% | 1.20% | 3.0% | ok |
| `000656` | index_tool | 0.72% | 0.72% | 3.0% | ok |
| `000176` | index_tool | 0.72% | 0.72% | 3.0% | ok |
| `000512` | index_tool | 0.72% | 0.72% | 3.0% | ok |
| `000059` | index_tool | 0.03% | 0.03% | 3.0% | ok |

</details>

## Risk Review Funds

检测到 4 只含风险标记（risk_tags high_volatility/large_drawdown/high_turnover 或 max_dd<-30% / vol>30% 或 watch_reasons 含 allocation_risk_review）。

| fund_code | status | risk_tags | watch_reasons | alpha_1y | vol | max_dd | bucket | opt_w |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| `000522` | eligible | drawdown_high, holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high | — | 132.22% | 44.25% | -20.21% | satellite | 0.03% |
| `000531` | eligible | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high | — | 151.38% | 38.25% | -17.60% | satellite | 1.00% |
| `000404` | eligible | industry_concentration_high, tracking_error_high, volatility_high | — | 143.42% | 38.08% | -17.15% | satellite | 1.85% |
| `000017` | eligible | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high | — | 295.51% | 40.16% | -14.85% | satellite | 1.68% |

## Optimized Top 20 by Weight

method = cap_redistribute_v1, capped_count = 0, total_weight = 100.00%

| rank | fund_code | opt_w | dry_run | max_cap | capped | bucket | role | sub_class |
| ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| 1 | `000279` | 2.26% | 2.26% | 8.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_deep_value | core |
| 2 | `000308` | 2.13% | 2.13% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | core |
| 3 | `000577` | 2.13% | 2.13% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha, style_quality_growth | core |
| 4 | `000520` | 2.09% | 2.09% | 8.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 5 | `000527` | 2.09% | 2.09% | 8.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 6 | `000619` | 2.09% | 2.09% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha | core |
| 7 | `000172` | 2.06% | 2.06% | 8.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha | core |
| 8 | `000126` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 9 | `000136` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 10 | `000263` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 11 | `000327` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 12 | `000513` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 13 | `000541` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 14 | `000595` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 15 | `000609` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 16 | `000654` | 1.92% | 1.92% | 6.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 17 | `000294` | 1.89% | 1.89% | 8.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 18 | `000309` | 1.89% | 1.89% | 8.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 19 | `000457` | 1.89% | 1.89% | 8.0% | ok | core | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | core |
| 20 | `000404` | 1.85% | 1.85% | 3.0% | ok | satellite | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | satellite |

## Excluded (from draft) — Reason Top

| reason | count |
| --- | ---: |
| `benchmark_data_missing` | 50 |
| `manual_exclude` | 4 |

## observe / review_required 现状

observe: 110 只（不进入 draft，但保留作为后续监控池）
review_required: 4 只（已通过 suggest API 给出预填建议）

observe 主要由低 coverage（factor_coverage_weight < 0.5）+ 数据不足组成，
下一阶段补 benchmark/因子覆盖后再回滚评估。

## Role Suggestion 预填（review_required 自动产出）

| fund_code | suggested_bucket | role_code | max_w | rationale |
| --- | --- | --- | ---: | --- |
| `100038` | exclude | excluded | 0.0% | 数据不足，建议先排除：data_insufficient，manual_review_action，manual_review_required |
| `100039` | exclude | excluded | 0.0% | 数据不足，建议先排除：data_insufficient，manual_review_action，manual_review_required |
| `100056` | exclude | excluded | 0.0% | 数据不足，建议先排除：data_insufficient，manual_review_action，manual_review_required |
| `100060` | exclude | excluded | 0.0% | 数据不足，建议先排除：data_insufficient，manual_review_action，manual_review_required |

## Sign-off Checklist（researcher 决定）

下面 4 个问题是 product acceptance 的关键决策点：

1. **核心/卫星池是否成立**
   - 当前 `core` = 9 只，`core_pending_risk_review` = 0 只，`satellite` = 11 只，`index_tool` = 8 只
   - 你是否接受这些角色分布？哪只应该 core 但被分到 satellite？哪只应该降级？

2. **风险复核基金的 max cap 是否合理**
   - 当前 4 只风险复核基金全部以 draft 权重进入
   - 这些基金 max_drawdown / volatility 是否需要收窄 cap（5% → 3%）或转 satellite？

3. **optimized top 20 权重分配是否符合预期**
   - 头部 5 只权重偏高（约 2~3%/只），是否符合「核心+卫星」直觉？
   - 哪只应该降权？哪只应该升到 core？

4. **排除原因可信度**
   - benchmark_data_missing 是主因（50 只），是项目设计选择
   - style_factor_coverage_low 是数据覆盖问题（95 只），不阻塞本次 acceptance

## 下一步

- 在前端工作台对每只 core/satellite 走一遍 manual override（写入 portfolio_role_reviews）
- 重生成 portfolio-draft 报告看 human override 之后的 draft 权重
- 把 sign-off 结果固化到 `config/portfolio_constraints.v1.json` 的 cap / weight_min 阈值
