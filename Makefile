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
FUND_DATA_CACHE ?= $(HOME)/.cache/fund-data/releases/2026-06-03T214600Z/fund_data_query.sqlite

# 因子横截面用的"今天"。建议每次跑前手动改成最近交易日。
TRADE_DATE  ?= 2026-06-23
# 最近一份已披露的季报日（YYYY-03-31 / 06-30 / 09-30 / 12-31）。
REPORT_DATE ?= 2025-09-30

# NAV 历史区间。默认拉 1Y，满足 --min-nav-samples 180 的 gate。
NAV_START   ?= 2025-06-01
NAV_END     ?= 2026-06-23

.PHONY: help refresh-factors refresh-nav copy-source run-batch run-batch-v1 test

help:
	@echo "Available targets:"
	@echo "  make refresh-factors    刷新 $(FACTOR_DB)（TRADE_DATE=$(TRADE_DATE), REPORT_DATE=$(REPORT_DATE)）"
	@echo "  make refresh-nav        把 phase1 ($(PHASE1_FILE)) 的 NAV 拉到 $(FUND_DATA_CACHE)，区间 $(NAV_START)~$(NAV_END)"
	@echo "  make copy-source        把 fundData cache DB 拷贝到 $(SOURCE_DB)"
	@echo "  make run-batch          运行 batch（依赖 copy-source；用 $(FACTOR_DB) 作为 factor cache）"
	@echo "  make run-batch-v1       运行 v1 正式权益清单 batch（排除待复核/低权益仓位基金）"
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
	    --rule-config $(RULE_CONFIG) \
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
	    --rule-config $(RULE_CONFIG) \
	    --factor-db $(PWD)/$(FACTOR_DB) \
	    --min-nav-samples 180 \
	    --min-holding-total-weight 0.5 \
	    --deep-value-weight-min 0.4 \
	    --quality-growth-weight-min 0.4

test:
	cd backend && $(PYTHON) -m pytest -q
