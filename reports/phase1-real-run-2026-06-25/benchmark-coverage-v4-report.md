# 相对基准覆盖 v4 报告

- run_at: `2026-06-26`
- rule_version: `v1`
- 输入库: `/tmp/fle-run/source-v4.sqlite`（基于 source.sqlite 备份，先灌入中债登指数日收益，再干净重跑）
- 基金数: **142**
- 行情区间: `2025-06-25 ~ 2026-06-24`（241 个交易日）

## 1. 覆盖结果

| status | v3 | v4 | Δ |
|---|---:|---:|---:|
| `benchmark_returns_ready` | 39 | **64** | **+25** |
| `benchmark_returns_missing` | 103 | 78 | -25 |
| 合计 | 142 | 142 | 0 |

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

## 3. 剩余 78 只缺失归因

| 缺口类型 | fund_count | 说明 |
|---|---:|---|
| 4 个债券指数无免费当前日收益源 | **58** | 见 §4，需付费/授权源 |
| 含未映射基准组件（含恒生4） | 12 | INDEX_MAP 缺映射，可补 |
| 全映射但 fetch-side 失败 | 8 | INDEX_MAP secid 缺口 + 少量 local 占位符，可不用付费数据修 |
| 合计 | 78 | |

### 3.1 全映射 fetch-side 失败（8 只，可不用付费数据修）

`000083, 000270, 000279, 000309, 000326, 000327, 000408, 000594`

阻塞组件：
- `上证国债 000012`（4）— SSE 指数，应为 `1.000012`，缺 secid 映射
- `中证700 000907`、`中证主要消费 000932`、`中证可选消费 000931`、`中证2000 932000`、`中证红利 000922` — CSI 指数，缺 secid 映射
- `标普中国债券 LOCAL_SP_CHINA_BOND`（2）— local 占位符，无源
- `中证国债 H11006`（1）— CSI 债券 H 代码，同 §4 无免费源

> 修这 8 只只需扩展 INDEX_MAP 的 secid 覆盖（上证国债/中证700/中证消费/中证2000/中证红利等），不涉及付费数据。

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

- 覆盖 39 → **64/142**（+25），中债登可用指数已全部灌入，免费源在债券侧的潜力已榨干。
- 剩余 78 缺失中，**58 只**需付费/授权债券指数数据（核心瓶颈），**12 只**需补 INDEX_MAP 映射，**8 只**需补 secid 映射（零成本）。
- 下一步优先级：
  1. 推动付费/授权债券指数日收益接入（解 58 只，覆盖可达 120+）。
  2. 零成本修 INDEX_MAP secid 缺口（解 8 只）+ 补未映射基准文本（部分 12 只）。
  3. 恒生指数（4 只）单独处理。
