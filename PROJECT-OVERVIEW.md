# 基金标签引擎项目——完整说明文档

> 本文档覆盖：项目定义、痛点、数据底座、8 步计算流程（代码级）、标签体系、基准处理、同类排名、竞品横评、FOF 组合工作台、前端工作台、工程化、卡点、下一步、7 个补充问题详解。
>
> 最后更新：2026-07-06

---

## 目录

- [第一部分：项目是什么、为什么做](#第一部分项目是什么为什么做)
- [第二部分：数据底座](#第二部分数据底座)
- [第三部分：8 步计算流程详解（代码级）](#第三部分8-步计算流程详解代码级)
- [第四部分：基准处理](#第四部分基准处理)
- [第五部分：标签体系](#第五部分标签体系)
- [第六部分：同类排名分位数系统](#第六部分同类排名分位数系统)
- [第七部分：竞品横评工作台](#第七部分竞品横评工作台)
- [第八部分：FOF 组合工作台](#第八部分fof-组合工作台)
- [第九部分：前端工作台](#第九部分前端工作台)
- [第十部分：工程化](#第十部分工程化)
- [第十一部分：当前卡点](#第十一部分当前卡点)
- [第十二部分：领导可能关心的问题](#第十二部分领导可能关心的问题)
- [第十三部分：7 个补充问题详解](#第十三部分7-个补充问题详解)
- [第十四部分：下一步规划](#第十四部分下一步规划)

---

## 第一部分：项目是什么、为什么做

### 1.1 一句话定义

这是一个**基金体检和标签报告系统**：把基金数据加工成可解释、可追溯、可复核、可批量运行的标签结果。不推荐买哪只基金，不做自动交易，只输出标签和证据。

### 1.2 解决的核心痛点

| 痛点 | 具体表现 | 本系统怎么解决 |
|---|---|---|
| 标签口径不统一 | 不同部门对"价值基金""成长基金"定义不同 | 统一规则计算，所有人看同一套标签 |
| 不知道"为什么打这个标签" | 传统方式只给结论不给过程 | 每个标签存证据：指标值、阈值、数据来源、白话解释 |
| 基准用错导致结论错 | 很多机构用沪深 300 代替所有基金基准 | 逐只解析业绩比较基准，拆组件，合成日收益，不用错误代理 |
| 数据不够也硬算 | 缺净值、缺持仓时仍出标签 | 数据门禁：数据不够标记"数据不足"，不硬算 |
| 没有"为什么没打标签" | 不知道是没达标还是没法算 | 三种计算状态：触发/未触发/无法计算 |
| 缺同类排名 | 只知道"是不是高估值"，不知道"排第几" | 横截面分位数：8 个指标 × 多分组维度 |

---

## 第二部分：数据底座

### 2.1 数据来源

| 数据维度 | 具体内容 | 来源 | 是否需要采购 |
|---|---|---|---|
| 基金画像 | 代码、名称、类型、规模 | fundData SQLite 库（本地缓存） | 否 |
| 基金净值 | 日收益率（142 只有 1 年，3 只有 3 年） | fundData 库 | 否 |
| 股票持仓 | 最新一期持仓（股票代码、名称、权重） | fundData 库 | 否 |
| 行业配置 | 持仓股票的行业归属 | 外挂因子库 | 否 |
| 基金经理 | 姓名、任期天数 | fundData 库 | 否 |
| 费率 | 管理费 + 托管费 + 销售服务费 | fundData 库 | 否 |
| 股票因子 | PB/PE/ROE/利润增速/营收增速/股息率/市值/估值分位 | API 抓取（5500+ 只 A 股） | 否 |
| 行业映射 | 4149 只股票的行业归属 | API 批量抓取 | 否 |
| 基准日收益 | 逐只解析业绩比较基准，拆组件合成 | 东方财富 + akshare + Investoday API | **5 只需采购** |

### 2.2 基金范围筛选（三层过滤）

| 层级 | 筛选条件 | 说明 |
|---|---|---|
| 第一层 | 基金类型 ∈ {股票型, 混合型-偏股, 混合型-灵活, 指数型-股票} | 防止拿股票基金尺子量债券基金 |
| 第二层 | 基金代码在 Phase1 v1 正式清单里 | 业务确认的范围 |
| 第三层 | 数据门禁通过 | 数据够才能正式计算 |

142 只基金类型分布：

| 类型 | 数量 |
|---|---:|
| 混合型-灵活 | 71 |
| 混合型-偏股 | 41 |
| 股票型 | 16 |
| 指数型-股票 | 14 |

### 2.3 数据清洗

| 因子 | 清洗规则 | 为什么 |
|---|---|---|
| PB（市净率） | 负值/零 → 剔除；>200 → 剔除 | 净资产为负无法解释估值倍数 |
| PE（市盈率） | 负值/零 → 剔除；>2000 → 剔除 | 亏损股的 PE 无意义 |
| ROE | 截断到 [-50%, 50%] | 极端值不具代表性 |
| 利润增速 | 截断到 [-100%, 300%] | 去年亏损小基数→今年盈利的假增长 |
| 营收增速 | 截断到 [-100%, 300%] | 同上 |

---

## 第三部分：8 步计算流程详解（代码级）

### 总览

```
第 1 步：加载原始材料
第 2 步：确认基金范围
第 3 步：数据门禁
第 4 步：计算基础指标
第 5 步：计算持仓风格
第 6 步：计算相对基准指标
第 7 步：按规则打标签
第 8 步：分类、分组、展示状态
```

---

### 第 1 步：加载原始材料

#### 做什么

系统从数据库里把这只基金的"材料袋"拿出来，组装成一个 `FundInput` 对象（engine.py 第 791 行）。

#### FundInput 对象的 18 个字段

| 序号 | 字段 | 类型 | 来源表 | 用途 |
|---|---|---|---|---|
| 1 | fund_code | str | fund_profiles | 基金代码 |
| 2 | fund_name | str | fund_profiles | 基金名称（判断是否被动指数） |
| 3 | fund_type | str | fund_profiles | 基金类型（判断是否进入范围） |
| 4 | nav_returns | list[float] | nav_history | 每日收益率序列 |
| 5 | stock_holdings | list[dict] | stock_holdings | 股票持仓（含 stock_code/weight/report_period） |
| 6 | industry_allocations | list[dict] | industry_allocations | 行业配置（含 industry_name/weight/report_period） |
| 7 | stock_factors | list[dict] | stock_factor_values（外挂因子库） | 股票因子（PB/PE/ROE 等） |
| 8 | factor_exposures | list[dict] | fund_factor_exposures | 预聚合的基金级因子暴露（可选） |
| 9 | benchmark_returns | list[float] | benchmark_returns | 基准日收益序列 |
| 10 | benchmark_name | str \| None | — | 基准名称 |
| 11 | manager_tenure_years | float \| None | fund_manager_links | 经理任期（年） |
| 12 | management_fee | float \| None | fee_structures | 管理费 |
| 13 | custody_fee | float \| None | fee_structures | 托管费 |
| 14 | sales_service_fee | float \| None | fee_structures | 销售服务费 |
| 15 | fund_size | float \| None | fund_profiles | 基金规模（亿元） |
| 16 | equity_position | float \| None | fund_positions | 权益仓位 |
| 17 | holding_report_date | str \| None | stock_holdings | 持仓报告期（用于 stale 检查） |
| 18 | industry_report_date | str \| None | industry_allocations | 行业报告期（用于 stale 检查） |

#### 关键细节

**细节 1：持仓和行业配置取"最新一期"**

基金每季度披露持仓。加载时先找到最大的 `report_period`（最新报告期），再取那一期的股票明细。同时把 `report_period` 存入 `holding_report_date`，后续第 3 步用来判断数据是否过期（stale）。

**细节 2：ETF 场内占位费率不会被当作真实费率**

有些 ETF 数据里只有"场内ETF-无费率信息"这种占位记录。系统不会把它理解成费率为 0，而是继续视为费率证据不足（management_fee/custody_fee 为 None）。

**细节 3：股票因子从外挂因子库读取**

股票因子通过 ATTACH DATABASE 挂载独立因子库 `stock_factors.sqlite`，覆盖 5500+ 只 A 股股票。

**细节 4：因子数据会做清洗**

加载股票因子时自动清洗脏值：PB 负值/零/>200 剔除，PE 负值/零/>2000 剔除，ROE 截断到 [-50%, 50%]，利润增速截断到 [-100%, 300%]。

**细节 5：行业映射从外挂因子库读取**

持仓股票的行业归属从 `stock_industry_map` 表读取，4149 只股票有行业映射。行业映射在加载时合并到 `stock_factors` 每一行里的 `sector_group` 字段。持仓权重覆盖率 99.3%。

---

### 第 2 步：确认基金范围

#### 第一层：看基金类型

engine.py 第 10 行定义了支持的类型：

```python
SUPPORTED_ACTIVE_EQUITY_TYPES = {
    "股票型",
    "混合型-偏股",
    "混合型-灵活",
    "指数型-股票",
}
```

基金类型直接从数据库 `fund_profiles` 表的 `fund_type` 字段读取，是数据源在抓取基金基础信息时已经分类好的，系统直接信任这个分类。

#### 第二层：看 Phase1 正式清单

项目有业务确认过的清单文件 `data/phase1_fund_codes_v1_official.txt`，只保留清单里的基金代码。

#### 第三层：进入计算前做数据 gate（第 3 步详述）

#### 范围确认后做分类

engine.py 第 1313 行的 `_is_passive_index_fund()`：

```python
@staticmethod
def _is_passive_index_fund(fund: FundInput) -> bool:
    text = f"{fund.fund_type} {fund.fund_name}".upper()
    return any(keyword in text for keyword in ("指数", "ETF", "联接", "INDEX"))
```

| 分类代码 | 判断方式 | 当前数量 |
|---|---|---|
| active | 名称不含"指数/ETF/联接/INDEX" | 128 |
| passive_index | 名称含上述关键词 | 14 |

---

### 第 3 步：数据门禁

#### 做什么

核心实现在 `_coverage_details()`（第 1948 行）。逐字段检查，每个字段返回 4 个信息：`ok`（是否通过）、`reason`（子原因码）、`observed`（实际值）、`threshold`（门槛值）。

#### 9 项检查

| 序号 | 检查字段 | 门槛 | 不通过原因码 | 代码位置 |
|---|---|---|---|---|
| 1 | supported_fund_type | 类型 ∈ 四类之一 | fund_type_unsupported | 第 1980 行 |
| 2 | nav_returns | ≥ 180 条 | nav_missing / nav_samples_below_min | 第 1988 行 |
| 3 | stock_holdings | ≥ 1 条 且 总权重 ≥ 50% 且 未过期 | stock_holdings_missing / count_low / total_weight_low / stale | 第 2001 行 |
| 4 | industry_allocations | ≥ 1 条 且 未过期 | industry_missing / count_low / stale | 第 2045 行 |
| 5 | manager_tenure_years | 不为 None | manager_missing | 第 2071 行 |
| 6 | fee_structure | 管理费和托管费都不为 None | fee_structure_missing | 第 2080 行 |
| 7 | fund_size | 不为 None | fund_size_missing | 第 2088 行 |
| 8 | equity_position | 不为 None 且 ≥ 最低门槛 | equity_position_missing / below_min | 第 2096 行 |
| 9 | return_window | NAV 样本 ≥ 指定窗口最小值 | return_window_insufficient | 第 2120 行 |

#### 4 级判断逻辑（以 stock_holdings 为例）

```
1. stock_len == 0 → stock_holdings_missing（完全没持仓）
2. stock_len < gate_min_stock_holding_count → stock_holdings_count_low（持仓条数太少）
3. stock_total_weight < gate_min_holding_total_weight → stock_holdings_total_weight_low（总权重太低）
4. holding_stale > gate_max_holding_stale_days → stock_holdings_stale（数据过期）
5. 以上都不满足 → ok=True（通过）
```

#### 数据过期检查（stale days）

`_stale_days()`（第 2127 行）计算报告期距离数据截止日的天数。任一为空返回 None，不参与 gate 判定。

#### 门禁不通过时系统做 3 件事

1. 打 `data_insufficient` 标签（confidence=1.0, status=observe）
2. 打 `manual_review_required` 标签（confidence=1.0, status=observe）
3. 对每个未通过的 gate 输出一条独立 evidence

#### 标签降级

门禁不通过时，所有非 data_quality/review 类标签被强制降级为 `observe`（观察）状态。

#### 当前结果

142 只基金在上述基础 gate 上全部通过，都进入 `label_ready_pool`。

---

### 第 4 步：计算基础指标

#### 收益风险指标：按 4 个窗口计算

engine.py 第 21 行定义了窗口：

```python
RETURN_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("1m", 21, 15),    # 1 个月：21 个交易日，最少 15 个有效样本
    ("3m", 63, 40),    # 3 个月：63 个交易日，最少 40 个有效样本
    ("1y", 252, 180),  # 1 年：252 个交易日，最少 180 个有效样本
    ("3y", 756, 500),  # 3 年：756 个交易日，最少 500 个有效样本
)
```

正式标签只能从 1y 和 3y 窗口产出。优先用 3y，3y 不够再用 1y。当前 142 只都有 1y，其中 3 只有 3y。

#### 核心指标计算方式

| 指标 | 代码实现 | 小白理解 |
|---|---|---|
| 区间收益 | `cumulative = Π(1 + r)`，`period_return = cumulative - 1` | 这段时间总共涨跌多少 |
| 年化收益 | `cumulative ** (252/n) - 1`，负累计返回 -1.0 | 换算成一年口径 |
| 年化波动 | `std(daily_returns) × √252` | 净值上下晃得有多厉害 |
| 最大回撤 | 见下方代码 | 中间最难受的时候跌了多少 |
| 夏普 | `annualized_return / annualized_volatility`（无风险利率=0） | 每承担一份波动换来多少收益 |

#### 最大回撤计算（第 1869 行）

```python
@staticmethod
def _max_drawdown(returns: list[float]) -> float:
    wealth = 1.0      # 财富曲线，从 1 开始
    peak = 1.0        # 历史最高点
    max_drawdown = 0.0
    for daily_return in returns:
        wealth *= 1 + daily_return      # 每天更新财富
        peak = max(peak, wealth)        # 更新历史最高点
        if peak > 0:
            max_drawdown = min(max_drawdown, wealth / peak - 1)  # 当前相对高点的跌幅
    return max_drawdown
```

#### 持仓和行业指标

| 指标 | 计算方式 | source |
|---|---|---|
| top_10_holding_weight | 前 10 只股票权重相加 | fund_stock_holdings |
| stock_holding_count | 持仓股票总数 | fund_stock_holdings |
| industry_top1_weight | 最大行业权重 | fund_industry_allocations |
| industry_top3_weight | 前三大行业权重相加 | fund_industry_allocations |
| industry_count | 涉及行业数量 | fund_industry_allocations |
| equity_position | 权益仓位（直接读） | fund_positions |
| manager_tenure_years | `tenure_days / 365.25` | fund_manager_links |
| total_annual_fee | 管理费 + 托管费 + 销售服务费 | fee_structures |
| fund_size | 基金规模（直接读） | fund_profiles |

#### 关键细节

- **负累计收益处理**：年化公式在累计收益为负时返回 -1.0，避免负数开方出错
- **full 窗口不参与正式标签**：只用于排查
- **每个指标都记录来源**：每个 FeatureValue 都带 source 字段

---

### 第 5 步：计算持仓风格

#### 第一阶段：检查是否有股票因子

`_add_style_boundary_labels()`（第 2753 行）：有持仓但缺股票因子 → 输出 `style_unlabeled_stock_factors_missing`。

#### 第二阶段：高级风格标签（深度价值/质量成长/红利稳健）

`_add_style_labels()`（第 3424 行）。对每只持仓股票判断它属于哪种特征：

| 股票特征 | 命中条件 | 配置项 |
|---|---|---|
| 深度价值股票 | `pb ≤ 1.5` 且 `valuation_pct ≤ 30%` | deep_value_pb_max / deep_value_valuation_pct_max |
| 质量成长股票 | `roe ≥ 15%` 且 `revenue_growth ≥ 15%` | quality_growth_roe_min / quality_growth_revenue_growth_min |
| 红利稳健股票 | `dividend_yield ≥ 3%` | dividend_steady_yield_min |

按持仓权重汇总到基金级，达到门槛触发风格标签：

| 风格标签 | 触发门槛 | 当前触发数 |
|---|---|---|
| 深度价值 | 深度价值股票权重 ≥ 60% | 2 |
| 质量成长 | 质量成长股票权重 ≥ 50% | 9 |
| 红利稳健 | 红利股票权重 ≥ 50% | 1 |

#### 第三阶段：覆盖率检查（3 级门槛）

| 因子覆盖权重 | 系统处理 | 输出标签 |
|---|---|---|
| < 50% | 不输出正式风格标签 | style_exposure_low_coverage |
| 50% ~ 70% | 只输出观察 | style_exposure_observe |
| ≥ 70% | 进入正式风格判断 | 正式风格标签 |

当前 142 只里 136 只覆盖率 ≥ 70%，6 只在 50%-70% 观察区间。

#### 第四阶段：红利风格细分

| 情况 | 输出标签 | 当前触发数 |
|---|---|---|
| 行业映射覆盖不足 70% | 保留 dividend_steady + 追加 sector_mapping_insufficient | — |
| 金融 + 能源/公用事业红利贡献 ≥ 60% | high_dividend_financial | 1 |
| 消费行业红利贡献 ≥ 60% | consumer_quality | 0 |

#### 第五阶段：扩展风格标签

`_add_extended_style_labels()`（第 2787 行）。从持仓股票因子现算加权值：

```python
pb_weighted = Σ(weight × pb) / Σ(weight)     # 加权 PB
pe_weighted = Σ(weight × pe) / Σ(weight)     # 加权 PE
mcap_weighted = Σ(weight × mcap) / Σ(weight) # 加权对数市值
roe_weighted = Σ(weight × roe) / Σ(weight)   # 加权 ROE
pg_weighted = Σ(weight × pg) / Σ(weight)     # 加权利润增速
```

估值标签（校准后分位数阈值）：

| 标签 | 触发条件 | 校准后阈值 |
|---|---|---|
| 低估值 | PB ≤ P30 或 PE ≤ P30 | PB≤4.53 或 PE≤33.70 |
| 高估值 | PB ≥ P70 或 PE ≥ P70 | PB≥8.22 或 PE≥71.37 |

规模标签：

| 标签 | 触发条件 | 校准后阈值 |
|---|---|---|
| 大盘 | 加权市值 ≥ P50 | ≥10.99 |
| 中盘 | P30 ~ P70 | 10.82~11.15 |
| 小盘 | < P30 | <10.82 |

盈利/成长标签：

| 标签 | 触发条件 | 校准后阈值 |
|---|---|---|
| 高盈利质量 | ROE ≥ P70 | ≥13.26% |
| 利润高增长 | 利润增速 ≥ P65 | ≥34.97% |

#### 第六阶段：行业主题标签

`_add_industry_theme_labels()`（第 3016 行）：

| 标签 | 触发条件 | 当前触发数 |
|---|---|---|
| 科技主题 | 科技行业权重 ≥ 50% | 24 |
| 医药主题 | 医药行业权重 ≥ 50% | 8 |
| 消费主题 | 消费行业权重 ≥ 50% | 3 |
| 周期主题 | 周性行业权重 ≥ 50% | 3 |
| 金融主题 | 金融行业权重 ≥ 50% | 1 |

#### 第七阶段：风格组合标签

`_add_composite_style_labels()`（第 3053 行）：

| 标签 | 组合条件 | 当前触发数 |
|---|---|---|
| 大盘成长 | quality_growth + large_cap | 9 |
| 成长盈利 | quality_growth + profit_growth_strong | 9 |
| 价值质量 | low_valuation + high_roe | 8 |
| 价值红利 | low_valuation + dividend_steady | 1 |
| 高质量红利 | high_roe + dividend_steady | 1 |
| 小盘成长 | quality_growth + small_cap | 0 |

#### 第八阶段：均衡风格

`_maybe_emit_style_balanced()`（第 2738 行）：如果没有任何单一风格达到阈值，但有 2 个以上风格权重 ≥ 20%，判为"均衡风格"。

---

### 第 6 步：计算相对基准指标

#### 三个核心原则

1. 不是所有基金都统一和沪深 300 比
2. 基准要逐只解析，能拆组件就拆组件
3. 基准日收益源不可靠就不展示

#### 基准解析 4 步

**第一步**：读基准原文，比如 `沪深300指数收益率*80%+中证综合债指数收益率*20%`

**第二步**：检查是否是固定收益型基准（存款利率+X%、年化收益率X%）

**第三步**：按 `+` 拆组件，用 INDEX_MAP（60+ 个映射）匹配指数代码

**第四步**：按权重合成日收益

#### 指标计算方式（第 1799 行）

对齐方式：`n = min(len(fund_returns), len(benchmark_returns))`，从末尾截取（最新数据）。

| 指标 | 代码实现 | 小白理解 |
|---|---|---|
| 超额收益 | `active_cumulative = Π(1 + active_return)`，年化 | 比基准多赚多少 |
| 跟踪误差 | `std(active_returns) × √252` | 和基准偏离有多大 |
| 信息比率 | `annualized_excess / tracking_error` | 跑赢基准的效率 |
| Beta | `cov(fund, benchmark) / var(benchmark)` | 对基准涨跌的敏感度 |
| Alpha | `annualized_fund - beta × annualized_benchmark` | 扣掉基准影响后多出来的收益能力 |

#### 基准质量状态

| 状态 | 基金数 | 能否展示相对基准 |
|---|---|---|
| ready（精确源） | 111 | 能 |
| ready_approx（近似源） | 21 | 能（按近似口径解读） |
| missing_source | 5 | 不能（供应商授权指数：新华富时/FTSE/MSCI/ESG） |
| nav_window_insufficient | 4 | 不能（NAV 样本不足 180） |
| benchmark_missing | 1 | 不能（未披露基准） |

#### 基准数据源链路

| 数据源 | 覆盖组件 | 方式 |
|---|---|---|
| 东方财富 K线 API | 沪深300/中证500/上证50/创业板指等宽基及行业指数 | secid `1.xxx`/`0.xxx`/`2.xxx` 直接拉取 |
| akshare 中债登 | 中债综合/中债国债总/中债国债1-3年财富指数 | `fetch_cbond_index_returns.py` 精确源 |
| akshare 近似 | 中债总/中国债券总/标普中国债券 | `--include-approx` 用中债综合财富指数近似 |
| Investoday API | 中证全债(H11001)/中证综合债(H11009)/中证国债(H11006)/恒生指数(HSI) | `fetch_investoday_index_quotes.py` 精确源 |
| 确定性合成 | 银行存款利率/固定年化收益率 | 按年化折算日收益 |

#### 关键原则

宁可标记为缺失，也不用错误基准替代。

---

### 第 7 步：按规则打标签

#### 标签触发顺序

```
_add_holding_labels          # 持仓结构标签
_add_industry_labels         # 行业集中标签
_add_equity_position_labels  # 权益仓位标签
_add_risk_labels             # 收益风险标签
_add_relative_benchmark_labels  # 相对基准标签
_add_manager_labels          # 经理标签
_add_fee_labels              # 费率标签
_add_fund_size_labels        # 规模标签
_add_style_boundary_labels   # 风格边界标签
_add_extended_style_labels   # 扩展风格标签
```

#### 三种计算状态

| 状态 | 含义 | 举例 |
|---|---|---|
| triggered | 数据有，指标达到门槛 | 年化收益 25%，达 15% 门槛 |
| not_triggered | 数据有，指标没到门槛 | 经理任期 2 年，没到 5 年 |
| not_computed | 数据不够，不能算 | 没费率数据，不知道费率高低 |

#### 每个标签都留证据

| 字段 | 含义 | 举例 |
|---|---|---|
| label_code | 标签代码 | high_valuation |
| metric | 指标名 | pb_weighted/pe_weighted |
| value | 指标值 | PB=14.74, PE=134.10 |
| threshold | 阈值 | PB≥8.0 或 PE≥40.0 |
| source | 数据来源 | stock_factor_values |
| message | 白话解释 | 加权 PB=14.74，加权 PE=134.10，达到高估值阈值。 |

#### 规则启停机制

`disabled_rules` 可以停用特定标签。但 data_quality/review 类标签不可停用。

---

### 第 8 步：分类、分组、展示状态

#### 分类（4 个维度）

| 维度 | 分类代码 | 判断方式 | 当前数量 |
|---|---|---|---|
| 资产大类 | equity_related | 类型 ∈ 四类之一 | 142 |
| 管理方式 | active / passive_index | 名称关键词 | 128 / 14 |
| 计算资格 | label_ready / data_gap | 数据 gate | 142 / 0 |
| 风格清晰度 | style_clear / style_pending / style_factor_missing | 风格标签触发情况 | 14 / 128 / 0 |

#### 分组

| 分组 | 进入条件 | 当前数量 |
|---|---|---|
| label_ready_pool | 数据 gate 通过 | 142 |
| passive_tool_pool | 被动指数 | 14 |
| active_equity_candidate_pool | 主动 + 数据充足 + 经理达标 + 未触发规模偏小 | 79 |
| 风格分组 | 每触发一个风格标签进入对应分组 | — |
| high_return_high_drawdown_watch | 同时触发长期收益优秀 + 回撤较大 | — |
| industry_concentration_watch | 触发行业高度集中或行业集中观察 | 128 |

#### 展示状态

| 展示状态 | 基金数 | 说明 |
|---|---|---|
| 基础标签可展示 | 142 | 收益、风险、持仓、经理、费率、风格标签 |
| 相对基准标签可展示（精确） | 111 | Alpha、Beta、超额收益、信息比率 |
| 相对基准标签可展示（近似） | 21 | 使用近似债券指数源，需按近似口径解读 |
| 相对基准标签暂不可展示 | 10 | 5 只缺供应商授权指数 + 4 只 NAV 不足 + 1 只未披露基准 |

#### 同类排名分位数（跑批后计算）

8 个关键指标 × 多个分组维度，6800+ 条记录。

#### 最终输出

每只基金输出一个 `EngineResult` 对象，包含 labels、evidence、features、calculations、classifications、groups、coverage、review_action。

---

## 第四部分：基准处理

### 4.1 INDEX_MAP 覆盖范围

| 指数类别 | 举例 | 数据源 |
|---|---|---|
| 宽基指数 | 沪深300、中证500、中证800、中证1000、上证50、创业板指、科创50 | 东方财富 |
| 行业指数 | 中证医药、中证消费、中证军工、中证环保 | 东方财富 |
| 主题指数 | 中证TMT、中证红利、高端装备 | 东方财富 |
| 债券指数 | 中证全债、中证国债、中证综合债 | 新浪/本地 |
| 港股指数 | 港股通大消费 | 东方财富 |

### 4.2 找不到组件数据源怎么办

| 情况 | 举例 | 处理方式 |
|---|---|---|
| 组件认得但缺数据源 | 中债总指数 | 标记"缺收益源"，不用替代 |
| 存款利率 | 银行活期存款利率(税后) | 用固定年化 0.35% 换算日收益 |
| 固定年化 | "2.5%(指年收益率)" | 按交易日折算日收益 |
| 完全认不出 | 新华富时中国A200指数 | 标记"缺收益源" |

### 4.3 相对基准标签（7 个）

| 标签 | 触发条件 | 阈值 | 当前触发数 |
|---|---|---|---|
| excess_return_strong | 年化超额 ≥ 5% | 0.05 | 83 |
| information_ratio_high | 信息比率 ≥ 0.5 | 0.5 | 67 |
| tracking_error_high | 跟踪误差 ≥ 8% | 0.08 | 132 |
| alpha_positive | Alpha ≥ 3% | 0.03 | 110 |
| beta_high | Beta ≥ 1.2 | 1.2 | 0 |
| beta_low | Beta ≤ 0.8 | 0.8 | 132 |
| benchmark_data_missing | 基准数据缺失 | — | 10 |

---

## 第五部分：标签体系

### 5.1 标签全景（50+ 个，分 5 层）

#### 第 1 层：数据质量标签

| 标签 | 触发条件 | 当前触发数 |
|---|---|---|
| data_sufficient | 必要数据覆盖率达标 | 142 |
| data_insufficient | 缺必要数据 | 0 |
| manual_review_required | 需人工复核 | 0 |

#### 第 2 层：收益风险标签

| 标签 | 触发条件 | 当前触发数 |
|---|---|---|
| long_term_return_strong | 年化收益 ≥ 15% | 214 |
| sharpe_high | 夏普 ≥ 1.0 | 210 |
| drawdown_high | 最大回撤 ≤ -20% | 58 |
| volatility_high | 年化波动 ≥ 30% | 46 |
| volatility_low | 年化波动 ≤ 12% | 10 |

#### 第 3 层：持仓结构标签

| 标签 | 触发条件 | 当前触发数 |
|---|---|---|
| equity_position_high | 权益仓位 ≥ 80% | 246 |
| holding_concentration_high | 前十大持仓 ≥ 55% | 40 |
| industry_concentration_high | 第一大行业 ≥ 60% | 170 |
| industry_concentration_observe | 第一大行业 45%-60% | — |
| industry_diversified | 第一大行业 < 20% 且行业数 ≥ 5 | — |

#### 第 4 层：描述性标签（不展示在风格区）

| 标签 | 触发条件 | 当前触发数 |
|---|---|---|
| manager_tenure_long | 任期 ≥ 5 年 | 215 |
| fee_low | 综合费率 ≤ 1.2% | 53 |
| fee_high | 综合费率 > 2.5% | 2 |
| fund_size_moderate | 规模 5-100 亿 | 104 |
| fund_size_small | 规模 < 1 亿 | 66 |

#### 第 5 层：风格标签（23 个，核心价值）

**估值维度（3 个）**

| 标签 | 校准后阈值 | 触发数 |
|---|---|---|
| 高估值 | PB≥P70 或 PE≥P70 | 61(43%) |
| 低估值 | PB≤P30 或 PE≤P30 | 42(30%) |
| 深度价值 | 深度价值股票权重≥40% | 2 |

**规模维度（3 个）**

| 标签 | 校准后阈值 | 触发数 |
|---|---|---|
| 大盘 | 市值≥P50 | 71(50%) |
| 中盘 | P30~P70 | 27(19%) |
| 小盘 | <P30 | 40(28%) |

**盈利/成长维度（2 个）**

| 标签 | 校准后阈值 | 触发数 |
|---|---|---|
| 高盈利质量 | ROE≥P70 | 42(30%) |
| 利润高增长 | 增速≥P65 | 77(54%) |

**红利维度（3 个）**

| 标签 | 触发条件 | 触发数 |
|---|---|---|
| 红利稳健 | 红利股票权重≥50% | 1 |
| 金融高股息 | 金融+能源红利贡献≥60% | 1 |
| 消费质量 | 消费红利贡献≥60% | 0 |

**行业主题（5 个）**

| 标签 | 触发条件 | 触发数 |
|---|---|---|
| 科技主题 | 科技行业权重≥50% | 24 |
| 医药主题 | 医药行业权重≥50% | 8 |
| 消费主题 | 消费行业权重≥50% | 3 |
| 周期主题 | 周性行业权重≥50% | 3 |
| 金融主题 | 金融行业权重≥50% | 1 |

**组合风格（6 个）**

| 标签 | 组合条件 | 触发数 |
|---|---|---|
| 大盘成长 | quality_growth + large_cap | 9 |
| 成长盈利 | quality_growth + profit_growth_strong | 9 |
| 价值质量 | low_valuation + high_roe | 8 |
| 价值红利 | low_valuation + dividend_steady | 1 |
| 高质量红利 | high_roe + dividend_steady | 1 |
| 小盘成长 | quality_growth + small_cap | 0 |

### 5.2 标签校准效果对比

| 问题 | 校准前 | 校准后 |
|---|---|---|
| 大盘独大 | 81% | 50%（正常） |
| 小盘失效 | 1% | 28%（恢复） |
| 高估值过多 | 68% | 43%（正常） |
| 低估值过少 | 11% | 30%（正常） |
| 因子脏值 | PB 最小-1555 | 已清洗截断 |
| 阈值不适应市场 | 写死绝对值 | 横截面分位数 |

---

## 第六部分：同类排名分位数系统

### 做了什么

为 142 只基金 × 8 个关键指标 × 多个分组维度计算百分位排名，共 6800+ 条记录。

| 维度 | 内容 |
|---|---|
| 指标 | 年化收益、夏普、最大回撤、超额收益、信息比率、加权 ROE、加权 PE、加权 PB |
| 分组 | 全市场（142 只）+ 每个风格标签分组 |
| 输出 | 百分位 [0,1] + 排名 + 同类总数 |
| 方向 | higher_better / lower_better |

### 实际案例

基金 000017：
- 年化收益：全市场 106 只里排第 4（前 3%），在 quality_growth 同类 9 只里排第 3（前 25%）
- 夏普比率：全市场排第 3（前 2%）

---

## 第七部分：竞品横评工作台

### 四个对比模块

| 模块 | 功能 |
|---|---|
| 核心指标对比表 | 8 个指标并排，★ 标最优值，每格附分位排名 |
| 风格雷达图 | 5 维（估值/成长/红利/规模/盈利）SVG 雷达图，多基金叠加 |
| 风格标签矩阵 | 23 个标签 × N 只基金，✓ 命中 / — 未命中 |
| 持仓重叠度 | 前 10 大持仓的两两重叠权重 + 共同持仓明细 |

---

## 第八部分：FOF 组合工作台

### 做了什么

| 功能 | 说明 |
|---|---|
| 角色推导 | 根据标签自动分类：核心候选/卫星阿尔法/防守锚/指数工具/低成本 |
| 风险约束 | 高回撤标签收紧权重上限，硬阻断标签直接排除 |
| 组合草案 | 评分排序→排除硬阻断→按桶分配→应用上限→重新分配 |
| 人工校准 | 研究员可签署 accept/reject/needs_more_data |

### 当前结果

| 角色 | 数量 | 权重上限 |
|---|---|---|
| 核心候选 | 9 只 | 6-8% |
| 卫星阿尔法 | 11 只 | 3-5% |
| 指数工具 | 8 只 | 3% |
| 被排除 | 54 只 | — |
| 进入草案 | 88 只 | — |

### 缺口

缺相关性矩阵——如果核心池 9 只基金买的是同一批股票，分散风险效果打折扣。

---

## 第九部分：前端工作台（9 个页面）

| 页面 | 功能 | 面向谁 | 完成度 |
|---|---|---|---|
| 风格总览 | 标签分布 + 同类 TOP 5 | 所有人 | ✅ |
| 风格筛选 | 按标签/分组筛选 | 投研 | ✅ |
| 竞品横评 | 多基金并排对比 | 投研 | ✅ |
| 基金报告 | 单只基金体检 | 投研 | ✅ |
| 展示池 | 114 可展示 vs 28 不可展示 | 产品 | ✅ |
| 组合工作台 | FOF 子基金筛选 | FOF 经理 | 50% |
| 复核队列 | 人工复核标签 | 研究员 | ✅ |
| 批次管理 | 跑批记录 | 运维 | ✅ |
| 批次对比 | 两次跑批 diff | 运维 | ✅ |

---

## 第十部分：工程化

| 维度 | 实现 |
|---|---|
| 一键跑批 | `make run-batch-v1` |
| CI/CD | GitHub Actions：pytest + 前端 build + smoke test |
| 测试 | 35+ 个测试文件 |
| API | FastAPI，30+ 个 RESTful 端点 |
| 前端 | React + TypeScript + Vite |
| 数据库 | SQLite（轻量，单文件） |
| 配置 | 阈值/规则/约束均 JSON 配置 |
| 迁移 | 10 个 SQL migration 文件 |

---

## 第十一部分：当前卡点

| 卡点 | 状态 | 影响 | 解决方案 |
|---|---|---|---|
| 5 只缺供应商授权指数 | 需采购 | 不能算 Alpha/Beta | 采购新华富时/FTSE/MSCI/ESG 数据 |
| 4 只 NAV 样本不足 | 需时间积累 | 不能算收益风险标签 | 积累更多交易日数据 |
| 持仓只有一期 | 需时间积累 | 风格只能作研究线索 | 每季度跑批积累 |
| 组合缺相关性 | 未做 | FOF 不敢直接用 | 4-5 天可做 |
| 标签时序 | 未做 | 没法看标签变化 | 每月跑批积累 |

---

## 第十二部分：领导可能关心的问题

### Q1：系统能直接用吗？

基础功能可以用了：142 只基金的标签、证据、同类排名、竞品横评都能看。132 只基金有完整的相对基准标签（Alpha/Beta/超额收益），覆盖率 93%。3 个限制：① 5 只缺供应商授权指数数据；② 4 只 NAV 样本不足；③ 持仓只有一期。

### Q2：数据从哪来？要花钱吗？

大部分数据免费已有。基准日收益已通过多数据源拼接完成：东方财富（宽基/行业指数）、akshare（中债登财富指数）、Investoday API（中证债券指数/恒生指数）。唯一采购需求：5 只基金的供应商授权指数（新华富时/FTSE/MSCI/ESG）。

### Q3：142 只够不够？

142 只是第一版正式清单。扩展不需要改引擎，只需数据接入。

### Q4：标签准不准？

- 基础标签：**准确**，直接算
- 风格标签：**校准后可用**，触发率 20-50%
- 相对基准标签：**132 只准确**（111 只精确源 + 21 只近似源），10 只暂缺
- 所有标签有证据链，可追溯

### Q5：跟市面评价系统区别？

1. 基准精确解析——逐只拆解，不用错误代理
2. 证据链完整——每个标签可追溯"为什么"
3. 横截面分位数——不仅说"是不是"，还说"排第几"

### Q6：下一步做什么？

1. 组合相关性矩阵（4-5 天，数据已有）
2. 标准化报告导出（2-3 天）
3. 标签时序追踪（需多期积累）

---

## 第十三部分：7 个补充问题详解

### 问题 1：基金类型怎么判断的，判断逻辑是否合理

**怎么判断的**：基金类型直接从数据库 `fund_profiles` 表的 `fund_type` 字段读取，是数据源在抓取基金基础信息时已经分类好的。

**合理性**：基本合理，但有 3 个需要注意的点：

| 点 | 说明 | 是否需要改 |
|---|---|---|
| 信任数据源分类 | fund_type 来自 fundData 库，是基金公司合同约定的类型 | 合理 |
| 四类覆盖了权益基金 | 股票型 + 偏股 + 灵活 + 指数股票 | 合理 |
| **混合型-灵活的歧义** | 灵活配置基金的股票仓位可能在 0-95% 之间波动 | **需要关注** |

**建议改进**：在数据门禁阶段加一个"类型与实际仓位一致性检查"——如果一只"混合型-灵活"基金的权益仓位长期 < 30%，应该标记为"类型与实际不符，需人工复核"。

### 问题 2：用名称含"指数/ETF/联接/INDEX"判断被动指数是否合理

**当前逻辑**：engine.py 第 1313 行，把 fund_type 和 fund_name 拼接后检查关键词。

**合理性**：基本合理，但有 3 个边界情况会误判：

| 边界情况 | 举例 | 误判方向 |
|---|---|---|
| 主动基金名字含"指数" | "XX指数增强" | 误判为被动 |
| 量化基金名字含"指数" | "XX量化指数" | 可能误判 |
| QDII 含"INDEX" | "XX纳斯达克100指数" | 不影响（类型过滤已排除） |

**当前数据不会出问题的原因**：第一层过滤已锁在四类，fund_type 字段本身已区分"指数型-股票"和"股票型"。

**建议改进**：
- 排除"指数增强"
- 优先用 fund_type 判断
- 改进逻辑：`如果 fund_type == "指数型-股票" → 被动；否则如果名称含"ETF/联接/INDEX"且不含"增强" → 被动；否则 → 主动`

### 问题 3：数据门禁的门槛设置是否合理

**完整门槛列表**：

| 检查项 | 门槛值 | 合理性 |
|---|---|---|
| NAV 日收益样本 | ≥ 180 条 | 合理（≈9 个月，给数据缺口留容错） |
| 股票持仓条数 | ≥ 1 条 | 偏宽松（真正的约束在总权重） |
| 持仓总权重 | ≥ 50% | 合理 |
| 行业配置条数 | ≥ 1 条 | 偏宽松 |
| 经理/费率/规模/仓位 | 不为 None | 合理（"有没有"检查） |
| 持仓/行业过期天数 | ≤ 配置值 | 合理且重要 |
| 收益窗口 | NAV ≥ 1y 窗口最小样本 | 合理 |

**建议改进**：
- 持仓条数门槛：从 ≥ 1 条提高到 ≥ 5 条
- 权益仓位门槛：不同类型应该有不同门槛（股票型 ≥ 80%，混合型-灵活可以更低）

### 问题 4：计算基础指标具体做了什么

**完整指标清单**：

A. 收益风险指标（按 4 个窗口 + full 窗口）：period_return、annualized_return、annualized_volatility、max_drawdown、sharpe_ratio、sample_count

B. 相对基准指标（按 4 个窗口 + full 窗口）：benchmark_sample_count、annualized_benchmark_return、annualized_excess_return、tracking_error、information_ratio、beta、alpha

C. 持仓结构指标：top_10_holding_weight、stock_holding_count、industry_top1_weight、industry_top3_weight、industry_count

D. 基础信息指标：equity_position、manager_tenure_years、total_annual_fee、fund_size

**具体考虑**：
1. 按多个窗口计算（1m/3m/1y/3y），只有 1y 和 3y 能触发正式标签
2. full 窗口只用于排查
3. 负累计收益返回 -1.0 避免数学错误
4. 夏普无风险利率按 0（已知简化）
5. 对齐方式取共同可用天数，从末尾截取
6. 每个指标都记录来源

### 问题 5：计算持仓风格的合理性

**A. 高级风格标签（3 个）**：基于股票特征 + 持仓权重，股票特征条件来自经典投资理论。合理，但深度价值门槛 60% 偏高，建议降到 50%。

**B. 扩展风格标签（6 个）**：基于加权因子 + 分位数阈值，校准后触发率稳定在 20-50%。合理，但利润高增长 P65 仍触发 54%，建议提到 P70。

**C. 行业主题标签（5 个）**：基于持仓股票行业归属，50% 门槛合理。但行业分类只有 7 类，比较粗，建议增加细分（如新能源、半导体）。

**D. 组合风格标签（6 个）**：两个基础标签同时命中时生成，逻辑简单清晰，贴近投研语言。合理。

**需要改进的部分**：

| 改进点 | 当前 | 建议 |
|---|---|---|
| 深度价值门槛 | 60% | 降到 50% |
| 利润高增长分位 | P65 | 提到 P70 |
| 行业分类粒度 | 7 类 | 增加细分 |
| 风格稳定性 | 单期快照 | 需多期积累 |

### 问题 6：现在的基准标签都有哪些，怎么展现出来的

**基准解析流程**：读基准原文 → 检查是否固定收益型 → 按 `+` 拆组件 → 用 INDEX_MAP 匹配指数代码 → 按权重合成日收益

**INDEX_MAP 覆盖**：60+ 个映射，覆盖宽基指数、行业指数、主题指数、债券指数、港股指数

**7 个相对基准标签**：excess_return_strong（66）、information_ratio_high（56）、tracking_error_high（114）、alpha_positive（88）、beta_high（1）、beta_low（105）、benchmark_data_missing（28）

**展现方式**：
- 基准数据可用（132 只）：按窗口计算 6 个指标，逐个判断触发
- 基准数据缺失（10 只）：输出 benchmark_data_missing 标签，不展示 Alpha/Beta/超额收益

### 问题 7：其他做了什么，接下来需要做什么

**其他已做的工作**：
- 风格稳定性标签（需多期数据）
- 均衡风格标签（触发较少）
- 同类排名分位数系统（6800+ 条记录）
- 竞品横评工作台（4 个对比模块）
- FOF 组合工作台（角色推导 + 组合草案）
- 前端工作台（9 个页面）
- 工程化（一键跑批 + CI/CD + 35+ 测试）

**接下来需要做什么**（按优先级）：

| 优先级 | 任务 | 工作量 | 数据基础 |
|---|---|---|---|
| 1 | 组合相关性矩阵 | 4-5 天 | 已有 |
| 2 | 标准化报告导出 | 2-3 天 | 已有 |
| 3 | 5 只基准数据源采购 | 采购后 1-2 天 | 需采购 |
| 4 | 标签时序追踪 | 5-7 天 | 需积累 |
| 5 | 经理监控面板 | 3-4 天 | 已有 |
| 6 | 行业分类细化 | 2-3 天 | 需补充映射 |
| 7 | 风格门槛微调 | 1 天 | 已有 |
| 8 | 类型与仓位一致性检查 | 1 天 | 已有 |

---

## 第十四部分：下一步规划

### 短期（1-2 周）

1. 做组合相关性矩阵——当前唯一能用现有数据解决的重大缺口
2. 做标准化报告导出——让结果能交付
3. 微调风格门槛——深度价值降到 50%，利润高增长提到 P70

### 中期（1-2 个月）

4. 采购 28 只基准数据源
5. 积累多期持仓数据，做标签时序追踪
6. 细化行业分类

### 长期

7. 扩展基金范围（从 142 只到更多）
8. 增加债券基金/货币基金的标签体系

---

## 附录：项目最大价值

不是 142 只的标签结果，而是建立了一套**方法论和工程框架**：数据门禁→指标计算→规则标签→证据落库→计算状态→分类分组→基准门禁→组合草案。把基金研究流程标准化、可审计、可复现。
