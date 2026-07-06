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
  type PortfolioRoleReviewSuggestions,
  type RelativeEligibilityResponse,
  type RoleReviewSuggestion,
} from "../api";
import { LabelStatusBadge, ReviewActionBadge } from "../components";
import { labelTier, tierTitle, type LabelTier } from "../labelTiers";

const STATUS_LABELS: Record<string, string> = {
  eligible: "可进草案",
  observe: "观察池",
  review_required: "需复核",
  excluded: "已排除",
};

const READY_LABELS: Record<string, string> = {
  relative_label_ready: "可展示",
  relative_label_ready_approx: "可展示，近似基准",
  benchmark_source_missing: "缺少基准收益源",
  benchmark_mapping_required: "需要确认基准映射",
  benchmark_unresolved: "基准组件未解析",
  benchmark_missing: "未配置业绩基准",
  nav_window_insufficient: "收益窗口不足",
};

const BUCKET_LABELS: Record<string, string> = {
  core: "核心",
  satellite: "卫星",
  index_tool: "指数工具",
  cash_buffer: "现金缓冲",
  exclude: "排除",
};

const TAG_LABELS: Record<string, string> = {
  active_equity_candidate: "主动权益候选",
  core_holding_candidate: "核心候选",
  satellite_alpha: "卫星阿尔法",
  defensive_anchor: "防守锚",
  index_tool: "指数工具",
  style_deep_value: "深度价值",
  style_quality_growth: "质量成长",
  style_dividend_steady: "红利稳健",
  style_balanced: "风格均衡",
  alpha_positive: "Alpha 为正",
  alpha_negative: "Alpha 为负",
  excess_return_positive: "超额收益为正",
  excess_return_negative: "超额收益为负",
  volatility_high: "高波动",
  volatility_low: "低波动",
  drawdown_high: "高回撤",
  sharpe_high: "高夏普",
  data_sufficient: "数据充分",
  return_window_insufficient: "收益窗口不足",
  // 风格标签
  deep_value: "深度价值",
  low_valuation: "低估值",
  high_valuation: "高估值",
  quality_growth: "质量成长",
  high_roe: "高盈利",
  profit_growth_strong: "利润高增长",
  dividend_steady: "红利稳健",
  high_dividend_financial: "金融高股息",
  consumer_quality: "消费质量",
  large_cap: "大盘",
  mid_cap: "中盘",
  small_cap: "小盘",
  tech_focused: "科技主题",
  finance_focused: "金融主题",
  consumer_focused: "消费主题",
  healthcare_focused: "医药主题",
  cyclical_focused: "周期主题",
  value_dividend: "价值红利",
  growth_large_cap: "大盘成长",
  growth_small_cap: "小盘成长",
  small_cap_growth: "小盘高成长",
  quality_dividend: "高质量红利",
  value_quality: "价值质量",
  growth_profit: "成长盈利",
  // 收益风险标签
  long_term_return_strong: "长期收益优秀",
  // 持仓标签
  equity_position_high: "权益仓位高",
  holding_concentration_high: "持仓集中度高",
  industry_concentration_high: "行业集中度高",
  industry_concentration_observe: "行业集中观察",
  industry_diversified: "行业分散",
  // 描述性标签
  manager_tenure_long: "经理任期长",
  fee_low: "费率低",
  fee_high: "费率高",
  fund_size_moderate: "规模适中",
  fund_size_small: "规模偏小",
  // 相对基准标签
  excess_return_strong: "超额收益较强",
  information_ratio_high: "信息比率较高",
  tracking_error_high: "跟踪误差较高",
  beta_high: "Beta 较高",
  beta_low: "Beta 较低",
  benchmark_data_missing: "基准数据缺失",
  // 数据质量
  data_insufficient: "数据不足",
  manual_review_required: "需人工复核",
};

