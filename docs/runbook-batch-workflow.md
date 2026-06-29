# Phase 1 批量跑批工作流（runbook）

这份文档把 phase1 168 只基金的端到端跑批流程写下来，覆盖：
数据准备 → 因子横截面 → NAV 历史 → 标签批处理 → 验证。
完成 phase1 数据接入（2026-06 之前的 P0~P3）后，所有步骤都已经
被脚本和 Makefile 固化，可以一键重复执行。

## 涉及的产物

| 产物 | 路径 | 说明 |
|---|---|---|
| Phase1 基金清单 | `data/phase1_fund_codes.txt` | 168 只首期范围，每行一个 fund_code |
| 股票因子缓存 DB | `data/stock_factors.sqlite` | 独立 SQLite，存全 A 横截面因子 |
| 规则配置 | `config/rules.v1.json` | v1 阈值和 gate 配置，跑批时写入 rule snapshot |
| 基准组件收益源 | `benchmark_component_returns` | 可选表，存债券/行业/主题/港股指数日收益 |
| 源数据库（拷贝） | `/tmp/fle-run/source.sqlite` | fundData cache DB 的工作副本 |
| 输出库 | `/tmp/fle-run/output.sqlite` | 单次跑批的 label_runs / fund_label_results |

## 一、Make 入口

```bash
make help              # 看所有任务
make refresh-factors   # 拉股票因子横截面（PE/PB/ROE/分红/...），写 data/stock_factors.sqlite
make refresh-nav       # 分页拉 phase1 168 只 1Y NAV，写 fundData cache DB
make copy-source       # 把 fundData cache DB 复制到 /tmp/fle-run/source.sqlite
make run-batch         # 跑批：依赖 copy-source；自动外挂 factor DB
make test              # 跑后端 pytest
```

参数都在 Makefile 顶部 `?=` 处可覆盖。日常用：

```bash
make refresh-factors TRADE_DATE=2026-06-23 REPORT_DATE=2025-09-30
make refresh-nav      NAV_START=2025-06-01 NAV_END=2026-06-23
make run-batch
```

## 二、数据源拓扑

```
        ┌──────────────────────────────────────────┐
        │  fundData 真库（~/.cache/fund-data/...）  │
        │   fund_profiles / nav_history /          │
        │   stock_holdings / industry_allocations /│
        │   fee_structures / fund_manager_links    │
        └──────────────┬───────────────────────────┘
                       │ make copy-source
                       ▼
        ┌──────────────────────────────┐       ┌──────────────────────────┐
        │  /tmp/fle-run/source.sqlite  │       │  data/stock_factors.sqlite│
        │   只读，作为 batch 输入      │  ◄──  │  ATTACH 进同一连接       │
        └──────────────┬───────────────┘       │  stock_factor_values     │
                       │ make run-batch        └──────────────────────────┘
                       ▼
        ┌──────────────────────────────┐
        │  /tmp/fle-run/output.sqlite  │
        │   label_runs / 标签 / 证据   │
        └──────────────────────────────┘
```

### 为什么 factor 表是独立的 DB

`data/stock_factors.sqlite` 由 [scripts/fetch_stock_factors.py](../scripts/fetch_stock_factors.py)
生成，包含 PE/PB/ROE/dividend_yield 等全 A 横截面因子。它和 fundData 真库分开，
有两个原因：

1. **不污染上游**：fundData 是被 fundData 自己同步流程维护的，加入因子表会让
   schema 漂移。
2. **可独立刷新**：因子横截面每日变化，但基金画像变化慢，分开维护更自然。

`FundDataRepository._connect()` 在传入 `factor_db_path` 时，会用
`ATTACH DATABASE` 把它挂上，并通过 TEMP VIEW 让 `load_stock_factors` 透明指向
外挂表。读取层（`data_access/stock_factors.py`）感受不到差异。

真实双库跑批现在会自动校验权益因子链路：

- 跑前要求 source DB 或 `--factor-db` 中存在非空 `stock_factor_values` / `stock_factors`。
- 跑后要求输出库写出 `fund_factor_exposures`。
- 跑后要求至少有基金进入 `style_factor_ready_pool`。
- 跑后要求 `deep_value` / `quality_growth` / `dividend_steady` 至少被正式评估过。

如果只是构造一个没有股票因子的小样本 smoke，可以显式传
`--skip-equity-factor-check`，但真实 fundData 跑批不要跳过这个校验。

## 三、Phase1 范围控制

环境变量 `FLE_PHASE1_CODES_FILE` 指向一份 fund_code 清单时，
`FundDataRepository.list_supported_fund_codes` 会把候选基金交集到清单内：

