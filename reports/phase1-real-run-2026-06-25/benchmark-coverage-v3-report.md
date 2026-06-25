# 相对基准覆盖 v3 报告

- run_at: `2026-06-25`
- rule_version: `v1`
- 输入库: `/tmp/fle-run/source-v3.sqlite`（基于 v2 source.sqlite 备份，干净重跑）
- 基金数: **142**
- 行情区间: `2025-06-25 ~ 2026-06-24`（241 个交易日）

## 1. 覆盖结果

| status | fund_count |
|---|---:|
| `benchmark_returns_ready` | 39 |
| `benchmark_returns_missing` | 103 |
| 合计 | 142 |

`benchmark_returns` 表共 9399 行，覆盖 39 只基金，区间 `2025-06-26 ~ 2026-06-24`。

> 覆盖数与 v2 持平（39 只）。v3 的价值不在于提升覆盖数，而在于：(1) 通过重试机制让这 39 只的获取更稳定；(2) 把 103 只缺失的原因**逐组件审计清楚**，明确区分"未识别指数"与"已识别但无行情源"两类缺口。

## 2. 组件解析审计（benchmark_components）

| status | reason | component_count | fund_count |
|---|---|---:|---:|
| `resolved` | `index` | 247 | 132 |
| `unresolved` | `unsupported_component_or_missing_source` | 14 | 14 |
| `resolved` | `synthetic` | 8 | 8 |
| `resolved` | `synthetic_fixed_return` | 6 | 6 |
| `unresolved` | `benchmark_missing` | 1 | 1 |

对比 v2：
- resolved/index 组件 203 → 247（中债/中证债指数已映射为 `local:` 占位符或 `sina:` 源，进入审计）
- unresolved 组件 58 → 14（中债类不再标记为 unresolved，改由"已识别但无数据"的占位符承载）
- 剩余 14 个 unresolved 均为**未在 INDEX_MAP 中映射的指数**（见 §3）

## 3. 未识别指数（unresolved，需补映射）

| component_name | fund_count |
|---|---:|
| 恒生指数 | 4 |
| (指年,评价时按期间折算) | 1 |
| MSCI中国A股指数 | 1 |
| 上证高端装备60指数 | 1 |
| 中证A500指数 | 1 |
| 中证军工指数 | 1 |
| 中证服务业指数 | 1 |
| 中证财通中国可持续发展100(ECPIESG)指数 | 1 |
| 国证航天军工指数 | 1 |
| 富时中国A600指数 | 1 |
| 新华富时中国A200指数 | 1 |
| (benchmark 文本为空) | 1 |

> 这些多为单基金引用的小众指数，单独补齐 ROI 较低。恒生指数（4 只）值得后续单独处理，但新浪港股 K 线接口已失效（返回 `Service not valid`），东方财富对港股指数 secid 返回连接错误，需另寻稳定港股源。

## 4. 已识别但无行情源的债券指数（核心瓶颈）

下列组件已在 INDEX_MAP 中**成功识别**（审计状态 `resolved/index`），但其行情源**拿不到当前数据**，导致依赖它们的基金被 skip。这是覆盖率无法突破 39 的根本原因。

| component_name | secid | 缺数据原因 | fund_count |
|---|---|---|---:|
| 中证全债 | `sina:shH11001` | 新浪数据截止 2010，区间校验失败 | 26 |
| 中债综合 | `local:LOCAL_CBOND_COMPOSITE` | 无免费日收益源，占位符待入库 | 24 |
| 中债总 | `local:LOCAL_CBOND_TOTAL` | 无免费日收益源，占位符待入库 | 13 |
| 中证综合债 | `sina:shH11008` | 新浪数据过期，区间校验失败 | 13 |
| 中国债券总 | `local:LOCAL_CHINA_BOND_TOTAL` | 无免费日收益源，占位符待入库 | 6 |
| 中证国债 | `sina:shH11006` | 新浪数据过期，区间校验失败 | 2 |
| 标普中国债券 | `local:LOCAL_SP_CHINA_BOND` | 无免费日收益源 | 2 |
| 中债国债总 | `local:LOCAL_CBOND_GOV_TOTAL` | 无免费日收益源 | 1 |
| 中债国债总1-3年 | `local:LOCAL_CBOND_GOV_1_3Y` | 无免费日收益源 | 1 |
| 新华富时中国国债 | `local:LOCAL_XHFT_CHINA_GOV_BOND` | 无免费日收益源 | 1 |

