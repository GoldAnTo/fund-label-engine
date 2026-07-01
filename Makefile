# fund-label-engine 常用任务入口
#
# 用法：
#   make help                列出可用任务
#   make refresh-factors     拉取股票因子横截面到 data/stock_factors.sqlite（偶尔跑）
#   make refresh-nav         分页拉取 phase1 168 只基金的 NAV 历史到 fundData cache DB
#   make run-batch           用 phase1 168 只 + 1Y NAV gate + 风格 0.4 阈值跑一次批

PYTHON      ?= python3
SOURCE_DB   ?= /tmp/fle-run/source.sqlite
OUTPUT_DB   ?= /tmp/fle-run/output.sqlite
FACTOR_DB   ?= data/stock_factors.sqlite
RULE_CONFIG ?= config/rules.v1.json
PHASE1_FILE ?= data/phase1_fund_codes_canonical.txt
PHASE1_OFFICIAL_FILE ?= data/phase1_fund_codes_v1_official.txt
CBOND_AUTHORIZED_CSV ?= data/authorized_benchmark_component_returns.csv
FUND_DATA_CACHE ?= $(HOME)/.cache/fund-data/releases/2026-06-03T214600Z/fund_data_query.sqlite

# 因子横截面用的"今天"。建议每次跑前手动改成最近交易日。
TRADE_DATE  ?= 2026-06-23
# 最近一份已披露的季报日（YYYY-03-31 / 06-30 / 09-30 / 12-31）。
REPORT_DATE ?= 2025-09-30

# NAV 历史区间。默认拉 1Y，满足 --min-nav-samples 180 的 gate。
NAV_START   ?= 2025-06-01
NAV_END     ?= 2026-06-23

BENCHMARK_START ?= 2025-06-25
BENCHMARK_END   ?= 2026-06-24
BENCHMARK_REPORT_DIR ?= reports/phase1-real-run-2026-06-29
BENCHMARK_MAPPING_CSV ?= $(BENCHMARK_REPORT_DIR)/benchmark-mapping.csv
BENCHMARK_QUALITY_CSV ?= $(BENCHMARK_REPORT_DIR)/benchmark-quality.csv
BENCHMARK_QUALITY_MD  ?= $(BENCHMARK_REPORT_DIR)/benchmark-quality-gate.md
RELATIVE_ELIGIBILITY_CSV ?= $(BENCHMARK_REPORT_DIR)/relative-label-eligibility.csv
RELATIVE_ELIGIBILITY_MD  ?= $(BENCHMARK_REPORT_DIR)/relative-label-eligibility.md
READY_POOL_MD  ?= $(BENCHMARK_REPORT_DIR)/phase1-v1-ready-pool-sample.md

.PHONY: help refresh-factors refresh-nav copy-source run-batch run-batch-v1 refresh-benchmark import-authorized-benchmark-components audit-benchmark audit-relative-eligibility render-ready-pool-report run-batch-v1-with-benchmark test

help:
	@echo "Available targets:"
	@echo "  make refresh-factors    刷新 $(FACTOR_DB)（TRADE_DATE=$(TRADE_DATE), REPORT_DATE=$(REPORT_DATE)）"
	@echo "  make refresh-nav        把 phase1 ($(PHASE1_FILE)) 的 NAV 拉到 $(FUND_DATA_CACHE)，区间 $(NAV_START)~$(NAV_END)"
	@echo "  make copy-source        把 fundData cache DB 拷贝到 $(SOURCE_DB)"
	@echo "  make run-batch          运行 batch（依赖 copy-source；用 $(FACTOR_DB) 作为 factor cache）"
	@echo "  make run-batch-v1       运行 v1 正式权益清单 batch（排除待复核/低权益仓位基金）"
	@echo "  make refresh-benchmark  解析/拉取 phase1 v1 基准收益到 $(SOURCE_DB)"
	@echo "  make import-authorized-benchmark-components  导入授权债券指数日收益 CSV 到 $(SOURCE_DB)"
	@echo "  make audit-benchmark    输出 benchmark 质量审计到 $(BENCHMARK_REPORT_DIR)"
	@echo "  make audit-relative-eligibility  输出相对标签 ready 池审计"
	@echo "  make render-ready-pool-report  渲染 8 只样本 Phase1 v1 ready pool 验收报告"
	@echo "  make run-batch-v1-with-benchmark  先补 benchmark，再跑 v1 标签"
	@echo "  RULE_CONFIG=$(RULE_CONFIG)"
	@echo "  make test               跑 pytest"

refresh-factors:
	$(PYTHON) scripts/fetch_stock_factors.py \
	  --trade-date $(TRADE_DATE) \
	  --report-date $(REPORT_DATE) \
	  --db $(FACTOR_DB)

