# Benchmark Quality Gate Report

## Status Counts

| status | funds |
|---|---:|
| `benchmark_missing` | 1 |
| `mapping_required` | 2 |
| `missing_source` | 80 |
| `ready` | 45 |
| `unresolved` | 14 |

## Blocked Funds

| fund_code | fund_name | status | blocking_components | benchmark |
|---|---|---|---|---|
| `000001` | 华夏成长混合 | `benchmark_missing` |  | 该基金暂未披露业绩比较基准 |
| `000011` | 华夏大盘精选混合A | `unresolved` | 新华富时中国A200指数;LOCAL_XHFT_CHINA_GOV_BOND:新华富时中国国债 | 新华富时中国A200指数*80%+新华富时中国国债指数*20% |
| `000020` | 景顺长城品质投资混合A | `missing_source` | H11001:中证全债 | 沪深300指数*80%+中证全债指数*20% |
| `000021` | 华夏优势增长混合 | `unresolved` | 富时中国A600指数;LOCAL_CBOND_COMPOSITE:中债综合 | 富时中国A600指数收益率×80%+中债综合指数(财富)收益率×20% |
| `000029` | 富国宏观策略灵活配置混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*65%+中债综合指数收益率*35% |
| `000030` | 长城核心优选混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*55%+中债总财富指数收益率*45% |
| `000039` | 农银高增长混合 | `missing_source` | H11001:中证全债 | 75%×沪深300指数+25%×中证全债指数 |
| `000042` | 财通中证ESG100指数增强A | `unresolved` | 中证财通中国可持续发展100(ECPIESG)指数 | 中证财通中国可持续发展100(ECPI ESG)指数收益率*95%+银行活期存款利率(税后)*5% |
| `000056` | 建信消费升级混合 | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 75%×沪深300指数收益率+25%×中国债券总指数收益率 |
| `000063` | 长盛电子信息主题混合A | `missing_source` | H11008:中证综合债 | 中证TMT产业主题指数收益率*50%+中证综合债指数收益率*50% |
| `000066` | 诺安鸿鑫混合A | `missing_source` | H11001:中证全债 | 沪深300指数收益率*80%+中证全债指数收益率*20% |
| `000073` | 摩根成长动力混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*80%+中债总指数收益率*20% |
| `000082` | 嘉实研究阿尔法股票A | `unresolved` | MSCI中国A股指数 | MSCI中国A股指数收益率*95%+银行活期存款利率(税后)*5% |
| `000117` | 广发轮动配置混合 | `missing_source` | H11001:中证全债 | 80%×沪深300指数+20%×中证全债指数 |
| `000120` | 中银美丽中国混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*80%+中债综合指数收益率*20% |
| `000124` | 华宝服务优选混合 | `unresolved` | 中证服务业指数 | 中证服务业指数收益率×80%+上证国债指数收益率×20% |
| `000126` | 招商安润灵活配置混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*55%+中债综合全价(总值)指数收益率*45% |
| `000127` | 农银行业领先混合 | `missing_source` | H11001:中证全债 | 75%×沪深300指数+25%×中证全债指数 |
| `000136` | 民生加银策略精选混合A | `missing_source` | LOCAL_CBOND_GOV_TOTAL:中债国债总 | 沪深300指数收益率*60%+中债国债总指数收益率(全价)*40% |
| `000165` | 国投瑞银策略精选混合 | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 55%×沪深300指数+45%×中债总指数 |
| `000166` | 中海信息产业混合A | `missing_source` | H11001:中证全债 | 中证TMT产业主题指数收益率*80%+中证全债指数收益率*20% |
| `000167` | 广发聚优灵活配置混合A | `missing_source` | H11001:中证全债 | 50%×沪深300指数+50%×中证全债指数 |
| `000172` | 华泰柏瑞量化增强混合A | `unresolved` | (指年,评价时按期间折算) | 沪深300指数收益率*95%+2.5%(指年收益率,评价时按期间折算) |
| `000173` | 汇添富美丽30混合A | `missing_source` | H11001:中证全债 | 沪深300指数收益率*80%+中证全债指数收益率*20% |
| `000195` | 工银成长收益混合A | `missing_source` | H11001:中证全债 | 60%×沪深300指数+40%×中证全债指数 |
| `000196` | 工银成长收益混合B | `missing_source` | H11001:中证全债 | 60%×沪深300指数+40%×中证全债指数 |
| `000199` | 国泰量化策略收益混合A | `missing_source` | H11008:中证综合债 | 沪深300指数收益率*75%+中证综合债指数收益率*25% |
| `000209` | 中信保诚新兴产业混合A | `missing_source` | H11008:中证综合债 | 中证新兴产业指数收益率*80%+中证综合债指数收益率*20% |
| `000214` | 广发成长优选混合 | `missing_source` | H11001:中证全债 | 50%×沪深300指数+50%×中证全债指数 |
| `000220` | 富国医疗保健行业混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 中证医药卫生指数收益率×80%+中债综合指数收益率×20% |
| `000242` | 景顺长城策略精选灵活配置混合A | `missing_source` | H11001:中证全债 | 沪深300指数*50%+中证全债指数*50% |
| `000251` | 工银金融地产混合A | `mapping_required` | 沪深300金融地产行业指数 | 80%×沪深300金融地产行业指数收益率+20%×上证国债指数收益率 |
| `000264` | 博时内需增长混合A | `missing_source` | H11001:中证全债 | 沪深300指数收益率*60%+中证全债指数收益率*40% |
| `000273` | 华润元大安鑫灵活配置混合A | `unresolved` | LOCAL_CBOND_COMPOSITE:中债综合;恒生指数 | 沪深300指数收益率×60%+中债综合指数收益率×25%+恒生指数收益率×15% |
| `000294` | 华安生态优先混合A | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 中证800指数收益率*80%+中国债券总指数收益率*20% |
| `000308` | 建信创新中国混合 | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 75%×沪深300指数收益率+25%中国债券总指数收益率 |
| `000309` | 大摩品质生活精选股票A | `missing_source` | LOCAL_SP_CHINA_BOND:标普中国债券 | 沪深300指数收益率*85%+标普中国债券指数收益率*15% |
| `000314` | 招商瑞丰灵活配置混合发起式A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 60%×沪深300指数收益率+40%×中债综合指数收益率 |
| `000328` | 摩根转型动力混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*80%+中债总指数收益率*20% |
| `000336` | 农银研究精选混合 | `missing_source` | H11001:中证全债 | 65%×沪深300指数+35%×中证全债指数 |
| `000339` | 长城医疗保健混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 中证医药卫生指数收益率*90%+中债综合财富指数收益率*10% |
| `000354` | 长盛城镇化主题混合A | `missing_source` | H11008:中证综合债 | 沪深300指数收益率*80%+中证综合债指数收益率*20% |
| `000368` | 汇添富沪深300安中指数A | `mapping_required` | 沪深300安中动态策略指数 | 沪深300安中动态策略指数收益率*95%+金融机构人民币活期存款基准利率(税后)*5% |
| `000404` | 易方达新兴成长灵活配置 | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 中证新兴产业指数收益率×50%+中债总财富指数收益率×50% |
| `000408` | 民生加银城镇化混合A | `missing_source` | H11006:中证国债 | 沪深300指数收益率×60%+中证国债指数收益率×40% |
| `000409` | 鹏华环保产业股票 | `missing_source` | H11008:中证综合债 | 中证环保产业指数收益率×80%+中证综合债指数收益率×20% |
| `000411` | 景顺长城优质成长股票A | `missing_source` | H11001:中证全债 | 沪深300指数*90%+中证全债指数*10% |
| `000418` | 景顺长城成长之星股票A | `missing_source` | H11001:中证全债 | 沪深300指数*90%+中证全债指数*10% |
| `000423` | 前海开源事件驱动混合A | `missing_source` | H11001:中证全债 | 沪深300指数收益率×70%+中证全债指数收益率×30% |
| `000431` | 鹏华品牌传承混合 | `missing_source` | H11008:中证综合债 | 沪深300指数收益率×80%+中证综合债指数收益率×20% |
| `000432` | 中银优秀企业混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*80%+中债综合指数收益率*20% |
| `000457` | 摩根核心成长股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*85%+中债总指数收益率*15% |
| `000462` | 农银主题轮动混合A | `missing_source` | H11001:中证全债 | 沪深300指数*65%+中证全债指数*35% |
| `000471` | 富国城镇发展股票 | `unresolved` | 恒生指数;LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*80%+恒生指数收益率(使用估值汇率折算)*10%+中债综合指数收益率*10% |
| `000477` | 广发主题领先混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数*40%+中债-综合财富(总值)指数*50%+银行活期存款利率(税后)*10% |
| `000480` | 东方红新动力混合A | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 沪深300指数收益率*70%+中国债券总指数收益率*30% |
| `000496` | 长安产业精选混合A | `missing_source` | H11001:中证全债 | 沪深300指数收益率×65%+中证全债指数收益率×35% |
| `000511` | 国泰国策驱动灵活配置混合A | `missing_source` | H11008:中证综合债 | 沪深300指数收益率×50%+中证综合债券指数收益率×50% |
| `000513` | 富国高端制造行业股票A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 中证800指数收益率*80%+中债综合指数收益率*20% |
| `000522` | 华润元大信息传媒科技混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 中证TMT产业主题指数收益率×80%+中债综合指数收益率×20% |
| `000523` | 国投瑞银医疗保健混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 中证医药卫生指数收益率*80%+中债综合全价(总值)指数收益率*20% |
| `000524` | 摩根民生需求股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*85%+中债总指数收益率*15% |
| `000529` | 广发竞争优势混合A | `missing_source` | H11001:中证全债 | 沪深300指数*50%+中证全债指数*50% |
| `000531` | 东吴阿尔法灵活配置混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数*65%+中国债券综合全价指数*35% |
| `000532` | 景顺长城优势企业混合A | `missing_source` | H11001:中证全债 | 沪深300指数*80%+中证全债指数*20% |
| `000534` | 长盛高端装备混合A | `unresolved` | 上证高端装备60指数;H11008:中证综合债 | 上证高端装备60指数收益率*50%+中证综合债指数收益率*50% |
| `000535` | 长盛航天海工混合A | `unresolved` | 国证航天军工指数;H11008:中证综合债 | 国证航天军工指数收益率*50%+中证综合债指数收益率*50% |
| `000538` | 诺安优势行业混合A | `missing_source` | H11001:中证全债 | 60%沪深300指数+40%中证全债指数 |
| `000547` | 建信健康民生混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*70%+中债综合全价(总值)指数收益率*30% |
| `000549` | 华安大国新经济股票A | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 中证800指数收益率*90%+中国债券总指数收益率*10% |
| `000550` | 广发新动力混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数*80%+中债-综合财富(总值)指数*10%+银行活期存款利率(税后)*10% |
| `000551` | 中信保诚幸福消费混合A | `missing_source` | H11008:中证综合债 | 中证内地消费主题指数收益率*60%+中证港股通大消费主题指数收益率*20%+中证综合债指数收益率*20% |
| `000566` | 华泰柏瑞创新升级混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 中证TMT产业主题指数收益率×20%+中证新兴产业指数收益率×40%+中债总指数(全价)收益率×40% |
| `000567` | 广发聚祥灵活混合 | `missing_source` | H11001:中证全债 | 55%×沪深300指数+45%×中证全债指数 |
| `000574` | 宝盈新价值混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率×65%+中债综合指数收益率×35% |
| `000577` | 安信价值精选股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*80%+中债总指数收益率*20% |
| `000584` | 新华鑫益灵活配置混合C | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*60%+中债总指数收益率*40% |
| `000586` | 景顺长城中小创精选股票A | `missing_source` | H11001:中证全债 | 创业板综合指数*45%+中小企业综合指数*45%+中证全债指数*10% |
| `000587` | 大成灵活配置混合A | `unresolved` | 中证A500指数;LOCAL_CBOND_GOV_1_3Y:中债国债总1-3年 | 中证A500指数收益率*80%+中债-国债总全价(1-3年)指数收益率*20% |
| `000589` | 光大银发商机混合A | `missing_source` | H11001:中证全债 | 沪深300指数收益率*75%+中证全债指数收益率*25% |
| `000591` | 中银健康生活混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*80%+中债综合指数收益率*20% |
| `000592` | 建信改革红利股票A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*85%+中债总财富(总值)指数收益率*15% |
| `000594` | 大摩进取优选股票 | `missing_source` | LOCAL_SP_CHINA_BOND:标普中国债券 | 沪深300指数收益率*85%+标普中国债券指数收益率*15% |
| `000596` | 前海开源中证军工指数A | `unresolved` | 中证军工指数 | 中证军工指数收益率×95%+银行活期存款利率(税后)×5% |
| `000598` | 长盛生态环境混合A | `missing_source` | H11008:中证综合债 | 中证环保产业指数收益率*50%+中证综合债指数收益率*50% |
| `000603` | 易方达创新驱动灵活配置混合 | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 中证800指数收益率*85%+中债-总财富(总值)指数收益率*15% |
| `000619` | 东方红产业升级混合 | `missing_source` | LOCAL_CHINA_BOND_TOTAL:中国债券总 | 沪深300指数收益率*70%+中国债券总指数收益率*30% |
| `000628` | 大成高鑫股票A | `unresolved` | 恒生指数;H11008:中证综合债 | 中证800指数收益率*80%+恒生指数收益率*10%+中证综合债指数收益率*10% |
| `000634` | 富国天盛灵活配置基金 | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率×65%+中债综合指数收益率×35% |
| `000646` | 华润元大量化优选混合A | `unresolved` | 恒生指数;H11006:中证国债 | 沪深300指数收益率*50%+恒生指数收益率*20%+中证国债指数收益率*30% |
| `000649` | 长城久鑫混合A | `missing_source` | LOCAL_CBOND_TOTAL:中债总 | 沪深300指数收益率*55%+中债总财富指数收益率*45% |
| `000652` | 博时裕隆灵活配置混合A | `missing_source` | H11001:中证全债 | 沪深300指数收益率*75%+中证全债指数收益率*25% |
| `000663` | 国投瑞银美丽中国混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率*60%+中债综合指数收益率*40% |
| `000684` | 长盛养老健康混合A | `missing_source` | H11008:中证综合债 | 沪深300指数收益率*50%+中证综合债指数收益率*50% |
| `100039` | 富国通胀通缩主题轮动混合A | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率×80%+中债综合指数收益率×20% |
| `100056` | 富国低碳环保混合 | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 沪深300指数收益率×80%+中债综合指数收益率×20% |
| `100060` | 富国高新技术产业混合 | `missing_source` | LOCAL_CBOND_COMPOSITE:中债综合 | 中证800指数收益率×80%+中债综合指数收益率×20% |

