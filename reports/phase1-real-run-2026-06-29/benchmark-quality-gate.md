# Benchmark Quality Gate Report

## Status Counts

| status | funds |
|---|---:|
| `benchmark_missing` | 1 |
| `missing_source` | 22 |
| `ready` | 113 |
| `unresolved` | 6 |

## Blocked Funds

| fund_code | fund_name | status | blocking_components | benchmark |
|---|---|---|---|---|
| `000001` | 华夏成长混合 | `benchmark_missing` |  | 该基金暂未披露业绩比较基准 |
| `000011` | 华夏大盘精选混合A | `unresolved` | 新华富时中国A200指数;LOCAL_XHFT_CHINA_GOV_BOND:新华富时中国国债 | 新华富时中国A200指数*80%+新华富时中国国债指数*20% |
| `000021` | 华夏优势增长混合 | `unresolved` | 富时中国A600指数 | 富时中国A600指数收益率×80%+中债综合指数(财富)收益率×20% |
| `000030` | 长城核心优选混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*55%+中债总财富指数收益率*45% |
| `000042` | 财通中证ESG100指数增强A | `unresolved` | 中证财通中国可持续发展100(ECPIESG)指数 | 中证财通中国可持续发展100(ECPI ESG)指数收益率*95%+银行活期存款利率(税后)*5% |
| `000056` | 建信消费升级混合 | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 75%×沪深300指数收益率+25%×中国债券总指数收益率 |
| `000073` | 摩根成长动力混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*80%+中债总指数收益率*20% |
| `000082` | 嘉实研究阿尔法股票A | `unresolved` | MSCI中国A股指数 | MSCI中国A股指数收益率*95%+银行活期存款利率(税后)*5% |
| `000124` | 华宝服务优选混合 | `unresolved` | 中证服务业指数 | 中证服务业指数收益率×80%+上证国债指数收益率×20% |
| `000165` | 国投瑞银策略精选混合 | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 55%×沪深300指数+45%×中债总指数 |
| `000172` | 华泰柏瑞量化增强混合A | `unresolved` | (指年,评价时按期间折算) | 沪深300指数收益率*95%+2.5%(指年收益率,评价时按期间折算) |
| `000294` | 华安生态优先混合A | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 中证800指数收益率*80%+中国债券总指数收益率*20% |
| `000308` | 建信创新中国混合 | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 75%×沪深300指数收益率+25%中国债券总指数收益率 |
| `000309` | 大摩品质生活精选股票A | `missing_source` | LOCAL_SP_CHINA_BOND:标普中国债券 | 沪深300指数收益率*85%+标普中国债券指数收益率*15% |
| `000328` | 摩根转型动力混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*80%+中债总指数收益率*20% |
| `000368` | 汇添富沪深300安中指数A | `missing_source` | H30124:沪深300安中动态策略 | 沪深300安中动态策略指数收益率*95%+金融机构人民币活期存款基准利率(税后)*5% |
| `000404` | 易方达新兴成长灵活配置 | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 中证新兴产业指数收益率×50%+中债总财富指数收益率×50% |
| `000457` | 摩根核心成长股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*85%+中债总指数收益率*15% |
| `000480` | 东方红新动力混合A | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 沪深300指数收益率*70%+中国债券总指数收益率*30% |
| `000524` | 摩根民生需求股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*85%+中债总指数收益率*15% |
| `000549` | 华安大国新经济股票A | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 中证800指数收益率*90%+中国债券总指数收益率*10% |
| `000566` | 华泰柏瑞创新升级混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 中证TMT产业主题指数收益率×20%+中证新兴产业指数收益率×40%+中债总指数(全价)收益率×40% |
| `000577` | 安信价值精选股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*80%+中债总指数收益率*20% |
| `000584` | 新华鑫益灵活配置混合C | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*60%+中债总指数收益率*40% |
| `000592` | 建信改革红利股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*85%+中债总财富(总值)指数收益率*15% |
| `000594` | 大摩进取优选股票 | `missing_source` | LOCAL_SP_CHINA_BOND:标普中国债券 | 沪深300指数收益率*85%+标普中国债券指数收益率*15% |
| `000603` | 易方达创新驱动灵活配置混合 | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 中证800指数收益率*85%+中债-总财富(总值)指数收益率*15% |
| `000619` | 东方红产业升级混合 | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 沪深300指数收益率*70%+中国债券总指数收益率*30% |
| `000649` | 长城久鑫混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*55%+中债总财富指数收益率*45% |
