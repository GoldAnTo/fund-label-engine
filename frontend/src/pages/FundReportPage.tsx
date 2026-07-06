import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  downloadFile,
  fetchBenchmarkComponents,
  fetchFundPercentile,
  fetchFundReport,
  fetchRelativeEligibility,
  postReview,
  type EquityStyleContribution,
  type Evidence,
  type FundLabel,
  type PercentileRank,
} from "../api";
import {
  LabelStatusBadge,
  ReviewActionBadge,
  reviewActionLabel,
  useAsync,
} from "../components";
import { labelTier, shouldDisplayTier, type LabelTier } from "../labelTiers";
import {
  styleName as styleCodeToName,
  styleTagClass,
} from "../styleConfig";

function cleanBlocker(value: string) {
  return value
    .replaceAll("benchmark_source_status=benchmark_missing", "未配置业绩基准")
    .replaceAll("benchmark_source_status=missing_source", "缺少基准收益源")
    .replaceAll("benchmark_source_status=mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_source_status=unresolved", "基准组件未解析")
    .replaceAll("relative_label_ready", "可展示")
    .replaceAll("benchmark_source_missing", "缺少基准收益源")
    .replaceAll("benchmark_mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_unresolved", "基准组件未解析")
    .replaceAll("benchmark_missing", "未配置业绩基准")
    .replaceAll("nav_window_insufficient", "收益窗口不足")
    .replace(/\b[A-Z0-9_]+:/g, "");
}

function evidenceForLabel(data: { evidence: Evidence[] }, labelCode: string) {
  return data.evidence.filter((e) => e.label_code === labelCode);
}

function parseJson(str: string): Record<string, unknown> | null {
  try { return JSON.parse(str); } catch { return null; }
}

// 百分位条组件
function PercentileBar({ percentile }: { percentile: number }) {
  const pct = Math.max(0, Math.min(1, percentile));
  const fillPct = (pct * 100).toFixed(0);
  // 颜色梯度：低 0.3 用蓝灰，0.3-0.7 用蓝，0.7+ 用绿
  const color = pct >= 0.7 ? "var(--pos)" : pct >= 0.3 ? "var(--accent)" : "var(--text-3)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 110 }}>
      <div style={{
        flex: 1, height: 6, borderRadius: 3, background: "var(--surface-2)",
        overflow: "hidden", border: "1px solid var(--border)",
      }}>
        <div style={{ width: `${fillPct}%`, height: "100%", background: color }} />
      </div>
      <span style={{ fontSize: 11, color: "var(--text-2)", minWidth: 30, textAlign: "right" }}>
        {fillPct}%
      </span>
    </div>
  );
}

