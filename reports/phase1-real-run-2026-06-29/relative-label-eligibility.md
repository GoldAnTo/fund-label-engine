# Relative-Benchmark Eligibility Audit

Total funds: 142

三层状态收口：基准源 ready 不等于相对标签 ready。relative_label_ready 才是可正式展示 Alpha/Beta/超额收益的池子。

## relative_label_status Counts

| status | count |
| --- | ---: |
| `relative_label_ready` | 46 |
| `nav_window_insufficient` | 3 |
| `benchmark_source_missing` | 92 |
| `benchmark_missing` | 1 |

## benchmark_source_status Counts

| status | count |
| --- | ---: |
| `missing_source` | 92 |
| `ready` | 49 |
| `benchmark_missing` | 1 |

## benchmark_ready 但 NAV 不足（可通过补 NAV 解决）

| fund_code | fund_name | nav_sample_count | benchmark_sample_count | blocking_reason |
| --- | --- | ---: | ---: | --- |
| `100038` | 富国沪深300指数增强A | 20 | 241 | nav_sample_count=20<180 |
| `000326` | 南方中小盘成长股票A | 256 | 0 | aligned_sample_count=0<180 (nav=256, benchmark=0) |
| `000327` | 南方潜力新蓝筹混合A | 256 | 0 | aligned_sample_count=0<180 (nav=256, benchmark=0) |