```python
# backend/app/data_access/funddata_repository.py
phase1 = _read_phase1_codes()
if phase1 is not None:
    codes = [c for c in codes if c in phase1]
```

不设这个变量则保留原来"按 fund_type 过全 A"的行为。

`make run-batch` 默认会设上 `FLE_PHASE1_CODES_FILE=data/phase1_fund_codes.txt`，
所以你拿到的就是 168 只这一档。

## 四、典型一次性跑批

冷启动场景（什么都没有，要从头跑通 168 只）：

```bash
# 1. 拉 NAV 历史（约 5–10 分钟，单线程会更慢一些）
make refresh-nav

# 2. 拉股票因子横截面（约 5 分钟，包含分红聚合）
make refresh-factors

# 3. 跑批（约 30 秒）
make run-batch

# 4. （可选）跑测试确认没回归
make test
```

热启动（只是想换一个日期或者阈值，重跑标签）：

```bash
make run-batch
```

## 五、可调阈值

Makefile 当前 `run-batch` 写死的组合：
`--rule-config config/rules.v1.json --min-nav-samples 180 --deep-value-weight-min 0.4 --quality-growth-weight-min 0.4`。
风格阈值压到 0.4 是为了让小规模 168 只数据集里能看到样本（生产线上是否要保留
默认 0.5/0.6 由产品决定）。

`--rule-config` 从 JSON 读取完整阈值；命令行上的单项参数优先级更高，适合临时校准。

| 参数 | 默认 | 说明 |
|---|---|---|
| `--rule-config` | 无 | JSON 规则配置文件，例如 `config/rules.v1.json` |
| `--min-nav-samples` | RuleConfig 默认 | NAV 样本数 gate；做 1Y 标签时设 180 |
| `--min-holding-total-weight` | RuleConfig 默认 | 持仓穿透总权重 gate |
| `--deep-value-weight-min` | 配置文件/RuleConfig | 深度价值的持仓权重阈值 |
| `--quality-growth-weight-min` | 配置文件/RuleConfig | 质量成长的持仓权重阈值 |
| `--factor-db` | 无 | 外挂股票因子 SQLite 路径 |

## 六、各因子来源对照

`data/stock_factors.sqlite` 里的字段：

| factor_code | 单位 | 来源 |
|---|---|---|
| `pe` | 倍数 | 东财 RPT_VALUEANALYSIS_DET / PE_TTM |
| `pb` | 倍数 | 东财 RPT_VALUEANALYSIS_DET / PB_MRQ |
| `log10_market_cap` | log10(元) | 东财 RPT_VALUEANALYSIS_DET / TOTAL_MARKET_CAP 取对数 |
| `close_price` | 元 | 东财 RPT_VALUEANALYSIS_DET / CLOSE_PRICE |
| `roe` | 小数 | 东财 RPT_LICO_FN_CPD / WEIGHTAVG_ROE ÷ 100 |
| `revenue_growth` | 小数 | 东财 RPT_LICO_FN_CPD / YSTZ ÷ 100 |
| `profit_growth` | 小数 | 东财 RPT_LICO_FN_CPD / SJLTZ ÷ 100 |
| `valuation_percentile` | 0~1 | PB 横截面 (rank+0.5)/n |
| `dividend_yield` | 小数 | TTM 分红/10/close_price，来自 RPT_SHAREBONUS_DET |

> 提醒：`PRETAX_BONUS_RMB` 单位是「元/10股」，所以每股分红 = `SUM(PRETAX_BONUS_RMB)/10`。
> compute_dividend_yield 已经处理。

## 七、相对基准组件收益源

`scripts/fetch_benchmark_returns.py` 会把 benchmark 文本解析成组件，并写入
`benchmark_components` 审计表。v3 支持优先读取本地稳定组件收益表：

```sql
CREATE TABLE IF NOT EXISTS benchmark_component_returns (
  component_code TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  daily_return REAL NOT NULL,
  source TEXT,
  fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (component_code, trade_date)
);
```

推荐先把外部稳定来源整理进这个表，再运行 benchmark 脚本。当前内置的本地组件代码包括：

| component_code | 典型文本 |
|---|---|
| `LOCAL_CBOND_COMPOSITE` | 中债综合指数 / 中债-综合指数 / 中国债券综合指数 |
| `LOCAL_CBOND_TOTAL` | 中债总指数 / 中债-总指数 |
| `LOCAL_CHINA_BOND_TOTAL` | 中国债券总指数 |
| `LOCAL_CBOND_GOV_TOTAL` | 中债国债总指数 |
| `LOCAL_CBOND_GOV_1_3Y` | 中债-国债总(1-3年)指数 |
| `LOCAL_SP_CHINA_BOND` | 标普中国债券指数 |

