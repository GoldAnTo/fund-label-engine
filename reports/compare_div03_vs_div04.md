# 规则回放对比报告

- before: `/tmp/fle-run/output-equity-contribution-full.sqlite` run_id=`dcce7dcd84ef4345add2a342d8be266d`
- after:  `/tmp/fle-run/output-div04.sqlite` run_id=`29296eb888a54db6a75d475495aa4584`
- 基金数: before=718 after=371 共同=371
- 标签行数: before=718 after=371
- 状态翻转: 0 | 新增: 0 | 消失: 347

## 1. 标签级计数对比

| label_code | before(active) | before(observe) | after(active) | after(observe) | Δ(active) |
|---|---:|---:|---:|---:|---:|
| `dividend_steady` | 63 | 655 | 21 | 350 | -42 |

## 2. 基金级状态翻转（0 条）

无状态翻转。


## 4. after 消失标签（347 条）

| fund_code | label_code | before_status |
|---|---|---|
| 000127 | dividend_steady | active |
| 000251 | dividend_steady | active |
| 000326 | dividend_steady | active |
| 000835 | dividend_steady | active |
| 000884 | dividend_steady | active |
| 000926 | dividend_steady | active |
| 000928 | dividend_steady | active |
| 000965 | dividend_steady | active |
| 001027 | dividend_steady | active |
| 001044 | dividend_steady | active |
| 001054 | dividend_steady | active |
| 001097 | dividend_steady | active |
| 001110 | dividend_steady | active |
| 001111 | dividend_steady | active |
| 001149 | dividend_steady | active |
| 001250 | dividend_steady | active |
| 001291 | dividend_steady | active |
| 001320 | dividend_steady | active |
| 001336 | dividend_steady | active |
| 001337 | dividend_steady | active |
| 001352 | dividend_steady | active |
| 001392 | dividend_steady | active |
| 001393 | dividend_steady | active |
| 001403 | dividend_steady | active |
| 001484 | dividend_steady | active |
| 001490 | dividend_steady | active |
| 001577 | dividend_steady | active |
| 001604 | dividend_steady | active |
| 001638 | dividend_steady | active |
| 001660 | dividend_steady | active |
| 001708 | dividend_steady | active |
| 001726 | dividend_steady | active |
| 001816 | dividend_steady | active |
| 001849 | dividend_steady | active |
| 001857 | dividend_steady | active |
| 001884 | dividend_steady | active |
| 002011 | dividend_steady | active |
| 002164 | dividend_steady | active |
| 002334 | dividend_steady | active |
| 002335 | dividend_steady | active |
| 002443 | dividend_steady | active |
| 002512 | dividend_steady | active |
| 003147 | dividend_steady | observe |
| 003548 | dividend_steady | observe |
| 003684 | dividend_steady | observe |
| 003685 | dividend_steady | observe |
| 003957 | dividend_steady | observe |
| 003958 | dividend_steady | observe |
| 004477 | dividend_steady | observe |
| 004856 | dividend_steady | observe |
| ... | (297 more) | |
