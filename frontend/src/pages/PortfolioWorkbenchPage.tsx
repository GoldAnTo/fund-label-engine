import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  applyPortfolioRoleReviewSuggestions,
  deletePortfolioRoleReview,
  fetchFundReport,
  fetchPortfolioDraft,
  fetchPortfolioMatrix,
  fetchPortfolioRoleReviewSuggestions,
  fetchPortfolioRoleReviews,
  fetchRelativeEligibility,
  fetchRuns,
  postPortfolioRoleReview,
  type ApplySuggestionsRequest,
  type FundLabel,
  type FundReport,
  type PortfolioDraftMode,
  type PortfolioDraftResponse,
  type PortfolioMatrixResponse,
  type PortfolioRoleReview,
  type RelativeEligibilityResponse,
  type RoleReviewSuggestion,
} from "../api";
import { LabelStatusBadge, ReviewActionBadge } from "../components";
import { labelTier, tierTitle, type LabelTier } from "../labelTiers";

const BUCKET_LABELS: Record<string, string> = {
  core: "核心",
  satellite: "卫星",
  index_tool: "指数工具",
  cash_buffer: "现金缓冲",
  exclude: "排除",
};

const TAG_LABELS: Record<string, string> = {
  active_equity_candidate: "主动权益",
  core_holding_candidate: "核心候选",
  satellite_alpha: "卫星α",
  defensive_anchor: "防守锚",
  index_tool: "指数工具",
  deep_value: "深度价值",
  low_valuation: "低估值",
  high_valuation: "高估值",
  quality_growth: "质量成长",
  high_roe: "高盈利",
  profit_growth_strong: "利润高增长",
  dividend_steady: "红利稳健",
  large_cap: "大盘",
  mid_cap: "中盘",
  small_cap: "小盘",
  alpha_positive: "Alpha正",
  alpha_negative: "Alpha负",
  excess_return_strong: "超额收益强",
  volatility_high: "高波动",
  volatility_low: "低波动",
  sharpe_high: "高夏普",
  data_sufficient: "数据充分",
  benchmark_data_missing: "基准缺失",
};

const FEATURE_LABELS: Record<string, string> = {
  annualized_return_1y: "近一年收益",
  max_drawdown_1y: "最大回撤",
  volatility_1y: "波动率",
  sharpe_1y: "夏普",
  fund_size: "规模",
  manager_tenure_years: "经理任期",
  expense_ratio: "费率",
  equity_position: "权益仓位",
  top_10_holding_weight: "前十大",
  annualized_excess_return_1y: "超额收益",
  tracking_error_1y: "跟踪误差",
  information_ratio_1y: "信息比率",
  beta_1y: "Beta",
  alpha_1y: "Alpha",
};

const REVIEW_DECISIONS = [
  { value: "core", label: "核心" },
  { value: "satellite", label: "卫星" },
  { value: "index_tool", label: "指数工具" },
  { value: "exclude", label: "排除" },
];

type FundRow = PortfolioMatrixResponse["rows"][number];

function bucketLabel(value: string) {
  return BUCKET_LABELS[value] ?? value;
}

function tagLabel(value: string) {
  return TAG_LABELS[value] ?? value;
}

function featureLabel(value: string) {
  return FEATURE_LABELS[value] ?? value;
}

function displayValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  return value;
}

function isReadyStatus(value: string | undefined) {
  return value === "relative_label_ready" || value === "relative_label_ready_approx";
}

function readyLabel(value: string | undefined) {
  if (!value) return "—";
  if (isReadyStatus(value)) return "可展示";
  if (value === "benchmark_source_missing") return "缺基准源";
  if (value === "nav_window_insufficient") return "窗口不足";
  if (value === "benchmark_missing") return "未配置基准";
  return value;
}

function reviewMap(reviews: PortfolioRoleReview[]) {
  const map = new Map<string, PortfolioRoleReview>();
  reviews.forEach((r) => {
    const existing = map.get(r.fund_code);
    if (!existing || r.reviewed_at >= existing.reviewed_at) map.set(r.fund_code, r);
  });
  return map;
}

function tierLabels(data: FundReport | null, relativeReady: boolean) {
  const empty: Record<LabelTier, FundLabel[]> = { style: [], relative: [], observe: [], data_only: [], other: [] };
  if (!data) return empty;
  data.labels.forEach((label) => empty[labelTier(label, relativeReady)].push(label));
  return empty;
}

