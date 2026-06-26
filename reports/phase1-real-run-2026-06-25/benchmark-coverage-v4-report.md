# 相对基准覆盖 v4 报告

- run_at: `2026-06-26`
- rule_version: `v1`
- 输入库: `/tmp/fle-run/source-v4.sqlite`（基于 source.sqlite 备份，先灌入中债登指数日收益，再干净重跑）
- 基金数: **142**
- 行情区间: `2025-06-25 ~ 2026-06-24`（241 个交易日）

## 1. 覆盖结果

| status | v3 | v4 | v5 | Δ(v3→v5) |
|---|---:|---:|---:|---:|
| `benchmark_returns_ready` | 39 | 64 | **68** | **+29** |
| `benchmark_returns_missing` | 103 | 78 | 74 | -29 |
| 合计 | 142 | 142 | 142 | 0 |

- **v4（+25）**：灌入中债登指数日收益（见 §2）。
- **v5（+4）**：修复 INDEX_MAP 中 CSI/深市股指被错误标记为失效 `sina:` 源、且深市 secid 缺 `0.` 前缀的问题（见 §6）。`benchmark_returns` 表 15403 行，`success_funds=68`。

`benchmark_returns` 表共 14439 行，覆盖 64 只基金。`fetch_benchmark_returns` 输出：`mapped_funds=127, success_funds=64, skipped_funds=63`。

> v4 的价值：把 v3 已识别但"无可用免费当前日收益源"的中债登指数，经 akshare 真正灌入 `benchmark_component_returns`，让 25 只以中债综合/中债国债总/中债国债1-3年为基准组件的基金首次可合成基准收益。覆盖从 39 → 64。

## 2. 本次新增数据源：中债登财富指数（akshare）

