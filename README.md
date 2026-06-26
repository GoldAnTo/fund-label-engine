# fund-label-engine

基金标签计算引擎，用于给公募基金生成可解释、可追溯、可复核的标签，并服务资管产品池准入、观察池、人工复核和后续 FOF 研究。

## 项目定位

本项目不是自动交易系统，也不是基金推荐机器人。它的核心目标是把基金侧数据、持仓穿透、收益风险特征和规则标签组织成一个可审计的计算流程：

```text
基金数据 -> 数据覆盖率检查 -> 特征计算 -> 标签规则 -> 证据说明 -> 人工复核
```

第一版聚焦：

- 股票型基金
- 偏股混合型基金
- 灵活配置型基金
- 股票指数型基金

第一版明确不做：

- 不做自动交易
- 不做实盘买卖建议
- 不覆盖所有基金类型
- 不用 LLM 自动下最终结论
- 不在缺少股票因子时生成深度价值、质量成长、红利稳健等高级风格标签

## 基准项目

工程形态参考 [nai-he/fund-analysis-agent](https://github.com/nai-he/fund-analysis-agent)：借鉴其 FastAPI + React + 风险评分/分析模块的分层方式。

辅助参考：

- [xalpha](https://github.com/refraction-ray/xalpha)：基金组合、持仓穿透、基金投资管理。
- [FactorHub](https://github.com/cn-vhql/FactorHub)：A 股因子管理和因子生命周期。

本项目不会复制这些仓库的代码，只借鉴产品边界和模块拆分。

## 当前目录

```text
backend/                  后端与标签引擎
config/                   规则配置文件，例如 rules.v1.json
docs/                     需求、边界、数据契约、标签体系
examples/                 示例输入输出
frontend/                 标签工作台
data/                     本地样例数据或缓存，不提交大数据文件
```

## 第一版最小闭环

输入一只基金的结构化数据，输出：

- 数据覆盖率
- 基础画像
- 收益风险特征
- 持仓结构特征
- 基金经理特征
- 费用规模特征
- 标签结果
- 每个标签的证据
- 观察池/人工复核建议

## 当前可运行能力

- `scripts/seed_sample_db.py` 生成本地样例 SQLite。
- `python -m app.batch --db <sqlite>` 执行一次批量标签计算。
- `python -m app.batch --db <fundData.sqlite> --source funddata` 读取真实 fundData schema。
- FastAPI 查询批次、基金标签、证据、覆盖率和人工复核记录。
- FastAPI 查询单基金完整结果包：`/v1/runs/{run_id}/funds/{fund_code}/report`。
- 支持通过 API 写入单个标签的人工复核结论。
- 支持分类/分组落库，并在工作台按业务池、分组类型和分类筛选。
- 支持基金级因子暴露聚合、风格 coverage gate、风格稳定/漂移观察标签。
- 支持相对基准组件解析、`benchmark_components` 审计和本地稳定组件收益源。
- 支持从 `config/rules.v1.json` 加载规则阈值，并把 rule snapshot 落库。

详细目标见 [docs/project-goals.md](docs/project-goals.md)，后续待办见 [docs/todo.md](docs/todo.md)。
真实数据接入见 [docs/funddata-integration.md](docs/funddata-integration.md)。

## 开发命令

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

## 本地试跑

```bash
mkdir -p data
python scripts/seed_sample_db.py data/sample_fund_data.sqlite
python -m app.batch --db data/sample_fund_data.sqlite --rule-config config/rules.v1.json
FLE_DB_PATH=data/sample_fund_data.sqlite uvicorn app.main:app --reload
```

## fundData 试跑

```bash
cp /Users/xiongjiali/Desktop/code/fundData/fund-data/data/fund_data.sqlite /tmp/fund_data_source.sqlite
python -m app.batch \
  --source-db /tmp/fund_data_source.sqlite \
  --output-db /tmp/fund_data_label.sqlite \
  --source funddata \
  --rule-config config/rules.v1.json \
  --factor-db data/stock_factors.sqlite \
  --style-history-periods 2
FLE_DB_PATH=/tmp/fund_data_label.sqlite uvicorn app.main:app --reload
```

真实 fundData 双库跑批会自动校验权益因子链路：`--factor-db` 必须指向非空
股票因子库，并且输出库必须生成 `fund_factor_exposures` 和
`style_factor_ready_pool`。

## Phase1 批量跑批（推荐工作流）

冷启动跑通 168 只 phase1 基金的完整流程：

```bash
make refresh-nav        # 拉 1Y NAV 到 fundData cache
make refresh-factors    # 拉 PE/PB/ROE/股息率到 data/stock_factors.sqlite
make run-batch          # 跑批 + 自动外挂 factor DB（约 30 秒）
```

工作流细节、可调阈值、因子来源对照表见
[docs/runbook-batch-workflow.md](docs/runbook-batch-workflow.md)。
