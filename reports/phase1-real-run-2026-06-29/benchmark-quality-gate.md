# Benchmark Quality Gate Report

## Status Counts

| status | funds |
|---|---:|
| `benchmark_missing` | 1 |
| `missing_source` | 6 |
| `ready` | 135 |

## Blocked Funds

| fund_code | fund_name | status | blocking_components | benchmark |
|---|---|---|---|---|
| `000001` | 华夏成长混合 | `benchmark_missing` |  | 该基金暂未披露业绩比较基准 |
| `000011` | 华夏大盘精选混合A | `missing_source` | LOCAL_XHFT_CHINA_A200:新华富时中国A200;LOCAL_XHFT_CHINA_GOV_BOND:新华富时中国国债 | 新华富时中国A200指数*80%+新华富时中国国债指数*20% |
| `000021` | 华夏优势增长混合 | `missing_source` | LOCAL_FTSE_CHINA_A600:富时中国A600 | 富时中国A600指数收益率×80%+中债综合指数(财富)收益率×20% |
| `000042` | 财通中证ESG100指数增强A | `missing_source` | LOCAL_CSI_ECPI_ESG100:中证财通ESG100 | 中证财通中国可持续发展100(ECPI ESG)指数收益率*95%+银行活期存款利率(税后)*5% |
| `000082` | 嘉实研究阿尔法股票A | `missing_source` | LOCAL_MSCI_CHINA_A:MSCI中国A股 | MSCI中国A股指数收益率*95%+银行活期存款利率(税后)*5% |
| `000124` | 华宝服务优选混合 | `missing_source` | H30074:中证服务业 | 中证服务业指数收益率×80%+上证国债指数收益率×20% |
| `000368` | 汇添富沪深300安中指数A | `missing_source` | H30124:沪深300安中动态策略 | 沪深300安中动态策略指数收益率*95%+金融机构人民币活期存款基准利率(税后)*5% |