新增脚本 [scripts/fetch_cbond_index_returns.py](file:///Users/xiongjiali/Desktop/code/fund-label-engine/scripts/fetch_cbond_index_returns.py) 从 akshare 拉取中债登官方财富指数点位，换算为日收益率写入 `benchmark_component_returns`，供 `fetch_benchmark_returns.py` 的本地优先通路（`load_local_component_returns`）消费。财富指数已含票息再投资，其逐日变化率即总收益日收益率，**非代理**。

灌入的指数（截至 2026-06-24/25，均为当日数据，615 行/指数）：

| component_code | 基准名 | akshare 源 | 受益基金数 |
|---|---|---|---:|
| `LOCAL_CBOND_COMPOSITE` | 中债综合财富指数 | `bond_composite_index_cbond(财富,总值)` | 24 |
| `LOCAL_CBOND_GOV_TOTAL` | 中债国债总财富指数 | `bond_index_general_cbond(国债总指数,财富,总值)` | 1 |
| `LOCAL_CBOND_GOV_1_3Y` | 中债国债1-3年财富指数 | `bond_treasury_index_cbond(财富,1-3Y)` | 1 |

实测样本（重跑日志）：
- `000663 沪深30060%+中债综合40%: 194 rows`
- `100039 沪深30080%+中债综合20%: 194 rows`
- `100060 中证80080%+中债综合20%: 194 rows`

测试：[backend/tests/test_fetch_cbond_index_returns.py](file:///Users/xiongjiali/Desktop/code/fund-label-engine/backend/tests/test_fetch_cbond_index_returns.py)（4 passed，覆盖财富点位换算、落库、幂等替换，不依赖网络）。

## 3. 剩余缺失归因（v5：74 只）

| 缺口类型 | v4(78) | v5(74) | 说明 |
|---|---:|---:|---|
| 4 个债券指数无免费当前日收益源 | 58 | **58** | 见 §4，需付费/授权源 |
| 含未映射基准组件（含恒生4） | 12 | 12 | INDEX_MAP 缺映射，可补 |
| 全映射但 fetch-side 失败 | 8 | 4 | v5 已修 4 只（见 §6） |
| 合计 | 78 | 74 | |

### 3.1 v5 后剩余 fetch-side 失败（4 只）

`000059, 000309, 000408, 000594`

阻塞组件：
- `000059` 医药100 `1.000978` — 映射与源均正常，属 eastmoney 偶发请求失败，重试可解决
- `000309 / 000594` 标普中国债券 `LOCAL_SP_CHINA_BOND` — local 占位符，无免费源
- `000408` 中证国债 `H11006` — CSI 债券 H 代码，同 §4 无免费源

> 这 4 只已无零成本 secid 缺口可修：1 只偶发、2 只标普中国债券占位符、1 只 CSI 债券 H 代码。

## 4. 核心瓶颈：4 个债券指数无免费当前日收益源

| component_code | 基准名 | 阻塞基金数 | 现状 |
|---|---|---:|---|
| `H11001` | 中证全债 | 26 | CSI 债券 H 代码，东财 push2his 不返回，中证官网无免费当前日收益 |
| `LOCAL_CBOND_TOTAL` | 中债总 | 13 | 不在 akshare 中债登 313 指数列表内 |
| `H11008` | 中证综合债 | 13 | CSI 债券 H 代码，同 H11001 |
| `LOCAL_CHINA_BOND_TOTAL` | 中国债券总 | 6 | 不在 akshare 中债登 313 指数列表内 |
| 小计 | | **58** | |

实测确认（[probe_map.py](file:///private/tmp/probe_map.py)）：
- 中债登 313 指数列表内有 `综合指数`(=中债综合)、`国债总指数`、`国债1-3Y`，**无**裸 `总指数`/`中国债券总指数`/`中债总指数`。
- 东财 push2his 对 `H11001`/`H11008` 不返回数据；新浪/腾讯同步失效。

### 4.1 v3 → v4 的方法论收敛

v3 已证明瓶颈不是解析规则（103 只缺失中 58 只是"已识别但无源"）。v4 进一步证明：中债登**列表内**指数经 akshare 可取且当日，但**列表外**（中债总/中国债券总）与 **CSI 债券 H 代码**（中证全债/中证综合债）在免费源确无当前日收益。这两类合计 58 只，是覆盖从 64 提升到 120+ 的唯一硬阻塞。

### 4.2 建议解法（按可行性）

1. **付费/授权债券指数日收益**（中债登 CSI Bond / Wind / 中证指数授权）→ 直接写入 `benchmark_component_returns`，component_code 用 `H11001`/`H11008`/`LOCAL_CBOND_TOTAL`/`LOCAL_CHINA_BOND_TOTAL`。代码通路已就绪，差可靠数据。一举解决 58 只。
2. **恒生指数**（4 只）：单独找可用港股指数源。
3. **INDEX_MAP secid 扩展**（§3.1 的 8 只）：零成本，可立即做。

## 5. 结论与下一步

- 覆盖 39 → 64（v4，灌中债登指数）→ **68/142**（v5，修 secid），免费源潜力已基本榨干。
- 剩余 74 缺失中，**58 只**需付费/授权债券指数数据（核心瓶颈），**12 只**需补 INDEX_MAP 映射（含恒生 4），**4 只**为偶发/占位符/CSI 债券 H 代码（见 §3.1）。
- 下一步优先级：
  1. 推动付费/授权债券指数日收益接入（解 58 只，覆盖可达 120+）。
  2. 补未映射基准文本（部分 12 只）。
  3. 恒生指数（4 只）单独处理。

## 6. v5：INDEX_MAP secid 源修复（零成本，+4）

v4 归因发现 8 只"全映射但 fetch-side 失败"，根因有二，均与付费数据无关：

1. **CSI/深市股指被钉死在失效的 `sina:` 源**：`中证主要消费/可选消费/新兴产业/医药卫生/创业板指/创业板综合/中小企业综合` 等在 INDEX_MAP 中 secid 写成 `sina:shXXXXXX` / `sina:szXXXXXX`。sina K 线接口在当前环境已整体失效（实测返回 0 行），而这些指数经东财 `push2his` 直取全部成功。
2. **深市指数缺 `0.` 前缀**：`创业板指 399006`、`创业板综合 399102`、`中小企业综合 399101` 的东财 secid 应为 `0.399xxx`（深市），原 `sina:sz` 的 fallback 把裸 `sz399xxx` 误传给东财导致失败。

修复（[scripts/fetch_benchmark_returns.py](file:///Users/xiongjiali/Desktop/code/fund-label-engine/scripts/fetch_benchmark_returns.py)）：

- 将上述股指 secid 全部改为东财格式（沪市 `1.`、深市 `0.`），不再依赖 sina。
- `fetch_component_returns` 的 sina fallback 增加 `_SINA_TO_EAST` 反查：仅对能翻译成东财 secid 的 SH/SZ 标的回退，CSI 债券 H 代码（`shH11001` 等）无东财源，不再被原样错传。

实测东财直取（2026-06-18~24）：`1.000932 / 1.000964 / 1.000933 / 0.399102 / 0.399101 / 0.399006 / 1.000012` 全部返回数据。重跑后 `success_funds=64 → 68`。CSI 债券 H 代码（`H11001/H11006/H11008`）东财同样不返回，仍归 §4 不可取范畴。