原则：没有可靠日收益源时保留 `benchmark_data_missing`，不使用不相干指数做代理。

## Benchmark Quality Gate

相对基准标签只允许在 benchmark quality 为 `ready` 的基金上解释和展示。

运行顺序：

```bash
make run-batch-v1-with-benchmark \
  PYTHON=.venv/bin/python \
  OUTPUT_DB=/tmp/fle-run/output-v1-with-benchmark.sqlite
```

输出文件：

- `reports/phase1-real-run-2026-06-29/benchmark-mapping.csv`
- `reports/phase1-real-run-2026-06-29/benchmark-quality.csv`
- `reports/phase1-real-run-2026-06-29/benchmark-quality-gate.md`

状态含义：

| status | 含义 | 是否允许相对基准标签 |
|---|---|---|
| `ready` | 组件映射明确，且有可用日收益序列 | 是 |
| `missing_source` | 组件映射明确，但缺少可靠日收益源 | 否 |
| `mapping_required` | 文本命中高风险宽指数，必须补精确映射 | 否 |
| `unresolved` | 暂不支持或解析失败 | 否 |
| `benchmark_missing` | 基金未披露基准 | 否 |

原则：宁可缺失，也不使用宽指数代理。比如 `沪深300金融地产行业指数` 不得自动退化为普通 `沪深300`。

## 八、当前能产出的标签（截至 2026-06-25）

跑 phase1 168 只的典型分布：

```
data_sufficient                154
fee_low                        152
industry_concentration_high    131
manager_tenure_long            122
equity_position_high           120
sharpe_high                    119
long_term_return_strong        112
fund_size_moderate              64
fund_size_small                 42
drawdown_high                   30
volatility_high                 23
holding_concentration_high      20
volatility_low                  17
manual_review_required          14
data_insufficient               14
return_window_insufficient      12
industry_diversified            11
quality_growth                   9
dividend_steady                  3
deep_value                       2
```

剩下 14 只 manual_review 是结构性问题（12 只数据源缺失的"幽灵基金" + 2 只
ETF 联接结构性无持仓），属于饱和状态。

## 九、常见问题排查

### 1. `make run-batch` 拿到的 NAV 样本数仍然小于 180

先确认 fundData cache DB 是不是用 `make refresh-nav` 更新过的。常见原因：

- `fundData batch-sync` 用底层 `per=20`，单次只拿 20 行，需要 `make refresh-nav`
  显式做分页（[scripts/fetch_nav_history.py](../scripts/fetch_nav_history.py)）。
- 拷贝时 WAL 没合并：`refresh-nav` 脚本最后一行已经 `PRAGMA wal_checkpoint(TRUNCATE)`，
  如果手工同步过别的工具，建议手动跑一次再 `make copy-source`。

### 2. 风格规则一只都没触发

- 检查 `data/stock_factors.sqlite` 是否存在且非空
- 检查 `make run-batch` 或手工命令里 `--factor-db` 路径是否指向
  `data/stock_factors.sqlite`，不要误指到 source DB
- 如果 CLI 报 `equity factor validation failed`，先按错误信息检查
  `fund_factor_exposures` 和 `style_factor_ready_pool`
- 看具体一只基金的因子覆盖：
  ```python
  from app.data_access.funddata_repository import FundDataRepository
  repo = FundDataRepository(
      "/tmp/fle-run/source.sqlite",
      factor_db_path="data/stock_factors.sqlite",
  )
  fund = repo.load_fund_input("000251")
  print(f"holdings={len(fund.stock_holdings)} factors={len(fund.stock_factors)}")
  ```

### 3. 报 `IP 被封 / Empty reply from server`

东财对单 IP 高频访问会临时拒绝。表现是 curl exit 52。等几分钟，或把
`scripts/fetch_stock_factors.py` 的 `_curl_get` 重试间隔加大。

## 十、扩展方向

| 想做的事 | 改哪里 |
|---|---|
| 把范围从 168 扩到更大 | 替换 `data/phase1_fund_codes.txt`，或者去掉 `FLE_PHASE1_CODES_FILE` |
| 触发 3Y / 5Y 标签 | `make refresh-nav NAV_START=2022-06-01` 拉更长历史 |
| 新增股票因子 | 在 `scripts/fetch_stock_factors.py` 加一个 `fetch_xxx` 步骤 |
| 让风格标签更严 / 更松 | 调 `--deep-value-weight-min` / `--quality-growth-weight-min` |
| 把因子换日期 | 调 `TRADE_DATE` 和 `REPORT_DATE` 后重跑 `make refresh-factors` |
