# 权益风格标签拆分设计：金融高股息 / 红利 / 消费质量

> 状态：已评审，进入实施计划。本文件只定义方案，不改业务代码。
> 背景依据：[dividend-steady-threshold-ab-replay.md](../../../reports/dividend-steady-threshold-ab-replay.md)
> 与 [equity-style-audit-and-calibration-dcce7dcd.md](../../../reports/equity-style-audit-and-calibration-dcce7dcd.md)。

## 1. 问题与结论回顾

全量 A/B 回放已证明：**单一 `dividend_steady_yield_min` 阈值无法同时满足两个目标**。

| 阈值 | dividend_steady 数 | 食饮ETF 159843 | 真红利 000916 |
| --- | ---: | :-: | :-: |
| 0.03（线上） | 718 | 误入 | 保留 0.747 |
| 0.04 | 371 | 仍误入 | 保留 0.598 |
| 0.05 | 40 | 退出 | **误伤 0.387** |

根因：股息率是单维度，区分不了「传统红利股（银行/能源/公用事业，股息 3~5%）」
和「恰好高股息的消费白酒（茅台 4.2%、五粮液 7.7%）」。要靠**行业维度**才能拆开。

deep_value ∩ dividend_steady 重叠 226 只（占 deep_value 的 71%），主要由银行股驱动，
也指向同一结论：需要金融维度来区分「金融低估高息」与「泛深度价值」。

## 2. 目标标签设计

保持现有底层因子命中条件不变（`dividend_steady_yield_min=0.03` 等），
在**基金级**新增/约束以下标签：

### 2.1 `high_dividend_financial` 金融高股息（新增）
- 含义：红利贡献主要来自金融/能源/公用事业等传统高股息行业。
- 判定（基金级，最新报告期）：
  - `dividend_steady_weight >= dividend_steady_weight_min`（沿用 0.5）
  - 且 红利贡献权重中「红利行业」占比 `>= high_dividend_sector_ratio_min`（建议 0.6）
- 「红利行业」白名单（可配置）：银行、保险、证券、多元金融、煤炭、石油石化、
  电力及公用事业、交通运输（高速/港口）。
- 房地产本轮归入 `other`，不计入红利行业。原因是地产高股息常伴随周期、杠杆和信用风险，
  与银行/电力/煤炭这类传统稳定红利不同，放入红利行业会污染「稳健」语义。

### 2.2 `dividend_steady` 红利稳健（保留 + 约束）
- 保留现有阈值判定，但叠加**排除项**：
  - 当红利贡献被**单一消费行业主导**（消费行业占比 `>= consumer_dominant_ratio_min`，
    建议 0.6）时，不打 `dividend_steady`，改走 2.3。
- 即：红利稳健 = 红利达标 且 非金融主导 且 非消费单一主导（中间地带，分散红利）。

### 2.3 `consumer_quality` 消费质量（新增，窄版本轮做）
- 含义：高股息但本质是消费蓝筹（白酒、食品饮料、家电等）。
- 判定：红利达标 且 消费行业占比 `>= consumer_dominant_ratio_min`。
- 目的：把 159843 食饮ETF、001382 易方达国企改革（白酒持仓）归到这里，而非红利。
- 边界：本轮只做「红利底层命中后的消费主导分流」，不扩展成完整消费风格体系。

### 标签关系图

```text
红利底层命中（dividend_steady_weight >= 0.5）
  ├─ 红利行业占比 >= 0.6        -> high_dividend_financial 金融高股息
  ├─ 消费行业占比 >= 0.6        -> consumer_quality 消费质量
  └─ 其余（分散红利）           -> dividend_steady 红利稳健
```

> 三者互斥，由行业占比决定归属；底层股票因子命中逻辑完全不变，只在基金级做分流。

## 3. 数据依赖：股票行业映射表（关键前置）

因子库 `stock_factor_values` 只有数值因子，持仓表只有股票名，**没有行业**。
按评审决定：**正式新建股票行业映射表，最小覆盖版本起步，keyword 仅作校验辅助，
不使用基金级 `industry_allocations` 作主判定。**

