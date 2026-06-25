# 风格暴露 coverage 质量门槛验证报告

- before_run_id: `9c01103530064984b41fe004585414e0`
- after_run_id: `f7ad3dfbac4f4d579a2d6804dfc35d35`
- rule_version: `v1`
- 输入库: `/tmp/fle-run/source.sqlite`
- 输出库: `/tmp/fle-run/output-v1-coverage-gated.sqlite`
- processed: **142**

## 1. 规则

| coverage_weight | 处理 |
|---|---|
| `<50%` | 输出 `style_exposure_low_coverage`，不出正式风格标签 |
| `50%-70%` | 输出 `style_exposure_observe`，只观察，不出正式风格标签 |
| `>=70%` | 允许正式 `deep_value` / `quality_growth` / `dividend_steady` |

## 2. 覆盖质量分布

| bucket | fund_count | min | max | avg |
|---|---:|---:|---:|---:|
| `50%-70% observe` | 6 | 0.5402 | 0.6979 | 0.617967 |
| `>=70% formal_allowed` | 136 | 0.7017 | 0.9521 | 0.881831 |

## 3. 风格标签变化

| label_code | status | before | after | delta |
|---|---|---:|---:|---:|
| `style_pending_rule_definition` | observe | 128 | 122 | -6 |
| `quality_growth` | active | 9 | 9 | 0 |
| `style_exposure_observe` | observe | 0 | 6 | 6 |
| `deep_value` | active | 3 | 3 | 0 |
| `dividend_steady` | active | 3 | 3 | 0 |

## 4. 低于 70% coverage 的正式风格标签拦截

未发现 coverage < 70% 仍打出正式风格标签的基金。

## 5. 观察区间样本

| fund_code | fund_name | coverage | quality_growth | deep_value | dividend | evidence |
|---|---|---:|---:|---:|---:|---|
| `000567` | 广发聚祥灵活混合 | 54.02% | 7.35% | 35.98% | 32.84% | 基金级因子覆盖权重 54%，处于观察区间 50%~70%，不输出正式风格标签。 |
| `000264` | 博时内需增长混合A | 57.02% | 5.73% | 11.80% | 18.96% | 基金级因子覆盖权重 57%，处于观察区间 50%~70%，不输出正式风格标签。 |
| `000551` | 中信保诚幸福消费混合A | 60.91% | 12.41% | 2.38% | 25.04% | 基金级因子覆盖权重 61%，处于观察区间 50%~70%，不输出正式风格标签。 |
| `100039` | 富国通胀通缩主题轮动混合A | 63.08% | 4.17% | 4.95% | 12.17% | 基金级因子覆盖权重 63%，处于观察区间 50%~70%，不输出正式风格标签。 |
| `000530` | 招商丰盛稳定增长混合A | 65.96% | 0.00% | 15.27% | 31.69% | 基金级因子覆盖权重 66%，处于观察区间 50%~70%，不输出正式风格标签。 |
| `000056` | 建信消费升级混合 | 69.79% | 7.22% | 5.89% | 45.33% | 基金级因子覆盖权重 70%，处于观察区间 50%~70%，不输出正式风格标签。 |

## 6. 结论

- v1 142 只中没有 `<50%` 低覆盖基金。
- 6 只基金进入 `50%-70%` 观察区间，输出 `style_exposure_observe`。
- 正式风格标签没有出现在 coverage < 70% 的基金上。
- 质量门槛只改变风格可信度表达，没有继续扩展多期稳定性或同类池功能。