## Relative Label Counts After Quality Gate

跑批输出：`/tmp/fle-run/benchmark-quality-output.sqlite`，run_id=`a82ca0f4896e4e308c94a6940e14cdac`，processed=142。

相对基准标签只在拥有合成 `benchmark_returns` 的基金上产生。修复审计 ready 判定后，
`ready` 由 11 校正为 45，与实际能算出合成收益、能产出相对标签的基金集合完全一致
（差集双向为空）。

| label_code | distinct funds |
|---|---:|
| `alpha_positive` | 38 |
| `benchmark_data_missing` | 98 |
| `beta_low` | 44 |
| `excess_return_strong` | 30 |
| `information_ratio_high` | 26 |
| `tracking_error_high` | 44 |

两个原误配基金仍被挡住（`benchmark_data_missing|observe`，无任何相对业绩标签）：

| fund_code | fund_name | 旧行为 | 新行为 |
|---|---|---|---|
| `000251` | 工银金融地产混合A | 沪深300金融地产→普通沪深300，产出 alpha/beta | `benchmark_data_missing`（`exact_component_mapping_required`）|
| `000368` | 汇添富沪深300安中指数A | 沪深300安中策略→普通沪深300，产出 alpha/beta | `benchmark_data_missing`（`exact_component_mapping_required`）|