const FEATURE_LABELS: Record<string, string> = {
  annualized_return_1y: "近一年收益",
  annualized_return_3y: "近三年收益",
  annualized_return_1m: "近一月收益",
  annualized_return_3m: "近三月收益",
  max_drawdown_1y: "最大回撤",
  max_drawdown_3y: "近三年最大回撤",
  volatility_1y: "波动率",
  volatility_3y: "近三年波动率",
  sharpe_1y: "夏普",
  sharpe_3y: "近三年夏普",
  sharpe_ratio_1y: "夏普比率",
  fund_size: "基金规模",
  manager_tenure_years: "经理任职",
  expense_ratio: "费率",
  total_annual_fee: "综合费率",
  equity_position: "权益仓位",
  top_10_holding_weight: "前十大持仓",
  stock_holding_count: "持仓股票数",
  industry_top1_weight: "第一大行业",
  industry_top3_weight: "前三大行业",
  industry_count: "行业数量",
  // 相对基准
  annualized_excess_return_1y: "超额收益",
  annualized_excess_return_3y: "近三年超额收益",
  tracking_error_1y: "跟踪误差",
  information_ratio_1y: "信息比率",
  beta_1y: "Beta",
  alpha_1y: "Alpha",
  annualized_benchmark_return_1y: "基准收益",
  // 因子暴露
  pb_weighted: "加权 PB",
  pe_weighted: "加权 PE",
  roe_weighted: "加权 ROE",
  profit_growth_weighted: "加权利润增速",
  revenue_growth_weighted: "加权营收增速",
  dividend_yield_weighted: "加权股息率",
  log10_market_cap_weighted: "加权对数市值",
  valuation_percentile_weighted: "加权估值分位",
};

const REVIEW_DECISIONS = [
  { value: "core", label: "核心" },
  { value: "satellite", label: "卫星" },
  { value: "index_tool", label: "指数工具" },
  { value: "exclude", label: "排除" },
];

const DELIVERY_LANES = [
  { title: "标签引擎", body: "覆盖率、收益风险、持仓、经理、费率、风格、相对基准标签全部有证据。" },
  { title: "可展示池", body: "把可对外展示和暂不可展示的基金分开，明确每个阻塞原因。" },
  { title: "Benchmark 审计", body: "检查基准组件、收益源、近似口径，避免相对标签误读。" },
  { title: "人工复核", body: "复核队列承接边界样本，保留研究员判断和签核痕迹。" },
  { title: "组合草案", body: "把基金映射到核心、卫星、指数工具，形成可讨论的组合雏形。" },
];

const FLOW = ["数据接入", "标签计算", "证据落库", "展示门禁", "人工签核", "组合草案"];

type FundRow = PortfolioMatrixResponse["rows"][number];

function statusLabel(value: string) {
  return STATUS_LABELS[value] ?? value;
}

function readyLabel(value: string | undefined) {
  return value ? READY_LABELS[value] ?? value : "资格加载中";
}

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

function badgeClass(status: string | undefined) {
  if (isReadyStatus(status) || status === "eligible") return "badge-observe";
  if (status === "review_required") return "badge-manual_review";
  if (status === "excluded") return "badge-default";
  return "badge-active";
}