// 百分位排名面板
function PercentilePanel({ ranks, fundStyleTags }: { ranks: PercentileRank[]; fundStyleTags: string[] }) {
  const [selectedGroup, setSelectedGroup] = useState<string>("all_market");

  if (ranks.length === 0) {
    return <p className="muted">暂无分位数据</p>;
  }

  // 收集所有有数据的分组
  const availableGroups = Array.from(new Set(ranks.map((r) => r.label_code)));
  // 优先级排序：all_market 在前，然后是基础数据类，然后风格标签
  const labelOrder = (code: string) => {
    if (code === "all_market") return 0;
    if (["data_sufficient", "equity_position_high"].includes(code)) return 1;
    return 2;
  };
  const sortedGroups = availableGroups.sort((a, b) => {
    const oa = labelOrder(a);
    const ob = labelOrder(b);
    if (oa !== ob) return oa - ob;
    return a.localeCompare(b);
  });

  const metricName = METRIC_NAMES;

  const filteredRanks = selectedGroup === "all_market"
    ? ranks.filter((r) => r.label_code === "all_market")
    : ranks.filter((r) => r.label_code === selectedGroup);

  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 10 }}>
        {sortedGroups.map((g) => (
          <button
            key={g}
            className={`style-filter-btn ${selectedGroup === g ? "active" : ""}`}
            onClick={() => setSelectedGroup(g)}
            style={{ fontSize: 11 }}
          >
            {g === "all_market" ? "全市场" : styleCodeToName(g)}
            {g !== "all_market" && fundStyleTags.includes(g) && " ★"}
          </button>
        ))}
      </div>
      <p className="muted" style={{ marginBottom: 8, fontSize: 12 }}>
        ★ = 该基金命中的风格标签。百分位 1.0 = 同类第一，0.0 = 同类最末。
      </p>
      <table>
        <thead>
          <tr><th>指标</th><th>指标值</th><th>同类排名</th><th>分位</th></tr>
        </thead>
        <tbody>
          {filteredRanks.map((r) => {
            const displayName = metricName[r.metric_code] ?? r.metric_code;
            const arrow = r.direction === "higher_better" ? "↑ 越大越好" : "↓ 越小越好";
            return (
              <tr key={r.metric_code}>
                <td>
                  <strong>{displayName}</strong>
                </td>
                <td className="num">
                  {r.metric_value !== null ? Number(r.metric_value).toFixed(4) : "-"}
                  <div className="muted" style={{ fontSize: 11 }}>{arrow}</div>
                </td>
                <td className="num">
                  {r.rank_value} / {r.peer_count}
                </td>
                <td>
                  <PercentileBar percentile={r.percentile} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// 下钻面板：展示某风格标签的贡献股票明细
function DrillDownPanel({ contributions, styleCode }: { contributions: EquityStyleContribution[]; styleCode: string }) {
  const rows = contributions
    .filter((c) => c.style_code === styleCode)
    .sort((a, b) => b.contribution_weight - a.contribution_weight);

  if (rows.length === 0) {
    return <p className="muted">暂无贡献明细数据。</p>;
  }

  const totalWeight = rows.reduce((sum, r) => sum + r.contribution_weight, 0);
  const matchedCount = rows.filter((r) => r.matched === 1).length;

  return (
    <div className="drill-panel">
      <div className="muted" style={{ marginBottom: 8 }}>
        共 {rows.length} 只持仓股票，{matchedCount} 只命中，贡献权重合计 {(totalWeight * 100).toFixed(1)}%
      </div>
      <table className="drill-table">
        <thead>
          <tr>
            <th>股票</th><th className="num">持仓权重</th><th className="num">贡献权重</th>
            <th>命中</th><th>因子值</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const fv = parseJson(r.factor_values_json);
            const factorStr = fv
              ? Object.entries(fv)
                  .filter(([, v]) => v !== null && v !== undefined)
                  .map(([k, v]) => `${k}=${typeof v === "number" ? v.toFixed(2) : v}`)
                  .join("  ")
              : "-";
            return (
              <tr key={`${r.stock_code}-${r.style_code}`}>
                <td>
                  <strong>{r.stock_code}</strong>
                  {r.stock_name && <div className="muted">{r.stock_name}</div>}
                </td>
                <td className="num">{(r.weight * 100).toFixed(1)}%</td>
                <td className="num">{(r.contribution_weight * 100).toFixed(1)}%</td>
                <td>{r.matched === 1 ? <span className="drill-hit">命中</span> : <span className="drill-miss">未命中</span>}</td>
                <td className="muted" style={{ fontSize: 11 }}>{factorStr}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// 指标/因子中文名映射（模块级，所有组件共享）
const METRIC_NAMES: Record<string, string> = {
  annualized_return_1y: "年化收益",
  annualized_return_3y: "近三年年化收益",
  annualized_return_1m: "近一月收益",
  annualized_return_3m: "近三月收益",
  sharpe_ratio_1y: "夏普比率",
  sharpe_ratio_3y: "近三年夏普",
  max_drawdown_1y: "最大回撤",
  max_drawdown_3y: "近三年最大回撤",
  annualized_excess_return_1y: "超额收益",
  annualized_excess_return_3y: "近三年超额收益",
  information_ratio_1y: "信息比率",
  information_ratio_3y: "近三年信息比率",
  tracking_error_1y: "跟踪误差",
  beta_1y: "Beta",
  alpha_1y: "Alpha",
  roe_weighted: "加权 ROE",
  pe_weighted: "加权 PE",
  pb_weighted: "加权 PB",
  profit_growth_weighted: "加权利润增速",
  revenue_growth_weighted: "加权营收增速",
  dividend_yield_weighted: "加权股息率",
  log10_market_cap_weighted: "加权对数市值",
  valuation_percentile_weighted: "加权估值分位",
  quality_growth_weight: "质量成长权重",
  deep_value_weight: "深度价值权重",
  dividend_steady_weight: "红利稳健权重",
  factor_coverage_weight: "因子覆盖权重",
  annualized_volatility_1y: "年化波动率",
  annualized_volatility_3y: "近三年波动率",
  top_10_holding_weight: "前十大持仓权重",
  industry_top1_weight: "第一大行业权重",
  industry_top3_weight: "前三大行业权重",
  industry_count: "行业数量",
  equity_position: "权益仓位",
  manager_tenure_years: "经理任期",
  total_annual_fee: "综合费率",
  fund_size: "基金规模",
  stock_holding_count: "持仓股票数",
  annualized_benchmark_return_1y: "基准年化收益",
};

const REASON_LABELS: Record<string, string> = {
  threshold_not_met: "未达阈值",
  benchmark_data_missing: "基准数据缺失",
  return_window_insufficient: "收益窗口不足",
  stock_factors_missing: "缺少股票因子",
  coverage_passed: "数据覆盖通过",
  threshold_met: "达到阈值",
};

function translateObserved(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  const s = String(value);
  return s
    .replace(/style_weight_below_threshold/g, "风格权重未达阈值")
    .replace(/min\(1y=(\d+), 3y=(\d+)\)/g, "最少 $1 天（1年）/ $2 天（3年）")
    .replace(/all_required_fields_present/g, "所有必要字段已提供")
    .replace(/any_required_field_missing/g, "存在缺失字段")
    .replace(/'(\w+)':\s*([\d.]+)/g, "$1 = $2")
    .replace(/[{}']/g, "");
}

export default function FundReportPage() {
  const { runId = "", fundCode = "" } = useParams();
  const [version, setVersion] = useState(0);
  const { data, error, loading } = useAsync(
    () => fetchFundReport(runId, fundCode),
    [runId, fundCode, version]
  );
  const { data: bench } = useAsync(
    () => fetchBenchmarkComponents(runId, fundCode),
    [runId, fundCode]
  );
  const { data: eligibility } = useAsync(
    () => fetchRelativeEligibility(runId, "all", fundCode),
    [runId, fundCode]
  );
  const { data: percentile } = useAsync(
    () => fetchFundPercentile(runId, fundCode),
    [runId, fundCode]
  );
  const eligibilityRow = eligibility?.results.find((row) => row.fund_code === fundCode) ?? null;
  const relativeReady = eligibilityRow?.relative_label_status === "relative_label_ready";

  const [drillCode, setDrillCode] = useState<string | null>(null);
  const [activeLabel, setActiveLabel] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState("researcher");
  const [decision, setDecision] = useState("confirm");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const tieredLabels = useMemo<Record<LabelTier, FundLabel[]>>(() => {
    const empty: Record<LabelTier, FundLabel[]> = { style: [], relative: [], observe: [], data_only: [], other: [] };
    if (!data) return empty;
    for (const label of data.labels) {
      empty[labelTier(label, relativeReady)].push(label);
    }
    return empty;
  }, [data, relativeReady]);

  const unresolvedCalculations = useMemo(() => {
    if (!data?.calculations) return [];
    return data.calculations.filter(
      (c) => c.state !== "active" && c.reason_code && c.reason_code !== "ok"
    );
  }, [data]);

  const factorCoverage = data?.factor_exposures.find((f) => f.factor_code === "factor_coverage_weight");
  const factorCoverageValue = factorCoverage ? Number(factorCoverage.exposure_value) : null;

  const contributions = data?.equity_style_contributions ?? [];

  // 用于报告头：核心指标摘要
  const annualReturnFeature = data?.features.find((f) => f.feature_code === "annualized_return_1y");
  const annualReturnValue = annualReturnFeature ? Number(annualReturnFeature.value) : null;
  const annualBenchmarkFeature = data?.features.find(
    (f) => f.feature_code === "annualized_benchmark_return_1y"
  );
  const annualBenchmarkValue = annualBenchmarkFeature ? Number(annualBenchmarkFeature.value) : null;
  const taggedStylesCount = data
    ? new Set(
        data.labels
          .filter((l) => l.category === "style" && l.status === "active")
          .map((l) => l.label_code)
      ).size
    : 0;

  const submit = async () => {
    if (!activeLabel) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await postReview(runId, fundCode, activeLabel, decision, reviewer, comment);
      setActiveLabel(null);
      setComment("");
      setVersion((v) => v + 1);
    } catch (e: unknown) {
      setSubmitError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      {/* 报告头 v2：决策摘要 + 关键指标 */}
      <div className="report-head-v2">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span className="flow-steps" style={{ fontSize: 10 }}>
              <span className="flow-step is-done">
                <span className="step-num">1</span>总览
              </span>
              <span className="flow-arrow">→</span>
              <span className="flow-step is-current">
                <span className="step-num">2</span>诊断
              </span>
              <span className="flow-arrow">→</span>
              <span className="flow-step">
                <span className="step-num">3</span>加入组合
              </span>
            </span>
          </div>
          <div className="fund-id">
            <span className="code">{fundCode}</span>
            {eligibilityRow?.fund_name && (
              <span className="name">· {eligibilityRow.fund_name}</span>
            )}
            {data && <ReviewActionBadge value={data.review_action} />}
          </div>
          <div className="meta-row">
            <span>
              批次 <strong>{runId.slice(0, 12)}…</strong>
            </span>
            {factorCoverageValue !== null && (
              <span>
                因子覆盖 <strong>{(factorCoverageValue * 100).toFixed(1)}%</strong>
              </span>
            )}
            {contributions.length > 0 && (
              <span>
                风格贡献明细 <strong>{contributions.length} 条</strong>
              </span>
            )}
            {data?.summary && (
              <span>
                标签 <strong>{data.summary.label_count}</strong> · 证据{" "}
                <strong>{data.summary.evidence_count}</strong>
              </span>
            )}
          </div>
        </div>
        <div className="head-stats">
          <div className="head-stat">
            <div className="label">展示资格</div>
            <div className="value" style={{ color: relativeReady ? "var(--pos-text)" : "var(--warn-text)" }}>
              {eligibilityRow
                ? relativeReady
                  ? "可展示"
                  : "暂不可"
                : "—"}
            </div>
            <div className="sub">
              {eligibilityRow
                ? relativeReady
                  ? "可进入展示池"
                  : cleanBlocker(
                      eligibilityRow.blocking_components ||
                        eligibilityRow.blocking_reason ||
                        ""
                    )
                : "加载中…"}
            </div>
          </div>
          <div className="head-stat">
            <div className="label">年化收益 1Y</div>
            <div className="value">
              {annualReturnValue !== null
                ? `${(annualReturnValue * 100).toFixed(2)}%`
                : "—"}
            </div>
            <div className="sub">
              {annualBenchmarkValue !== null
                ? `基准 ${(annualBenchmarkValue * 100).toFixed(2)}%`
                : "基准缺失"}
            </div>
          </div>
          <div className="head-stat">
            <div className="label">风格标签</div>
            <div className="value">{taggedStylesCount}</div>
            <div className="sub">
              {taggedStylesCount > 0 ? "已识别" : "未识别"}
            </div>
          </div>
        </div>
      </div>

      {/* 工具栏 v2 */}
      <div className="toolbar-v2">
        <span className="flow-step is-done">
          <span className="step-num">✓</span>数据已加载
        </span>
        <div className="spacer" />
        <button
          className="secondary"
          onClick={() =>
            downloadFile(
              `/v1/runs/${runId}/funds/${fundCode}/export?format=xlsx`,
              `fund_${fundCode}.xlsx`
            )
          }
        >
          导出 XLSX
        </button>
        <button
          className="secondary"
          onClick={() =>
            downloadFile(
              `/v1/runs/${runId}/funds/${fundCode}/export?format=csv`,
              `fund_${fundCode}.zip`
            )
          }
        >
          导出 CSV
        </button>
        <Link to={`/compare?codes=${fundCode}`} className="link-btn" style={{ fontSize: 12 }}>
          横向对比 →
        </Link>
      </div>

      {loading && (
        <div className="filter-empty" style={{ marginBottom: 12 }}>
          加载中…
        </div>
      )}
      {error && <div className="alert alert-warn">{error}</div>}

      {/* 展示门禁作为 decision card 形式 */}
      {data && (
        <div className="decision-card">
          <span
            className={`verdict is-${relativeReady ? "go" : "watch"}`}
            style={!relativeReady ? { background: "var(--warn-soft)", color: "var(--warn-text)" } : undefined}
          >
            {relativeReady ? "GO" : "WATCH"}
          </span>
          <div className="takeaway">
            {relativeReady ? (
              <>
                该基金 <strong>可立即进入展示池</strong>
                ：基准已就绪、收益窗口充足、风格已识别。
              </>
            ) : (
              <>
                该基金 <strong>暂不可进入展示池</strong>
                ，主要阻塞：{" "}
                <strong>
                  {cleanBlocker(
                    eligibilityRow?.blocking_components ||
                      eligibilityRow?.blocking_reason ||
                      ""
                  )}
                </strong>
                。需运维修复后可入池。
              </>
            )}
          </div>
          <div className="actions">
            <Link to="/ready-pool" className="secondary">
              返回展示池
            </Link>
          </div>
        </div>
      )}

      {/* 风格标签（核心展示区）— 含下钻 */}
      {data && tieredLabels.style.length > 0 && (
        <div className="report-section">
          <h2>风格标签</h2>
          <p className="muted" style={{ marginTop: -4, marginBottom: 10 }}>
            点击「下钻」查看每只持仓股票对该风格的贡献明细
          </p>
          <div className="style-labels-grid">
            {tieredLabels.style.map((label) => {
              const ev = evidenceForLabel(data, label.label_code);
              const hasDrill = contributions.some((c) => c.style_code === label.label_code);
              return (
                <div className="style-label-item" key={label.label_code}>
                  <span className={styleTagClass(label.label_code)}>{label.label_name}</span>
                  {ev[0] && <div className="label-evidence">{ev[0].message}</div>}
                  <div style={{ display: "flex", gap: 6 }}>
                    {hasDrill && (
                      <button
                        className="drill-toggle"
                        onClick={() => setDrillCode(drillCode === label.label_code ? null : label.label_code)}
                      >
                        {drillCode === label.label_code ? "收起" : "下钻"}
                      </button>
                    )}
                    <button className="secondary compact-button" onClick={() => setActiveLabel(label.label_code)}>
                      复核
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          {drillCode && <DrillDownPanel contributions={contributions} styleCode={drillCode} />}
        </div>
      )}

      {/* 相对基准标签 */}
      {data && tieredLabels.relative.length > 0 && (
        <div className="report-section">
          <h2>相对基准</h2>
          <div className="style-labels-grid">
            {tieredLabels.relative.map((label) => {
              const ev = evidenceForLabel(data, label.label_code);
              return (
                <div className="style-label-item" key={label.label_code}>
                  <span className="style-tag">{label.label_name}</span>
                  {ev[0] && <div className="label-evidence">{ev[0].message}</div>}
                  <button className="secondary compact-button" onClick={() => setActiveLabel(label.label_code)}>
                    复核
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 风格观察 */}
      {data && tieredLabels.observe.length > 0 && (
        <div className="report-section">
          <h2>风格观察</h2>
          <div className="tier-list">
            {tieredLabels.observe.map((label) => {
              const ev = evidenceForLabel(data, label.label_code);
              return (
                <div className="tier-item" key={label.label_code}>
                  <strong>{label.label_name}</strong>
                  <span className="muted"><code>{label.label_code}</code></span>
                  {ev[0] && <div className="muted">{ev[0].message}</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 基准解析 */}
      {bench && (
        <div className="report-section">
          <h2>基准解析</h2>
          {bench.has_benchmark_returns ? (
            <div className="alert alert-ok">
              基准收益已合成（{bench.benchmark_returns_count} 行），全部组件已解析。
            </div>
          ) : (
            <div className="alert alert-warn">
              未能合成基准日收益，相对基准类标签无法计算。
              {bench.unresolved_count > 0 && ` ${bench.unresolved_count} 个组件未解析。`}
            </div>
          )}
          {bench.components.length > 0 && (
            <table>
              <thead>
                <tr><th>#</th><th>组件</th><th className="num">权重</th><th>状态</th><th>收益源</th></tr>
              </thead>
              <tbody>
                {bench.components.map((c) => (
                  <tr key={c.component_order}>
                    <td>{c.component_order}</td>
                    <td>
                      <strong>{c.component_name}</strong>
                      {c.component_code && <div className="muted">{c.component_code}</div>}
                    </td>
                    <td className="num">{c.weight !== null ? `${(c.weight * 100).toFixed(1)}%` : "-"}</td>
                    <td>{c.status === "resolved" ? "已解析" : c.status === "missing_source" ? "缺收益源" : c.status}</td>
                    <td>{c.has_returns ? "有" : "无"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* 同类分位排名 */}
      {percentile && percentile.ranks.length > 0 && (
        <div className="report-section">
          <h2>同类分位排名</h2>
          <p className="muted" style={{ marginBottom: 8, fontSize: 12 }}>
            在不同风格组中的相对位置（百分位 1.0 = 同类第一）
          </p>
          <PercentilePanel
            ranks={percentile.ranks}
            fundStyleTags={data?.labels.filter((l) => l.status === "active").map((l) => l.label_code) ?? []}
          />
        </div>
      )}

      {/* 因子暴露 */}
      {data && data.factor_exposures.length > 0 && (
        <div className="report-section">
          <h2>因子暴露</h2>
          <table>
            <thead>
              <tr><th>因子</th><th className="num">暴露值</th><th className="num">覆盖权重</th><th>股票覆盖</th></tr>
            </thead>
            <tbody>
              {data.factor_exposures.map((f) => (
                <tr key={`${f.report_date}-${f.factor_code}`}>
                  <td>{METRIC_NAMES[f.factor_code] ?? f.factor_code}</td>
                  <td className="num">{Number(f.exposure_value).toFixed(4)}</td>
                  <td className="num">{(Number(f.coverage_weight) * 100).toFixed(1)}%</td>
                  <td>{f.covered_stock_count}/{f.stock_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 标签详情 */}
      {data && (
        <div className="report-section">
          <h2>标签详情</h2>
          <table>
            <thead>
              <tr><th>标签</th><th>状态</th><th>证据</th><th></th></tr>
            </thead>
            <tbody>
              {data.labels
                .filter((label) => shouldDisplayTier(labelTier(label, relativeReady)))
                .map((label) => {
                  const ev = data.evidence.filter((e) => e.label_code === label.label_code);
                  return (
                    <tr key={label.label_code}>
                      <td>
                        <strong>{label.label_name}</strong>
                        <div className="muted">{label.label_code}</div>
                      </td>
                      <td><LabelStatusBadge value={label.status} /></td>
                      <td>
                        {ev.map((e, i) => (
                          <div key={i} className="muted" style={{ marginBottom: 2 }}>{e.message}</div>
                        ))}
                      </td>
                      <td>
                        <button className="secondary compact-button" onClick={() => setActiveLabel(label.label_code)}>
                          复核
                        </button>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      )}

      {/* 未触发原因 */}
      {data && unresolvedCalculations.length > 0 && (
        <div className="report-section">
          <h2>未触发标签原因</h2>
          <table>
            <thead>
              <tr><th>标签</th><th>原因</th><th>观测值</th><th>阈值</th></tr>
            </thead>
            <tbody>
              {unresolvedCalculations.map((c) => (
                <tr key={c.label_code}>
                  <td><strong>{c.label_name}</strong></td>
                  <td className="muted">{c.message}（{REASON_LABELS[c.reason_code] ?? c.reason_code}）</td>
                  <td className="num">{translateObserved(c.observed)}</td>
                  <td className="num">{translateObserved(c.threshold)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 历史复核 */}
      {data && data.reviews.length > 0 && (
        <div className="report-section">
          <h2>历史复核</h2>
          <table>
            <thead>
              <tr><th>标签</th><th>决定</th><th>复核人</th><th>备注</th></tr>
            </thead>
            <tbody>
              {data.reviews.map((r) => (
                <tr key={r.review_id}>
                  <td>{styleCodeToName(r.label_code)}</td>
                  <td>{reviewActionLabel(r.decision)}</td>
                  <td>{r.reviewer}</td>
                  <td>{r.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 复核弹层 */}
      {activeLabel && (
        <div className="card">
          <h2>提交复核 — {activeLabel}</h2>
          {submitError && <div className="alert alert-warn">{submitError}</div>}
          <div className="toolbar">
            <label>
              决定
              <select value={decision} onChange={(e) => setDecision(e.target.value)}>
                <option value="confirm">确认</option>
                <option value="reject">驳回</option>
                <option value="observe">观察</option>
              </select>
            </label>
            <label>
              复核人
              <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
            </label>
          </div>
          <textarea
            placeholder="备注"
            rows={3}
            style={{ width: "100%", marginBottom: 12 }}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <div className="toolbar">
            <button onClick={submit} disabled={submitting}>
              {submitting ? "提交中…" : "提交"}
            </button>
            <button className="secondary" onClick={() => setActiveLabel(null)}>取消</button>
          </div>
        </div>
      )}
    </div>
  );
}