refresh-nav:
	$(PYTHON) scripts/fetch_nav_history.py \
	  --codes-file $(PHASE1_FILE) \
	  --start-date $(NAV_START) \
	  --end-date $(NAV_END) \
	  --db $(FUND_DATA_CACHE)

copy-source:
	@mkdir -p $(dir $(SOURCE_DB))
	sqlite3 $(FUND_DATA_CACHE) "PRAGMA wal_checkpoint(TRUNCATE);"
	cp $(FUND_DATA_CACHE) $(SOURCE_DB)

run-batch: copy-source
	@rm -f $(OUTPUT_DB)
	cd backend && FLE_PHASE1_CODES_FILE=$(PWD)/$(PHASE1_FILE) \
	  $(PYTHON) -m app.batch \
	    --source-db $(SOURCE_DB) \
	    --output-db $(OUTPUT_DB) \
	    --source funddata \
	    --rule-config $(PWD)/$(RULE_CONFIG) \
	    --factor-db $(PWD)/$(FACTOR_DB) \
	    --min-nav-samples 180 \
	    --min-holding-total-weight 0.5 \
	    --deep-value-weight-min 0.4 \
	    --quality-growth-weight-min 0.4

run-batch-v1: copy-source
	@rm -f $(OUTPUT_DB)
	cd backend && FLE_PHASE1_CODES_FILE=$(PWD)/$(PHASE1_OFFICIAL_FILE) \
	  $(PYTHON) -m app.batch \
	    --source-db $(SOURCE_DB) \
	    --output-db $(OUTPUT_DB) \
	    --source funddata \
	    --rule-config $(PWD)/$(RULE_CONFIG) \
	    --factor-db $(PWD)/$(FACTOR_DB) \
	    --min-nav-samples 180 \
	    --min-holding-total-weight 0.5 \
	    --deep-value-weight-min 0.4 \
	    --quality-growth-weight-min 0.4

refresh-benchmark: copy-source
	@mkdir -p $(BENCHMARK_REPORT_DIR)
	$(PYTHON) scripts/fetch_benchmark_returns.py \
	  --db $(SOURCE_DB) \
	  --codes-file $(PHASE1_OFFICIAL_FILE) \
	  --start-date $(BENCHMARK_START) \
	  --end-date $(BENCHMARK_END) \
	  --mapping-csv $(BENCHMARK_MAPPING_CSV)

import-authorized-benchmark-components:
	$(PYTHON) scripts/import_benchmark_component_returns.py \
	  --db $(SOURCE_DB) \
	  --from-csv $(CBOND_AUTHORIZED_CSV) \
	  --min-rows 180

audit-benchmark:
	@mkdir -p $(BENCHMARK_REPORT_DIR)
	$(PYTHON) scripts/audit_benchmark_quality.py \
	  --db $(SOURCE_DB) \
	  --codes-file $(PHASE1_OFFICIAL_FILE) \
	  --csv $(BENCHMARK_QUALITY_CSV) \
	  --markdown $(BENCHMARK_QUALITY_MD)

audit-relative-eligibility:
	@mkdir -p $(BENCHMARK_REPORT_DIR)
	$(PYTHON) scripts/audit_relative_label_eligibility.py \
	  --db $(SOURCE_DB) \
	  --codes-file $(PHASE1_OFFICIAL_FILE) \
	  --csv $(RELATIVE_ELIGIBILITY_CSV) \
	  --markdown $(RELATIVE_ELIGIBILITY_MD)

# Phase1 v1 ready pool 验收报告：从 108 ready 池抽 8 只基金逐只展示
# 依赖：SOURCE_DB 已是含 Investoday/HSI/cbond 数据的 source，OUTPUT_DB 已是最新 batch 输出
render-ready-pool-report:
	@mkdir -p $(BENCHMARK_REPORT_DIR)
	$(PYTHON) scripts/render_ready_pool_report.py \
	  --source-db $(SOURCE_DB) \
	  --output-db $(OUTPUT_DB) \
	  --out-md $(READY_POOL_MD)

run-batch-v1-with-benchmark: refresh-benchmark audit-benchmark
	@rm -f $(OUTPUT_DB)
	FLE_PHASE1_CODES_FILE=$(PWD)/$(PHASE1_OFFICIAL_FILE) PYTHONPATH=backend \
	  $(PYTHON) -m app.batch \
	    --source-db $(SOURCE_DB) \
	    --output-db $(OUTPUT_DB) \
	    --source funddata \
	    --rule-config $(PWD)/$(RULE_CONFIG) \
	    --factor-db $(PWD)/$(FACTOR_DB) \
	    --min-nav-samples 180 \
	    --min-holding-total-weight 0.5 \
	    --deep-value-weight-min 0.4 \
	    --quality-growth-weight-min 0.4

test:
	cd backend && $(PYTHON) -m pytest -q