> 仅"中证全债 + 中债综合 + 中证综合债"三项就阻塞约 60+ 个基金基准（含重叠）。若能补齐这三项当前日收益，覆盖率可望从 39 跃升至 70+。

## 5. 数据源探测结论（已穷尽免费源）

针对 §4 的关键债券指数，v3 期间系统化探测了所有免费源，结论如下：

| 数据源 | 探测方式 | 结果 |
|---|---|---|
| 东方财富 searchapi | `searchapi.eastmoney.com/api/suggest/get` 搜"中证全债/中证综合债/中债综合" | 0 命中 |
| 东方财富 push2his | 尝试 `1./47./48./90./100.H11001` 等 secid | `Remote end closed connection`（H 代码不被支持） |
| 新浪 K 线 | `quotes.sina.cn ... shH11001` | 数据存在但截止 2010，区间校验失败 |
| 腾讯 qt | `qt.gtimg.cn/q=shH11001` | `v_pv_none_match`（无此代码） |
| 中证官网 | `csindex.com.cn` 多个 API 路径 | 全部 404（官网改版为 SPA，旧 API 失效） |

**结论**：中证全债/中证综合债/中债综合/中债总/中国债券总指数，**在免费数据源中没有可获取的当前日收益数据**。中债登（ChinaBond）与中证指数公司的日收益为付费/授权数据。按既定原则，不使用不相干指数做代理，保留 `benchmark_data_missing`。

## 6. v3 代码改动

`scripts/fetch_benchmark_returns.py`：
- 新增 `_retrying_request`：指数行情请求带指数退避重试（默认 4 次，1.5s 递增），缓解东方财富偶发断连。
- 扩展 `INDEX_MAP`：新增中证全债/中证综合债/中证国债 → 新浪 `shH11001/shH11008/shH11006`（数据可获取时自动生效，当前过期则 skip）。
- 新增 `local:` 占位符映射：中债综合/中债总/中国债券总/标普中国债券等映射为 `LOCAL_*` 内部 code，作为审计钩子（已识别但待入库）。
- 新增 `load_local_component_returns`：从 `benchmark_component_returns(component_code, trade_date, daily_return, source)` 表读取本地日收益，fetch 流程优先本地、再 fallback 行情源。
- 移除 `fetch_hk_index_returns`：新浪港股接口已失效（`Service not valid`），且未被调用，清理死代码。

测试：`backend/tests/test_fetch_benchmark_returns.py` 9 项全部通过，覆盖 local 占位符解析与本地收益加载。

## 7. 结论与下一步

- **覆盖**：39/142，与 v2 持平；103 缺失已逐组件审计清楚。
- **瓶颈定位**：不是解析规则问题，而是中证全债/中债综合/中证综合债等债券指数**无免费当前日收益源**。
- **未做伪替代**：缺失基金保留 `benchmark_data_missing`，不强行用上证国债/沪深300代理。
- **可立即推进的方向**：
  1. 接入付费/授权债券指数日收益（中债登 CSI Bond / Wind / 中证指数授权），写入 `benchmark_component_returns` 表后覆盖率即可大幅提升。
  2. 单独处理恒生指数（4 只），寻找可用港股指数源。
  3. 小众未映射指数（中证A500/中证军工/国证航天军工等，各 1 只）按需补 INDEX_MAP。
- **建议**：相对基准 v3 到此收尾，转入风格稳定性分析（已有 exposure + coverage gate 基础）。债券指数源问题作为独立数据接入任务跟踪，不阻塞标签链路其他部分。
