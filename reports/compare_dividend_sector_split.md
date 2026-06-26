# 规则回放对比报告

- before: `/tmp/fle-run/output-equity-contribution-full.sqlite` run_id=`dcce7dcd84ef4345add2a342d8be266d`
- after:  `/tmp/fle-run/output-dividend-sector-split.sqlite` run_id=`3a1339e0e6f54065a8d1b0d5a879ffdd`
- 基金数: before=718 after=718 共同=718
- 标签行数: before=718 after=718
- 状态翻转: 0 | 新增: 357 | 消失: 357

## 1. 标签级计数对比

| label_code | before(active) | before(observe) | after(active) | after(observe) | Δ(active) |
|---|---:|---:|---:|---:|---:|
| `consumer_quality` | 0 | 0 | 4 | 114 | +4 |
| `dividend_steady` | 63 | 655 | 38 | 323 | -25 |
| `high_dividend_financial` | 0 | 0 | 21 | 218 | +21 |

## 2. 基金级状态翻转（0 条）

无状态翻转。


## 3. after 新增标签（357 条）

| fund_code | label_code | status |
|---|---|---|
| 000251 | high_dividend_financial | active |
| 000835 | high_dividend_financial | active |
| 000867 | consumer_quality | active |
| 001054 | high_dividend_financial | active |
| 001336 | high_dividend_financial | active |
| 001337 | high_dividend_financial | active |
| 001382 | consumer_quality | active |
| 001392 | high_dividend_financial | active |
| 001393 | high_dividend_financial | active |
| 001490 | high_dividend_financial | active |
| 001508 | high_dividend_financial | active |
| 001510 | high_dividend_financial | active |
| 001604 | high_dividend_financial | active |
| 001660 | high_dividend_financial | active |
| 001708 | high_dividend_financial | active |
| 001849 | high_dividend_financial | active |
| 001897 | high_dividend_financial | active |
| 001910 | high_dividend_financial | active |
| 002011 | high_dividend_financial | active |
| 002054 | high_dividend_financial | active |
| 002056 | high_dividend_financial | active |
| 002159 | high_dividend_financial | active |
| 002378 | consumer_quality | active |
| 002449 | high_dividend_financial | active |
| 002512 | consumer_quality | active |
| 002621 | consumer_quality | observe |
| 002697 | consumer_quality | observe |
| 002849 | high_dividend_financial | observe |
| 002952 | high_dividend_financial | observe |
| 003684 | consumer_quality | observe |
| 003685 | consumer_quality | observe |
| 003940 | consumer_quality | observe |
| 003957 | high_dividend_financial | observe |
| 003958 | high_dividend_financial | observe |
| 004357 | high_dividend_financial | observe |
| 004410 | high_dividend_financial | observe |
| 004510 | high_dividend_financial | observe |
| 004805 | consumer_quality | observe |
| 004942 | consumer_quality | observe |
| 004943 | consumer_quality | observe |
| 004987 | high_dividend_financial | observe |
| 005235 | consumer_quality | observe |
| 005236 | consumer_quality | observe |
| 005250 | high_dividend_financial | observe |
| 005328 | high_dividend_financial | observe |
| 005335 | consumer_quality | observe |
| 005519 | high_dividend_financial | observe |
| 005535 | consumer_quality | observe |
| 005561 | high_dividend_financial | observe |
| 005562 | high_dividend_financial | observe |
| ... | (307 more) | |

## 4. after 消失标签（357 条）

| fund_code | label_code | before_status |
|---|---|---|
| 000251 | dividend_steady | active |
| 000835 | dividend_steady | active |
| 000867 | dividend_steady | active |
| 001054 | dividend_steady | active |
| 001336 | dividend_steady | active |
| 001337 | dividend_steady | active |
| 001382 | dividend_steady | active |
| 001392 | dividend_steady | active |
| 001393 | dividend_steady | active |
| 001490 | dividend_steady | active |
| 001508 | dividend_steady | active |
| 001510 | dividend_steady | active |
| 001604 | dividend_steady | active |
| 001660 | dividend_steady | active |
| 001708 | dividend_steady | active |
| 001849 | dividend_steady | active |
| 001897 | dividend_steady | active |
| 001910 | dividend_steady | active |
| 002011 | dividend_steady | active |
| 002054 | dividend_steady | active |
| 002056 | dividend_steady | active |
| 002159 | dividend_steady | active |
| 002378 | dividend_steady | active |
| 002449 | dividend_steady | active |
| 002512 | dividend_steady | active |
| 002621 | dividend_steady | observe |
| 002697 | dividend_steady | observe |
| 002849 | dividend_steady | observe |
| 002952 | dividend_steady | observe |
| 003684 | dividend_steady | observe |
| 003685 | dividend_steady | observe |
| 003940 | dividend_steady | observe |
| 003957 | dividend_steady | observe |
| 003958 | dividend_steady | observe |
| 004357 | dividend_steady | observe |
| 004410 | dividend_steady | observe |
| 004510 | dividend_steady | observe |
| 004805 | dividend_steady | observe |
| 004942 | dividend_steady | observe |
| 004943 | dividend_steady | observe |
| 004987 | dividend_steady | observe |
| 005235 | dividend_steady | observe |
| 005236 | dividend_steady | observe |
| 005250 | dividend_steady | observe |
| 005328 | dividend_steady | observe |
| 005335 | dividend_steady | observe |
| 005519 | dividend_steady | observe |
| 005535 | dividend_steady | observe |
| 005561 | dividend_steady | observe |
| 005562 | dividend_steady | observe |
| ... | (307 more) | |