### 3.1 新表 `stock_industry_map`（落在 factor 库 `data/stock_factors.sqlite`）

```sql
CREATE TABLE IF NOT EXISTS stock_industry_map (
    stock_code TEXT NOT NULL,
    industry_code TEXT NOT NULL,   -- 申万/中信一级行业代码或自定义枚举
    industry_name TEXT NOT NULL,   -- 行业中文名
    sector_group TEXT NOT NULL,    -- 归并组：financial / energy_utility / consumer / other
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    PRIMARY KEY (stock_code, as_of_date)
);
```

- `sector_group` 是判定真正使用的归并维度，把细行业归到四组：
  - `financial`：银行、保险、证券、多元金融
  - `energy_utility`：煤炭、石油石化、电力及公用事业、交通运输
  - `consumer`：食品饮料、家用电器、白酒（若细分）、商贸零售等
  - `other`：其余，房地产本轮也归入此组
- 「红利行业」= `financial ∪ energy_utility`；「消费行业」= `consumer`。
- MVP 读取口径为**单一最新快照**：表保留 `as_of_date`，但本轮按每只股票最新行业映射使用。
  证据中记录 `industry_map_as_of_date`；后续做历史回测时再升级成按报告期 as-of 对齐。

### 3.2 最小覆盖版本（MVP）
- 不要求覆盖全 A 股。**只需覆盖出现在「红利贡献股票」里的高频股票**即可起步。
- 来源优先级：
  1. fetch 脚本从东财 datacenter 行业接口回填（首选，可复用 `fetch_stock_factors.py` 的请求范式）；
  2. 对未覆盖股票，不写入映射行；判定时按「行业缺失」处理，不把缺失股票计入 `other` 覆盖。
- keyword 辅助：保留股票名关键字（银行/保险/证券）作为**校验**手段，用于
  比对映射表覆盖率与抽样核对，不作为主判定。

### 3.3 覆盖率门槛
- 基金级判定前先算「红利贡献股票的行业映射覆盖率」：
  - 覆盖率 < `sector_coverage_min`（建议 0.7）时，**不分流**，仍按现有 `dividend_steady` 处理，
    并打 observe 级 `sector_mapping_insufficient`，避免在行业数据不足时误分类。

## 4. 计算链路改动

```text
fund_equity_style_contributions（已存在，含 stock_code/contribution_weight/style_code）
  + stock_industry_map（新增）
  -> 按 dividend_steady 命中股票聚合 sector_group 占比
  -> 写入基金级 sector mix 暴露（fund_factor_exposures）
  -> 基金级 high_dividend_financial / consumer_quality / dividend_steady 分流
  -> 标签 + 证据（证据里写明各 sector 占比与覆盖率）
```

- 复用已有贡献明细：`dividend_steady` 的 matched 贡献行已经记录了命中股票和权重，
  只需 join 行业映射即可算 sector 占比，**无需重算股票因子**。
- 新增聚合函数（建议）：`aggregate_dividend_sector_mix(contributions, industry_map)`
  返回 `{financial_ratio, energy_utility_ratio, consumer_ratio, coverage}`。
- batch 将 sector mix 写成 `fund_factor_exposures`，引擎在现有
  `dividend_weight >= cfg.dividend_steady_weight_min` 分支内读取这些暴露并做分流，
  避免让引擎直接查询数据库。

## 5. 配置新增（RuleConfig + rules.v1.json）

```python
high_dividend_sector_ratio_min: float = 0.6   # 红利行业占比达此值 -> 金融高股息
consumer_dominant_ratio_min: float = 0.6      # 消费占比达此值 -> 消费质量
sector_coverage_min: float = 0.7              # 行业映射覆盖率下限
# dividend_steady_yield_min 保持 0.03 不变
```

## 6. 持久化与展示

