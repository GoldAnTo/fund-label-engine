# CBOND_TOTAL / CHINA_BOND_TOTAL / SP_CHINA_BOND Source Probe

只读探针结果：评估 Investoday 与 akshare 中债登接口能否为下列三个
benchmark_component 精确日频源。**结论：未找到**——禁止用宽指数或中债综合/中债国债总代理。

## Component 决策

| component | decision | fallback_policy |
| --- | --- | --- |
| `LOCAL_CBOND_TOTAL` | missing_source | no_proxy_no_broad_index |
| `LOCAL_CHINA_BOND_TOTAL` | missing_source | no_proxy_no_broad_index |
| `LOCAL_SP_CHINA_BOND` | missing_source | no_proxy_no_broad_index |

## Investoday search evidence

- API key present: True
- exact matches in candidates: 0
  - (no Investoday candidate matches the three components)

## akshare 中债登接口 evidence

- available: True
- valid categories for `bond_index_general_cbond` 财富/总值:
  - 国债总指数
  - 商业银行债券指数
  - 浮动利率债券指数
  - 资产支持证券指数
- 没有任何 category 是 '中债总指数' / '债券总指数' / '中债-总指数'。
