# 阶段 0 · 私募内部投研 smoke 演示报告

> 生成时间:`2026-07-17T05:53:34Z`
> data_snapshot_id:`snap_smoke`
> strategy_policy_id + version:`private_equity_growth` + `v1`
> business_mode:`private_strategy`(主业务)
> sample_db:`/tmp/fle-p0/source.sqlite`(来源:`scripts/seed_sample_db.py`)

---

## 0. 阶段 0 纪律自检

- [x] 未写新业务代码(`backend/app/` 未变更)
- [x] 未建新表
- [x] 每个 candidate 都能反查 `research_input_id` / `strategy_policy_id` / `data_snapshot_id`
- [x] 不强制固定数量候选;无候选时输出 `no_eligible_candidate`
- [x] 使用 `seed_sample_db.py` 真实样例数据,无伪造

## A · 投资观点

- research_input_id:`ri_test_rec_api_a`
- thesis_id:`th_0f182ede834d`
- candidate_set_id:`cs_ee14853d11a5`
- persist_status:`created`
- actor_role:`researcher`
- raw_text:"我看好消费白马(高 ROE、稳定盈利、低估值的龙头企业)。"
- data_snapshot_id:`snap_smoke`
- strategy_policy_id:`private_equity_growth` (version=1)

### 投资假设

- title:消费白马配置假设
- belief_statement:我看好消费白马(高 ROE、稳定盈利、低估值的龙头企业)。
- time_horizon:P12M
- candidate_status:**candidates**

### 候选集合(1 个)

| asset_code | asset_name | 证据 | as_of_date |
|---|---|---|---|
| `000001` | 样例消费股票 | `{"consumer_blue_chip_holding_weight": 0.327, "industry_exposure": [{"industry": "医药", "weight": 0.05}, {"industry": "家电", "weight": 0.05}, {"industry": "汽车", "weight": 0.04}, {"industry": "电力设备", "weight": 0.05}, {"industry": "电池", "weight": 0.05}, {"industry": "银行", "weight": 0.05}, {"industry": "非银金融", "weight": 0.06}, {"industry": "食品饮料", "weight": 0.5}]}` | 2026-03-31 |

---

## B · 行业方向

- research_input_id:`ri_test_rec_api_b`
- thesis_id:`th_ebf44d6d6e01`
- candidate_set_id:`cs_39c395eaccb8`
- persist_status:`created`
- actor_role:`researcher`
- raw_text:"我看好食品饮料行业的稳定盈利能力。"
- data_snapshot_id:`snap_smoke`
- strategy_policy_id:`private_equity_growth` (version=1)

### 投资假设

- title:食品饮料 行业暴露假设
- belief_statement:我看好食品饮料行业的稳定盈利能力。
- time_horizon:P12M
- candidate_status:**candidates**

### 候选集合(1 个)

| asset_code | asset_name | 证据 | as_of_date |
|---|---|---|---|
| `000001` | 样例消费股票 | `{"食品饮料_exposure": 0.5}` | 2026-03-31 |

---

## C · 具体标的

- research_input_id:`ri_test_rec_api_c`
- thesis_id:`th_f82d1d2ecc2c`
- candidate_set_id:`cs_8b38028fecbd`
- persist_status:`created`
- actor_role:`researcher`
- raw_text:"我想知道哪些基金重仓了贵州茅台(600519)。"
- data_snapshot_id:`snap_smoke`
- strategy_policy_id:`private_equity_growth` (version=1)

### 投资假设

- title:重仓 600519 贵州茅台 的基金假设
- belief_statement:我想知道哪些基金重仓了贵州茅台(600519)。
- time_horizon:P12M
- candidate_status:**candidates**

### 候选集合(1 个)

| asset_code | asset_name | 证据 | as_of_date |
|---|---|---|---|
| `000001` | 样例消费股票 | `{"stock_weight_in_fund": 0.153, "stock_name_in_holding": "贵州茅台", "report_date": "2026-03-31"}` | 2026-03-31 |

---

## 阶段 0 出口检查(对应 phase0-acceptance.md)

- [x] 默认模式已确认:`private_strategy`
- [x] FOF 模式已标记为扩展样例(`foof_growth_v0.yaml: approved_for_production: false`)
- [x] 3 个研究请求场景均已跑通
- [x] 每个结果都包含 5 个 ID 字段
- [x] 候选可以反查输入、策略和快照