## Coverage Expansion Decisions

ready 判定修复后，可实时拉取的数字指数码（上证国债 000012、中证800 000906 等）和
synthetic 利率组件（银行活期等）已不再是 blocker。真实覆盖缺口集中在**本地债券指数**
——这些既无在线行情 secid，也尚未导入 `benchmark_component_returns` 日收益。

按"被阻塞基金数"从高到低（修复后）：

| blocker | 被阻塞基金数 | 性质 | 决策 |
|---|---:|---|---|
| `H11001:中证全债` | 26 | 债券指数，无日收益源 | `source_required` |
| `LOCAL_CBOND_COMPOSITE:中债综合` | 24 | 债券指数，无日收益源 | `source_required` |
| `LOCAL_CBOND_TOTAL:中债总` | 13 | 债券指数，无日收益源 | `source_required` |
| `H11008:中证综合债` | 13 | 债券指数，无日收益源 | `source_required` |
| `LOCAL_CHINA_BOND_TOTAL:中国债券总` | 6 | 债券指数，无日收益源 | `source_required` |
| `恒生指数` | 4 | 港股指数，需精确识别 + 日收益源 | `mapping_required` |
| `LOCAL_SP_CHINA_BOND:标普中国债券` | 2 | 债券指数，无日收益源 | `source_required` |
| `H11006:中证国债` | 2 | 债券指数，无日收益源 | `source_required` |
| `MSCI中国A股指数` / `富时中国A200/A600` / `中证服务业` 等 | 各 1 | 文本指数尚未精确识别 | `mapping_required` |

**结论**：覆盖率最大增量来自补债券指数日收益源（中证全债/中债综合/中债总/中证综合债，
合计阻塞 70+ 只）。这些都属 `source_required`，需导入可靠日频源到
`benchmark_component_returns` 后才能转 ready；本计划不盲补、不用宽指数代理。
决策口径：`source_required`=指数身份已知但缺日收益源；`mapping_required`=文本指数尚未精确识别。
