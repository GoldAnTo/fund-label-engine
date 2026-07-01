# Relative-Benchmark Eligibility Audit

Total funds: 142

三层状态收口：基准源 ready 不等于相对标签 ready。relative_label_ready 才是可正式展示 Alpha/Beta/超额收益的池子。

## relative_label_status Counts

| status | count |
| --- | ---: |
| `relative_label_ready` | 114 |
| `benchmark_source_missing` | 27 |
| `benchmark_missing` | 1 |

## benchmark_source_status Counts

| status | count |
| --- | ---: |
| `ready` | 114 |
| `missing_source` | 27 |
| `benchmark_missing` | 1 |

## benchmark_ready 但 NAV 不足（可通过补 NAV 解决）

| fund_code | fund_name | nav_sample_count | benchmark_sample_count | blocking_reason |
| --- | --- | ---: | ---: | --- |
