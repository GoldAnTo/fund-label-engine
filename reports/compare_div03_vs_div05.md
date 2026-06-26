# 规则回放对比报告

- before: `/tmp/fle-run/output-equity-contribution-full.sqlite` run_id=`dcce7dcd84ef4345add2a342d8be266d`
- after:  `/tmp/fle-run/output-div05.sqlite` run_id=`1c8a3e3b39b94e75a7b59625a9eb55bf`
- 基金数: before=718 after=40 共同=40
- 标签行数: before=718 after=40
- 状态翻转: 0 | 新增: 0 | 消失: 678

## 1. 标签级计数对比

| label_code | before(active) | before(observe) | after(active) | after(observe) | Δ(active) |
|---|---:|---:|---:|---:|---:|
| `dividend_steady` | 63 | 655 | 0 | 40 | -63 |

## 2. 基金级状态翻转（0 条）

无状态翻转。


## 4. after 消失标签（678 条）

| fund_code | label_code | before_status |
|---|---|---|
| 000127 | dividend_steady | active |
| 000251 | dividend_steady | active |
| 000326 | dividend_steady | active |
| 000835 | dividend_steady | active |
| 000867 | dividend_steady | active |
| 000884 | dividend_steady | active |
| 000916 | dividend_steady | active |
| 000926 | dividend_steady | active |
| 000928 | dividend_steady | active |
| 000965 | dividend_steady | active |
| 001017 | dividend_steady | active |
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
| 001382 | dividend_steady | active |
| 001392 | dividend_steady | active |
| 001393 | dividend_steady | active |
| 001403 | dividend_steady | active |
| 001463 | dividend_steady | active |
| 001484 | dividend_steady | active |
| 001490 | dividend_steady | active |
| 001508 | dividend_steady | active |
| 001510 | dividend_steady | active |
| 001577 | dividend_steady | active |
| 001604 | dividend_steady | active |
| 001638 | dividend_steady | active |
| 001648 | dividend_steady | active |
| 001660 | dividend_steady | active |
| 001679 | dividend_steady | active |
| 001681 | dividend_steady | active |
| 001708 | dividend_steady | active |
| 001726 | dividend_steady | active |
| 001816 | dividend_steady | active |
| 001849 | dividend_steady | active |
| 001857 | dividend_steady | active |
| 001884 | dividend_steady | active |
| 001897 | dividend_steady | active |
| 001910 | dividend_steady | active |
| 001927 | dividend_steady | active |
| 001928 | dividend_steady | active |
| ... | (628 more) | |