function reviewMap(reviews: PortfolioRoleReview[]) {
  const map = new Map<string, PortfolioRoleReview>();
  reviews.forEach((review) => {
    const existing = map.get(review.fund_code);
    if (!existing || review.reviewed_at >= existing.reviewed_at) map.set(review.fund_code, review);
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

function readableBlocker(value: string | undefined) {
  if (!value) return "没有阻塞项";
  return value
    .replaceAll("benchmark_source_status=benchmark_missing", "未配置业绩基准")
    .replaceAll("benchmark_source_status=missing_source", "缺少基准收益源")
    .replaceAll("benchmark_source_status=mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_source_status=unresolved", "基准组件未解析")
    .replaceAll("relative_label_ready_approx", "可展示，近似基准")
    .replaceAll("relative_label_ready", "可展示")
    .replaceAll("benchmark_source_missing", "缺少基准收益源")
    .replaceAll("benchmark_mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_unresolved", "基准组件未解析")
    .replaceAll("benchmark_missing", "未配置业绩基准")
    .replaceAll("nav_window_insufficient", "收益窗口不足")
    .replace(/\b[A-Z0-9_]+:/g, "");
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
    fetchRuns()
      .then((payload) => {
        setRuns(payload);
        if (payload.length > 0) setRunId(payload[0].run_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchPortfolioMatrix(runId),
      fetchPortfolioDraft(runId, draftMode),
      fetchPortfolioRoleReviews(runId),
      fetchRelativeEligibility(runId, "all"),
    ])
      .then(([matrixPayload, draftPayload, reviewPayload, eligibilityPayload]) => {
        setMatrix(matrixPayload);
        setDraft(draftPayload);
        setReviews(reviewPayload);
        setEligibility(eligibilityPayload);
        setSelectedFund((current) => {
          if (current && matrixPayload.rows.some((row) => row.fund_code === current)) return current;
          return draftPayload.rows[0]?.fund_code ?? matrixPayload.rows[0]?.fund_code ?? "";
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId, draftMode]);

  useEffect(() => {
    if (!runId || !selectedFund) {
      setSelectedReport(null);
      return;
    }
    setReportLoading(true);
    setReportError(null);
    fetchFundReport(runId, selectedFund)
      .then(setSelectedReport)
      .catch((e) => {
        setSelectedReport(null);
        setReportError(e.message);
      })
      .finally(() => setReportLoading(false));
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
  const selectedDraftRow = selectedFund ? draftByFund.get(selectedFund) ?? null : null;
  const selectedReview = selectedFund ? reviewsByFund.get(selectedFund) ?? null : null;
  const relativeReady = isReadyStatus(selectedEligibility?.relative_label_status);
  const groupedLabels = useMemo(() => tierLabels(selectedReport, relativeReady), [selectedReport, relativeReady]);

  const statusCounts = useMemo(() => {
    const counts = new Map<string, number>();
    matrix?.rows.forEach((row) => counts.set(row.allocation_status, (counts.get(row.allocation_status) ?? 0) + 1));
    return counts;
  }, [matrix]);

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
    setError(null);
    try {
      const saved = await postPortfolioRoleReview(runId, {
        fund_code: fundCode,
        role_code: "manual_portfolio_role",
        decision: "accept",
        target_bucket: targetBucket as "core" | "satellite" | "index_tool" | "exclude",
        max_weight_pct: 0,
        rationale: "portfolio workbench calibration",
        reviewer,
      });
      const nextDraft = await fetchPortfolioDraft(runId, draftMode);
      setReviews((current) => [saved, ...current.filter((item) => item.fund_code !== fundCode || item.role_code !== saved.role_code)]);
      setDraft(nextDraft);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingFund(null);
    }
  };

  const loadSuggestions = async () => {
    if (!runId) return;
    setLoadingSuggestions(true);
    setError(null);
    try {
      const payload: PortfolioRoleReviewSuggestions = await fetchPortfolioRoleReviewSuggestions(runId);
      setSuggestions(payload.suggestions || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const applyAllSuggestions = async () => {
    if (!runId || suggestions.length === 0) return;
    if (!reviewer.trim()) {
      setError("请输入复核人姓名后再一键采纳。");
      return;
    }
    setApplyingSuggestions(true);
    setError(null);
    try {
      const payload: ApplySuggestionsRequest = {
        reviewer,
        items: suggestions.map((s) => ({
          fund_code: s.fund_code,
          role_code: s.role_code,
          decision: s.decision,
          target_bucket: s.target_bucket as "core" | "satellite" | "index_tool" | "cash_buffer" | "exclude",
          max_weight_pct: s.recommended_max_weight_pct,
          rationale: s.rationale,
        })),
      };
      const result = await applyPortfolioRoleReviewSuggestions(runId, payload);
      setSuggestions([]);
      // 重新拉取 reviews 和 draft，让组合草案刷新
      const [nextReviews, nextDraft] = await Promise.all([
        fetchPortfolioRoleReviews(runId),
        fetchPortfolioDraft(runId, draftMode),
      ]);
      setReviews(nextReviews);
      setDraft(nextDraft);
      // 用 alert 提示成功消息
      alert(`已采纳 ${result.applied_count} 条建议`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setApplyingSuggestions(false);
    }
  };

  const clearReview = async (review: PortfolioRoleReview) => {
    if (!runId) return;
    setSavingFund(review.fund_code);
    setError(null);
    try {
      await deletePortfolioRoleReview(runId, review.fund_code, review.role_code);
      const nextDraft = await fetchPortfolioDraft(runId, draftMode);
      setReviews((current) => current.filter((item) => item.fund_code !== review.fund_code || item.role_code !== review.role_code));
      setDraft(nextDraft);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingFund(null);
    }
  };

  const totalFunds = matrix?.total_count ?? 0;
  const readyCount = eligibility?.ready_count ?? 0;
  const blockedCount = eligibility?.blocked_count ?? 0;
  const reviewRequiredCount = statusCounts.get("review_required") ?? 0;
  const acceptedCount = draftMode === "accepted" ? draft?.rows.length ?? 0 : reviews.length;
  const selectedName = selectedEligibility?.fund_name;
  const selectedTags = selectedMatrixRow ? rowTags(selectedMatrixRow) : [];
  const evidencePreview = selectedReport?.evidence.slice(0, 8) ?? [];
  const featurePreview = selectedReport?.features.slice(0, 8) ?? [];
  const currentRun = runs.find((run) => run.run_id === runId);

  return (
    <div className="executive-room">
      <div className="page-head-v2">
        <div>
          <span className="eyebrow">PORTFOLIO · 组合工作台</span>
          <h1>组合工作台</h1>
          <p>
            从风格标签到组合草案的完整生产线：研究员在此完成"基金地图 → 角色复核 → 草案生成 → 优化输出"。
          </p>
        </div>
        <div className="flow-steps" style={{ alignSelf: "flex-start" }}>
          <span className="flow-step is-done">
            <span className="step-num">1</span>总览
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step is-done">
            <span className="step-num">2</span>诊断
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step is-current">
            <span className="step-num">3</span>组合
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step">导出</span>
        </div>
      </div>
      <section className="executive-hero">
        <div className="hero-story">
          <p className="eyebrow">Executive overview</p>
          <h1>从标签引擎，到可审计的基金研究与组合工作台</h1>
          <p>
            这不是单点标签页面，而是一条完整生产线：批量计算基金标签，解释为什么命中，审计 Benchmark，筛出可展示池，交给研究员复核，最后形成核心、卫星、指数工具组合草案。
          </p>
          <div className="hero-actions">
            <a href="#fund-map">查看基金地图</a>
            {runId && <Link to={`/runs/${runId}`}>查看批次明细</Link>}
          </div>
        </div>
        <div className="run-control-tower">
          <span>当前演示批次</span>
          <strong>{runId ? `${runId.slice(0, 8)}…` : "待选择"}</strong>
          {currentRun && <small>{currentRun.run_at}</small>}
          <label>
            批次
            <select value={runId} onChange={(e) => setRunId(e.target.value)}>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>{run.run_id.slice(0, 8)}…</option>
              ))}
            </select>
          </label>
          <label>
            组合口径
            <select value={draftMode} onChange={(e) => setDraftMode(e.target.value as PortfolioDraftMode)}>
              <option value="research">研究草案</option>
              <option value="accepted">已验收组合</option>
            </select>
          </label>
        </div>
      </section>

      {error && <div className="error">{error}</div>}
      {loading && <p>加载中...</p>}

      <section className="board-metrics" aria-label="项目成果指标">
        <article>
          <span>已处理基金</span>
          <strong>{totalFunds}</strong>
          <p>从原始基金数据进入统一标签生产线。</p>
        </article>
        <article>
          <span>可展示池</span>
          <strong>{readyCount}</strong>
          <p>{blockedCount} 只基金仍有数据或基准门禁。</p>
        </article>
        <article>
          <span>组合草案</span>
          <strong>{draft?.rows.length ?? 0}</strong>
          <p>已映射到核心、卫星、指数工具等角色。</p>
        </article>
        <article>
          <span>人工签核</span>
          <strong>{acceptedCount}</strong>
          <p>{reviewRequiredCount} 只需要研究员继续复核。</p>
        </article>
      </section>

      <section className="strategy-panel">
        <div className="strategy-copy">
          <p className="eyebrow">What has been built</p>
          <h2>现在交付的是研究基础设施，不是一个标签小工具</h2>
          <p>
            高管最关心三件事：覆盖多少基金，结论能不能解释，能不能进入业务流程。这个页面把三件事合在一起展示。
          </p>
        </div>
        <div className="delivery-lanes">
          {DELIVERY_LANES.map((lane, index) => (
            <article key={lane.title}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h3>{lane.title}</h3>
              <p>{lane.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="operating-flow" aria-label="业务闭环">
        <div>
          <p className="eyebrow">Operating model</p>
          <h2>从数据到组合的闭环</h2>
        </div>
        <ol>
          {FLOW.map((item) => <li key={item}>{item}</li>)}
        </ol>
      </section>

      <section className="portfolio-snapshot">
        <div className="snapshot-copy">
          <p className="eyebrow">Portfolio layer</p>
          <h2>组合层已经能看出结构，而不只是散点标签</h2>
          <p>当前草案把基金放入角色桶，帮助投研团队讨论核心仓、卫星增强和指数工具的边界。</p>
        </div>
        <div className="bucket-stage">
          {[...bucketCounts.entries()].map(([bucket, count]) => {
            const weight = draft?.rows
              .filter((row) => row.bucket === bucket)
              .reduce((sum, row) => sum + row.draft_weight_pct, 0) ?? 0;
            return (
              <article key={bucket}>
                <span>{bucketLabel(bucket)}</span>
                <strong>{count} 只</strong>
                <small>{weight.toFixed(1)}% 草案权重</small>
              </article>
            );
          })}
          {bucketCounts.size === 0 && <p className="muted">暂无组合草案。</p>}
        </div>
      </section>

      <section className="fund-command" id="fund-map">
        <div className="fund-command-head">
          <div>
            <p className="eyebrow">Fund drilldown</p>
            <h2>基金地图：点一只基金，马上看到标签和证据</h2>
          </div>
          <div className="fund-filters">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索基金、名称、标签" />
            <select value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)}>
              <option value="all">全部</option>
              <option value="ready">可展示</option>
              <option value="blocked">暂不可展示</option>
              <option value="draft">已进草案</option>
              <option value="review">需复核</option>
            </select>
          </div>
        </div>

        <div className="fund-command-grid">
          <div className="fund-wall">
            {filteredRows.map((row) => {
              const ready = eligibilityByFund.get(row.fund_code);
              const draftRow = draftByFund.get(row.fund_code);
              const tags = rowTags(row).slice(0, 4);
              return (
                <button
                  key={row.fund_code}
                  className={`fund-tile ${selectedFund === row.fund_code ? "is-selected" : ""}`}
                  onClick={() => setSelectedFund(row.fund_code)}
                >
                  <span className="fund-tile-code">{row.fund_code}</span>
                  {ready?.fund_name && <span className="fund-tile-name">{ready.fund_name}</span>}
                  <span className={`badge ${badgeClass(ready?.relative_label_status)}`}>{readyLabel(ready?.relative_label_status)}</span>
                  <span className="mini-tags">{tags.map((tag) => <i key={tag}>{tagLabel(tag)}</i>)}</span>
                  {draftRow && <b>{bucketLabel(draftRow.bucket)}，{draftRow.draft_weight_pct.toFixed(1)}%</b>}
                </button>
              );
            })}
            {filteredRows.length === 0 && <p className="muted">没有命中的基金。</p>}
          </div>

          <aside className="fund-inspector">
            {!selectedFund && <p className="muted">选择一只基金查看详情。</p>}
            {selectedFund && (
              <>
                <div className="inspector-title">
                  <div>
                    <span>当前基金</span>
                    <h3>{selectedFund}</h3>
                    {selectedName && <p>{selectedName}</p>}
                  </div>
                  {selectedReport && <ReviewActionBadge value={selectedReport.review_action} />}
                </div>

                {reportError && <div className="error">{reportError}</div>}
                {reportLoading && <p>基金详情加载中...</p>}

                <div className="inspector-badges">
                  {selectedMatrixRow && <span className={`badge ${badgeClass(selectedMatrixRow.allocation_status)}`}>{statusLabel(selectedMatrixRow.allocation_status)}</span>}
                  <span className={`badge ${badgeClass(selectedEligibility?.relative_label_status)}`}>{readyLabel(selectedEligibility?.relative_label_status)}</span>
                  {selectedDraftRow && <span className="badge badge-active">{bucketLabel(selectedDraftRow.bucket)}</span>}
                </div>

                {selectedMatrixRow && (
                  <div className="executive-tags">
                    {selectedTags.slice(0, 12).map((tag) => <span key={tag}>{tagLabel(tag)}</span>)}
                  </div>
                )}

                <div className="inspector-stats">
                  <div><span>标签</span><strong>{selectedReport?.summary.label_count ?? "-"}</strong></div>
                  <div><span>证据</span><strong>{selectedReport?.summary.evidence_count ?? "-"}</strong></div>
                  <div><span>缺失</span><strong>{selectedReport?.summary.missing_field_count ?? "-"}</strong></div>
                </div>

                {selectedEligibility && !relativeReady && (
                  <div className="decision-warning">
                    <strong>暂不可展示原因</strong>
                    <p>{readableBlocker(selectedEligibility.blocking_components || selectedEligibility.blocking_reason)}</p>
                  </div>
                )}

                <div className="label-columns-exec">
                  {(["style", "relative", "observe"] as LabelTier[]).map((tier) => (
                    <section key={tier}>
                      <h4>{tierTitle(tier)}</h4>
                      {groupedLabels[tier].slice(0, 5).map((label) => {
                        const evidence = selectedReport ? evidenceForLabel(selectedReport, label.label_code) : [];
                        return (
                          <article key={label.label_code}>
                            <div><strong>{label.label_name}</strong><LabelStatusBadge value={label.status} /></div>
                            {evidence[0] && <p>{evidence[0].message}</p>}
                          </article>
                        );
                      })}
                      {groupedLabels[tier].length === 0 && <p className="muted">暂无</p>}
                    </section>
                  ))}
                </div>

                <div className="proof-and-data">
                  <section>
                    <h4>为什么这样打标签</h4>
                    {evidencePreview.map((item, index) => (
                      <article key={`${item.label_code}-${index}`}>
                        <strong>{item.message || item.label_code}</strong>
                        <small>{item.metric} = {item.value}，阈值 {item.threshold}</small>
                      </article>
                    ))}
                    {evidencePreview.length === 0 && <p className="muted">暂无证据。</p>}
                  </section>
                  <section>
                    <h4>关键数据</h4>
                    {featurePreview.map((feature) => (
                      <div key={feature.feature_code}>
                        <span>{featureLabel(feature.feature_code)}</span>
                        <strong>{displayValue(feature.value)}</strong>
                      </div>
                    ))}
                  </section>
                </div>

                <div className="review-strip">
                  <label>
                    复核人
                    <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
                  </label>
                  <label>
                    角色判断
                    <select
                      value={selectedReview?.target_bucket ?? ""}
                      onChange={(e) => saveReview(selectedFund, e.target.value)}
                      disabled={savingFund === selectedFund || !reviewer.trim()}
                    >
                      <option value="">待确认</option>
                      {REVIEW_DECISIONS.map((decision) => <option key={decision.value} value={decision.value}>{decision.label}</option>)}
                    </select>
                  </label>
                  {selectedReview && (
                    <>
                      <span className="manual-override-badge">人工覆盖：{bucketLabel(selectedReview.target_bucket)}</span>
                      <button className="secondary" onClick={() => clearReview(selectedReview)} disabled={savingFund === selectedFund}>撤销</button>
                    </>
                  )}
                </div>

                <section className="suggestions-block">
                  <div className="suggestions-header">
                    <h4>角色建议（批量）</h4>
                    <div>
                      <button
                        className="secondary"
                        onClick={loadSuggestions}
                        disabled={loadingSuggestions}
                      >
                        {loadingSuggestions ? "加载中..." : "生成建议"}
                      </button>
                      <button
                        onClick={applyAllSuggestions}
                        disabled={applyingSuggestions || suggestions.length === 0}
                        style={{ marginLeft: 8 }}
                      >
                        一键采纳 ({suggestions.length})
                      </button>
                    </div>
                  </div>
                  {suggestions.length > 0 && (
                    <ol className="suggestion-list">
                      {suggestions.slice(0, 10).map((s) => (
                        <li key={`${s.fund_code}-${s.role_code}`}>
                          <code>{s.fund_code}</code>
                          <span className="muted"> → {bucketLabel(s.target_bucket)} · 上限 {s.recommended_max_weight_pct.toFixed(1)}%</span>
                          <small>{s.rationale}</small>
                        </li>
                      ))}
                      {suggestions.length > 10 && (
                        <li className="muted">... 另 {suggestions.length - 10} 条</li>
                      )}
                    </ol>
                  )}
                  {suggestions.length === 0 && (
                    <p className="muted">点击"生成建议"获取需复核基金的角色推荐。</p>
                  )}
                </section>

                <Link className="full-report-link" to={`/runs/${runId}/funds/${selectedFund}`}>进入完整基金报告</Link>
              </>
            )}
          </aside>
        </div>
      </section>
    </div>
  );
}