function evidenceForLabel(data: FundReport, labelCode: string) {
  return data.evidence.filter((item) => item.label_code === labelCode);
}

function rowTags(row: FundRow) {
  return [...row.portfolio_roles, ...row.style_tags, ...row.return_tags, ...row.risk_tags, ...row.data_tags].filter(Boolean);
}

export default function PortfolioWorkbenchPage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [matrix, setMatrix] = useState<PortfolioMatrixResponse | null>(null);
  const [draft, setDraft] = useState<PortfolioDraftResponse | null>(null);
  const [draftMode, setDraftMode] = useState<PortfolioDraftMode>("research");
  const [reviews, setReviews] = useState<PortfolioRoleReview[]>([]);
  const [eligibility, setEligibility] = useState<RelativeEligibilityResponse | null>(null);
  const [selectedFund, setSelectedFund] = useState("");
  const [selectedReport, setSelectedReport] = useState<FundReport | null>(null);
  const [query, setQuery] = useState("");
  const [scopeFilter, setScopeFilter] = useState("all");
  const [reviewer, setReviewer] = useState("researcher-a");
  const [savingFund, setSavingFund] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<RoleReviewSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [applyingSuggestions, setApplyingSuggestions] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    fetchRuns().then((payload) => {
      setRuns(payload);
      if (payload.length > 0) setRunId(payload[0].run_id);
    }).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    Promise.all([
      fetchPortfolioMatrix(runId),
      fetchPortfolioDraft(runId, draftMode),
      fetchPortfolioRoleReviews(runId),
      fetchRelativeEligibility(runId, "all"),
    ]).then(([m, d, r, e]) => {
      setMatrix(m);
      setDraft(d);
      setReviews(r);
      setEligibility(e);
      setSelectedFund((cur) => cur && m.rows.some((row) => row.fund_code === cur) ? cur : d.rows[0]?.fund_code ?? m.rows[0]?.fund_code ?? "");
    }).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [runId, draftMode]);

  useEffect(() => {
    if (!runId || !selectedFund) { setSelectedReport(null); return; }
    setReportLoading(true);
    fetchFundReport(runId, selectedFund).then(setSelectedReport).catch((e) => { setSelectedReport(null); setReportError(e.message); }).finally(() => setReportLoading(false));
  }, [runId, selectedFund]);

  const draftByFund = useMemo(() => {
    const map = new Map<string, PortfolioDraftResponse["rows"][number]>();
    draft?.rows.forEach((row) => map.set(row.fund_code, row));
    return map;
  }, [draft]);

  const reviewsByFund = useMemo(() => reviewMap(reviews), [reviews]);

  const eligibilityByFund = useMemo(() => {
    const map = new Map<string, RelativeEligibilityResponse["results"][number]>();
    eligibility?.results.forEach((row) => map.set(row.fund_code, row));
    return map;
  }, [eligibility]);

  const selectedMatrixRow = matrix?.rows.find((row) => row.fund_code === selectedFund) ?? null;
  const selectedEligibility = selectedFund ? eligibilityByFund.get(selectedFund) ?? null : null;
  const selectedReview = selectedFund ? reviewsByFund.get(selectedFund) ?? null : null;
  const relativeReady = isReadyStatus(selectedEligibility?.relative_label_status);
  const groupedLabels = useMemo(() => tierLabels(selectedReport, relativeReady), [selectedReport, relativeReady]);

  const bucketCounts = useMemo(() => {
    const counts = new Map<string, number>();
    draft?.rows.forEach((row) => counts.set(row.bucket, (counts.get(row.bucket) ?? 0) + 1));
    return counts;
  }, [draft]);

  const filteredRows = useMemo(() => {
    const text = query.trim().toLowerCase();
    return (matrix?.rows ?? []).filter((row) => {
      const ready = eligibilityByFund.get(row.fund_code);
      const draftRow = draftByFund.get(row.fund_code);
      const tags = rowTags(row);
      const searchable = [row.fund_code, ready?.fund_name ?? "", ...tags.map(tagLabel)].join(" ").toLowerCase();
      if (text && !searchable.includes(text)) return false;
      if (scopeFilter === "ready" && !isReadyStatus(ready?.relative_label_status)) return false;
      if (scopeFilter === "blocked" && isReadyStatus(ready?.relative_label_status)) return false;
      if (scopeFilter === "draft" && !draftRow) return false;
      if (scopeFilter === "review" && row.allocation_status !== "review_required") return false;
      return true;
    });
  }, [draftByFund, eligibilityByFund, matrix, query, scopeFilter]);

  const saveReview = async (fundCode: string, targetBucket: string) => {
    if (!runId || !targetBucket) return;
    setSavingFund(fundCode);
    try {
      const saved = await postPortfolioRoleReview(runId, {
        fund_code: fundCode, role_code: "manual_portfolio_role", decision: "accept",
        target_bucket: targetBucket as "core" | "satellite" | "index_tool" | "exclude",
        max_weight_pct: 0, rationale: "workbench", reviewer,
      });
      const nextDraft = await fetchPortfolioDraft(runId, draftMode);
      setReviews((cur) => [saved, ...cur.filter((i) => i.fund_code !== fundCode || i.role_code !== saved.role_code)]);
      setDraft(nextDraft);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setSavingFund(null); }
  };

  const loadSuggestions = async () => {
    if (!runId) return;
    setLoadingSuggestions(true);
    try {
      const payload = await fetchPortfolioRoleReviewSuggestions(runId);
      setSuggestions(payload.suggestions || []);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setLoadingSuggestions(false); }
  };

  const applyAllSuggestions = async () => {
    if (!runId || suggestions.length === 0) return;
    setApplyingSuggestions(true);
    try {
      const payload: ApplySuggestionsRequest = {
        reviewer,
        items: suggestions.map((s) => ({
          fund_code: s.fund_code, role_code: s.role_code, decision: s.decision,
          target_bucket: s.target_bucket as "core" | "satellite" | "index_tool" | "cash_buffer" | "exclude",
          max_weight_pct: s.recommended_max_weight_pct, rationale: s.rationale,
        })),
      };
      const result = await applyPortfolioRoleReviewSuggestions(runId, payload);
      setSuggestions([]);
      const [nextReviews, nextDraft] = await Promise.all([fetchPortfolioRoleReviews(runId), fetchPortfolioDraft(runId, draftMode)]);
      setReviews(nextReviews);
      setDraft(nextDraft);
      alert(`已采纳 ${result.applied_count} 条建议`);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setApplyingSuggestions(false); }
  };

  const clearReview = async (review: PortfolioRoleReview) => {
    if (!runId) return;
    setSavingFund(review.fund_code);
    try {
      await deletePortfolioRoleReview(runId, review.fund_code, review.role_code);
      const nextDraft = await fetchPortfolioDraft(runId, draftMode);
      setReviews((cur) => cur.filter((i) => i.fund_code !== review.fund_code || i.role_code !== review.role_code));
      setDraft(nextDraft);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setSavingFund(null); }
  };

  const totalFunds = matrix?.total_count ?? 0;
  const draftCount = draft?.rows.length ?? 0;
  const reviewCount = reviews.length;
  const selectedTags = selectedMatrixRow ? rowTags(selectedMatrixRow) : [];
  const featurePreview = selectedReport?.features.slice(0, 8) ?? [];

  return (
    <div>
      {/* 上下文栏 */}
      <div className="context-bar">
        <div className="chip chip-mono">
          <span className="label">批次</span>
          <span className="value">{runId ? runId.slice(0, 12) : "—"}</span>
        </div>
        <div className="chip">
          <span className="label">基金</span>
          <span className="value">{totalFunds} 只</span>
        </div>
        <div className="chip">
          <span className="label">草案</span>
          <span className="value">{draftCount} 只</span>
        </div>
        <div className="chip">
          <span className="label">已签核</span>
          <span className="value">{reviewCount} 只</span>
        </div>
        <div className="spacer" />
        <select value={draftMode} onChange={(e) => setDraftMode(e.target.value as PortfolioDraftMode)}>
          <option value="research">研究草案</option>
          <option value="accepted">已验收组合</option>
        </select>
        {runs.length > 1 && (
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>{r.run_at.slice(0, 10)}</option>
            ))}
          </select>
        )}
      </div>

      {error && <div className="alert alert-warn">{error}</div>}
      {loading && <div className="alert alert-info">加载中...</div>}

      {/* 角色分桶概览 */}
      {bucketCounts.size > 0 && (
        <div className="metric-grid" style={{ gridTemplateColumns: `repeat(${Math.min(bucketCounts.size, 5)}, 1fr)` }}>
          {[...bucketCounts.entries()].map(([bucket, count]) => {
            const weight = draft?.rows.filter((r) => r.bucket === bucket).reduce((s, r) => s + r.draft_weight_pct, 0) ?? 0;
            return (
              <div key={bucket} className={`metric-card-v2 ${bucket === "core" ? "is-accent" : bucket === "exclude" ? "is-warn" : ""}`}>
                <div className="label">{bucketLabel(bucket)}</div>
                <div className="value">{count}</div>
                <div className="sub">{weight.toFixed(1)}% 草案权重</div>
              </div>
            );
          })}
        </div>
      )}

      {/* 基金地图 + Inspector */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div className="toolbar-v2" style={{ marginBottom: 0, borderRadius: 0, border: "none", borderBottom: "1px solid var(--border)" }}>
          <div className="filter-group">
            {[
              { v: "all", l: "全部" },
              { v: "ready", l: "可展示" },
              { v: "blocked", l: "不可展示" },
              { v: "draft", l: "已进草案" },
              { v: "review", l: "需复核" },
            ].map((opt) => (
              <button key={opt.v} className={scopeFilter === opt.v ? "active" : ""} onClick={() => setScopeFilter(opt.v)}>
                {opt.l}
              </button>
            ))}
          </div>
          <div className="search">
            <input type="search" placeholder="搜索基金代码、名称、标签" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <div className="spacer" />
          <div className="meta">{filteredRows.length} 只</div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "minmax(300px, 0.9fr) minmax(0, 1.1fr)", gap: 0, alignItems: "start" }}>
          {/* 基金列表 */}
          <div style={{ maxHeight: "calc(100vh - 200px)", overflow: "auto", padding: 8, borderRight: "1px solid var(--border)" }}>
            <table className="table-v2">
              <thead>
                <tr>
                  <th>基金</th>
                  <th>角色</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => {
                  const ready = eligibilityByFund.get(row.fund_code);
                  const draftRow = draftByFund.get(row.fund_code);
                  return (
                    <tr key={row.fund_code} className={selectedFund === row.fund_code ? "is-selected" : ""} onClick={() => setSelectedFund(row.fund_code)}>
                      <td>
                        <div className="fund-row-code">
                          <span className="code">{row.fund_code}</span>
                          <span className="name">{ready?.fund_name ?? "—"}</span>
                        </div>
                      </td>
                      <td>{draftRow ? <span className="badge badge-active">{bucketLabel(draftRow.bucket)}</span> : <span className="muted">—</span>}</td>
                      <td><span className={`status-pill ${isReadyStatus(ready?.relative_label_status) ? "is-go" : "is-watch"}`}>{readyLabel(ready?.relative_label_status)}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredRows.length === 0 && <div className="empty-state"><div className="title">没有命中的基金</div></div>}
          </div>

          {/* Inspector */}
          <div style={{ padding: 16, background: "var(--surface-2)", minHeight: 400 }}>
            {!selectedFund && <div className="empty-state"><div className="title">选择一只基金查看详情</div></div>}
            {selectedFund && (
              <>
                {/* 基金头部 */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
                  <div>
                    <span style={{ fontFamily: "ui-monospace, monospace", fontWeight: 800, fontSize: 20 }}>{selectedFund}</span>
                    {selectedEligibility?.fund_name && <span style={{ marginLeft: 8, color: "var(--text-2)", fontSize: 13 }}>{selectedEligibility.fund_name}</span>}
                  </div>
                  {selectedReport && <ReviewActionBadge value={selectedReport.review_action} />}
                </div>

                {reportError && <div className="alert alert-warn">{reportError}</div>}
                {reportLoading && <div className="alert alert-info">加载中...</div>}

                {/* 标签 */}
                {selectedTags.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 12 }}>
                    {selectedTags.slice(0, 12).map((tag) => (
                      <span key={tag} className="badge badge-default" style={{ fontSize: 10.5 }}>{tagLabel(tag)}</span>
                    ))}
                  </div>
                )}

                {/* 统计 */}
                <div className="metric-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", marginBottom: 12 }}>
                  <div className="metric-card-v2"><div className="label">标签</div><div className="value" style={{ fontSize: 18 }}>{selectedReport?.summary.label_count ?? "—"}</div></div>
                  <div className="metric-card-v2"><div className="label">证据</div><div className="value" style={{ fontSize: 18 }}>{selectedReport?.summary.evidence_count ?? "—"}</div></div>
                  <div className="metric-card-v2"><div className="label">缺失</div><div className="value" style={{ fontSize: 18 }}>{selectedReport?.summary.missing_field_count ?? "—"}</div></div>
                </div>

                {/* 风格标签 + 证据 */}
                {selectedReport && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                    {(["style", "relative"] as LabelTier[]).map((tier) => (
                      <div key={tier}>
                        <div className="section-head"><h2>{tierTitle(tier)}</h2></div>
                        {groupedLabels[tier].slice(0, 4).map((label) => {
                          const ev = evidenceForLabel(selectedReport, label.label_code);
                          return (
                            <div key={label.label_code} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                <strong style={{ fontSize: 12 }}>{label.label_name}</strong>
                                <LabelStatusBadge value={label.status} />
                              </div>
                              {ev[0] && <div className="muted" style={{ fontSize: 10.5, marginTop: 2 }}>{ev[0].message}</div>}
                            </div>
                          );
                        })}
                        {groupedLabels[tier].length === 0 && <span className="muted">暂无</span>}
                      </div>
                    ))}
                  </div>
                )}

                {/* 关键数据 */}
                {featurePreview.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div className="section-head"><h2>关键指标</h2></div>
                    <table className="table-v2" style={{ fontSize: 11.5 }}>
                      <tbody>
                        {featurePreview.map((f) => (
                          <tr key={f.feature_code}>
                            <td>{featureLabel(f.feature_code)}</td>
                            <td className="num">{displayValue(f.value)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* 角色复核 */}
                <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--r)", border: "1px solid var(--border)", marginBottom: 12 }}>
                  <div className="section-head"><h2>角色复核</h2></div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <label style={{ fontSize: 11.5, color: "var(--text-2)" }}>复核人</label>
                    <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} style={{ width: 120, fontSize: 11.5 }} />
                    <label style={{ fontSize: 11.5, color: "var(--text-2)", marginLeft: 8 }}>角色</label>
                    <select value={selectedReview?.target_bucket ?? ""} onChange={(e) => saveReview(selectedFund, e.target.value)} disabled={savingFund === selectedFund || !reviewer.trim()} style={{ fontSize: 11.5 }}>
                      <option value="">待确认</option>
                      {REVIEW_DECISIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                    </select>
                    {selectedReview && (
                      <>
                        <span className="badge badge-active">人工: {bucketLabel(selectedReview.target_bucket)}</span>
                        <button className="secondary compact-button" onClick={() => clearReview(selectedReview)} disabled={savingFund === selectedFund}>撤销</button>
                      </>
                    )}
                  </div>
                </div>

                {/* 批量建议 */}
                <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--r)", border: "1px solid var(--border)", marginBottom: 12 }}>
                  <div className="section-head">
                    <h2>批量角色建议</h2>
                    <div className="actions">
                      <button className="secondary compact-button" onClick={loadSuggestions} disabled={loadingSuggestions}>{loadingSuggestions ? "加载中..." : "生成建议"}</button>
                      <button className="compact-button" onClick={applyAllSuggestions} disabled={applyingSuggestions || suggestions.length === 0}>采纳 ({suggestions.length})</button>
                    </div>
                  </div>
                  {suggestions.length > 0 ? (
                    <table className="table-v2" style={{ fontSize: 11 }}>
                      <tbody>
                        {suggestions.slice(0, 8).map((s) => (
                          <tr key={`${s.fund_code}-${s.role_code}`}>
                            <td style={{ fontFamily: "ui-monospace, monospace", fontWeight: 700 }}>{s.fund_code}</td>
                            <td>{bucketLabel(s.target_bucket)}</td>
                            <td className="muted" style={{ fontSize: 10.5 }}>{s.rationale}</td>
                          </tr>
                        ))}
                        {suggestions.length > 8 && <tr><td colSpan={3} className="muted">...另 {suggestions.length - 8} 条</td></tr>}
                      </tbody>
                    </table>
                  ) : (
                    <span className="muted" style={{ fontSize: 11.5 }}>点击"生成建议"获取角色推荐</span>
                  )}
                </div>

                <Link to={`/runs/${runId}/funds/${selectedFund}`} className="link-btn" style={{ fontSize: 12 }}>进入完整基金报告 →</Link>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
