# Relative-Benchmark Eligibility Audit

Total funds: 142

三层状态收口：基准源 ready 不等于相对标签 ready。relative_label_ready 才是可正式展示 Alpha/Beta/超额收益的池子。

## relative_label_status Counts

| status | count |
| --- | ---: |
| `relative_label_ready` | 111 |
| `relative_label_ready_approx` | 21 |
| `nav_window_insufficient` | 4 |
| `benchmark_source_missing` | 5 |
| `benchmark_missing` | 1 |

## benchmark_source_status Counts

| status | count |
| --- | ---: |
| `ready` | 136 |
| `missing_source` | 5 |
| `benchmark_missing` | 1 |

## benchmark_ready 但 NAV 不足（可通过补 NAV 解决）

| fund_code | fund_name | nav_sample_count | benchmark_sample_count | blocking_reason |
| --- | --- | ---: | ---: | --- |
| `100038` | 富国沪深300指数增强A | 20 | 241 | nav_sample_count=20<180 |
| `100039` | 富国通胀通缩主题轮动混合A | 20 | 194 | nav_sample_count=20<180 |
| `100056` | 富国低碳环保混合 | 20 | 194 | nav_sample_count=20<180 |
| `100060` | 富国高新技术产业混合 | 20 | 194 | nav_sample_count=20<180 |