- 标签写入 `fund_label_results` / `label_calculation_states`（沿用现有通道）。
- 证据 `fund_label_evidence` 写明：各 sector 占比、覆盖率、归属原因。
- 报告脚本 `generate_equity_style_contribution_report.py` 增加：
  - 三个标签的数量分布；
  - high_dividend_financial vs dividend_steady vs consumer_quality 的样本对照；
  - 159843 / 001382 应落入 consumer_quality；512700 / 159887 应落入 high_dividend_financial。

## 7. 验证 gate 与回放

- 复用现有验证 gate：触发任一红利系标签的基金必须有贡献明细。
- 新增一致性检查：被打 `high_dividend_financial` 的基金，其红利贡献的 financial+energy
  占比必须 ≥ 阈值（防止行业映射缺失导致误判）。
- 用 `compare_runs.py` 对比拆分前后：
  - dividend_steady 数应下降，且下降部分应分别进入 high_dividend_financial / consumer_quality；
  - 验收样本：159843→consumer_quality，512700/159887→high_dividend_financial，
    000916→保持红利系（不被误伤）。

## 8. 实施顺序（待批准后执行，TDD）

1. **行业映射数据层**：新建 `stock_industry_map` migration + fetch 回填脚本（MVP 覆盖红利高频股），
   keyword 校验脚本。
2. **聚合函数**：`aggregate_dividend_sector_mix` + 单元测试（纯函数，先锁语义）。
3. **引擎分流**：在 dividend 分支内接入分流 + RuleConfig 新字段 + 测试。
4. **持久化/报告/gate**：证据、报告分布、一致性 gate。
5. **全量回放**：跑全量 + compare_runs 验收，出对照报告。

## 9. 评审决策（已拍板）

1. **房地产归 `other`，不放进 `energy_utility`。** 地产的周期、杠杆、信用风险与
   银行/电力/煤炭这类传统红利不同，放进红利行业会把「困境高息/周期修复」误包装成
   「稳健红利」。因此红利行业仅为 `financial ∪ energy_utility`，不含地产。

2. **`consumer_quality` 本轮就做，但只做窄版。** 本轮核心验收之一就是 159843
   食品饮料 ETF 不再叫红利；若只做 `high_dividend_financial`，白酒/消费蓝筹只是被排除
   却没有正确去处，解释层会断掉。窄版含义：仅表示「红利底层命中后，消费贡献占比高，
   故归为消费质量」，**不扩展成完整消费风格体系**。

3. **行业映射用单快照 MVP，不做时间序列。** 表保留 `as_of_date` 字段，但本轮按
   「每只股票最新行业映射」使用。行业归属变化慢，MVP 重点是修正语义。证据里记录
   `industry_map_as_of_date`，将来做历史回测再升级为按报告期 as-of 对齐。

4. **阈值先用 0.6，但必须配置化 + 二次校准。**
   - `high_dividend_sector_ratio_min = 0.6`
   - `consumer_dominant_ratio_min = 0.6`
   - `sector_coverage_min = 0.7`
   0.6 代表「主导」而非「略偏」，适合第一版，但非最终值。跑完全量后看分布，
   若 512700/159887 进金融高股息、159843/001382 进消费质量、000916 仍留红利系，则先通过。

## 10. 最终实施口径

```text
红利底层命中（dividend_steady_weight >= dividend_steady_weight_min）
  ├─ 行业映射覆盖率 < sector_coverage_min(0.7)
  │    -> 保留 dividend_steady，并追加 observe 级 sector_mapping_insufficient
  ├─ financial + energy_utility >= high_dividend_sector_ratio_min(0.6)
  │    -> high_dividend_financial 金融高股息
  ├─ consumer >= consumer_dominant_ratio_min(0.6)
  │    -> consumer_quality 消费质量（窄版）
  └─ 其他
       -> dividend_steady 红利稳健
```

> sector_group 归并：`financial`（银行/保险/证券/多元金融）、
> `energy_utility`（煤炭/石油石化/电力及公用事业/交通运输）、
> `consumer`（食品饮料/家电/白酒/商贸零售等）、`other`（含房地产及其余）。
