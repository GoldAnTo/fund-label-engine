const BASE = import.meta.env.VITE_API_BASE ?? "";

async function json(url: string) {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function downloadFile(url: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const fileName = match ? match[1] : fallbackName;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

async function postJSON(url: string, body: unknown) {
  const res = await fetch(`${BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function deleteJSON(url: string) {
  const res = await fetch(`${BASE}${url}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface Run {
  run_id: string;
  run_at: string;
  data_as_of: string | null;
  rule_version: string;
  status: string;
}

export interface RunFailure {
  fund_code: string;
  stage: string;
  error_type: string;
  message: string;
  recorded_at: string;
}

export interface RunDetail extends Run {
  fund_codes: string[];
  failures: RunFailure[];
  failure_count: number;
  rule_snapshot: Record<string, number | string> | null;
}

export interface FundLabel {
  label_code: string;
  label_name: string;
  category: string;
  confidence: number;
  status: string;
}

export interface Evidence {
  label_code: string;
  metric: string;
  value: string;
  threshold: string;
  source: string;
  message: string;
}

export interface FeatureValue {
  feature_code: string;
  value: string;
  source: string;
}

export interface FactorExposure {
  fund_code: string;
  report_date: string;
  factor_code: string;
  exposure_value: number;
  coverage_weight: number;
  holding_total_weight: number;
  stock_count: number;
  covered_stock_count: number;
  source: string;
  as_of_date: string;
  computed_at: string;
}

export interface EquityStyleContribution {
  fund_code: string;
  report_date: string;
  stock_code: string;
  stock_name: string | null;
  weight: number;
  style_code: string;
  style_name: string;
  matched: number;
  contribution_weight: number;
  factor_values_json: string;
  rule_snapshot_json: string;
  factor_as_of_date: string;
  source: string;
  computed_at: string;
}

export interface Review {
  review_id: string;
  run_id: string;
  fund_code: string;
  label_code: string;
  decision: string;
  reviewer: string;
  comment: string;
}

export interface Calculation {
  label_code: string;
  label_name: string;
  category: string;
  state: string;
  reason_code: string;
  observed: string | number | null;
  threshold: string | number | null;
  source: string;
  message: string;
}

export interface FundReport {
  run_id: string;
  fund_code: string;
  review_action: string;
  coverage: Record<string, boolean>;
  missing_fields: string[];
  labels: FundLabel[];
  evidence: Evidence[];
  features: FeatureValue[];
  factor_exposures: FactorExposure[];
  equity_style_contributions?: EquityStyleContribution[];
  reviews: Review[];
  calculations: Calculation[];
  style_history?: StyleHistory;
  summary: {
    label_count: number;
    feature_count: number;
    factor_exposure_count: number;
    evidence_count: number;
    missing_field_count: number;
    review_count: number;
    review_action: string;
    equity_style_contribution_count?: number;
    style_stable_run_count?: number;
    style_drift_run_count?: number;
    style_recent_shift_run_count?: number;
  };
}

export interface StyleHistoryEntry {
  run_id: string;
  run_at: string;
  data_as_of: string;
  rule_version: string;
  labels: string[];
  summary: "stable" | "drift" | "recent_shift" | "none";
}

export interface StyleHistory {
  fund_code: string;
  timeline: StyleHistoryEntry[];
  current: StyleHistoryEntry | null;
  trend: "stable" | "drifting" | "shifting" | "insufficient_data";
  stable_run_count: number;
  drift_run_count: number;
  shift_run_count: number;
}

export interface SearchResult {
  fund_code: string;
  label_count: number;
  review_action: string;
  missing_field_count: number;
}

export interface PercentileRank {
  label_code: string;
  metric_code: string;
  metric_value: number | null;
  percentile: number;
  rank_value: number;
  peer_count: number;
  direction: "higher_better" | "lower_better";
}

export interface FundPercentileResponse {
  run_id: string;
  fund_code: string;
  label_code: string | null;
  ranks: PercentileRank[];
}

export interface TopFundEntry {
  fund_code: string;
  metric_value: number | null;
  percentile: number;
  rank_value: number;
  peer_count: number;
}

export interface TopFundsResponse {
  run_id: string;
  label_code: string;
  metric_code: string;
  results: TopFundEntry[];
}

export interface SearchResponse {
  run_id: string;
  filters: {
    fund_code: string | null;
    label_code: string | null;
    review_action: string | null;
    group_code: string | null;
    group_type: string | null;
    classification_code: string | null;
  };
  available_labels: string[];
  available_groups: string[];
  available_group_types: string[];
  available_classifications: string[];
  results: SearchResult[];
}

export async function fetchRuns(): Promise<Run[]> {
  const data: { runs: Run[] } = await json("/v1/runs");
  return data.runs;
}

export async function fetchRun(runId: string): Promise<RunDetail> {
  return json(`/v1/runs/${runId}`);
}

export async function fetchFundReport(runId: string, fundCode: string): Promise<FundReport> {
  return json(`/v1/runs/${runId}/funds/${fundCode}/report`);
}

export async function fetchStyleHistory(
  runId: string,
  fundCode: string,
  limit: number = 12
): Promise<StyleHistory & { run_id: string }> {
  return json(
    `/v1/runs/${runId}/funds/${fundCode}/style-history?limit=${limit}`
  );
}

export interface BenchmarkComponent {
  component_order: number;
  component_code: string | null;
  component_name: string;
  weight: number | null;
  source_text: string;
  status: string;
  reason: string;
  has_returns: boolean;
}

export interface BenchmarkComponents {
  run_id: string;
  fund_code: string;
  components: BenchmarkComponent[];
  benchmark_returns_count: number;
  has_benchmark_returns: boolean;
  unresolved_count: number;
  unresolved_unresolved_count?: number;
  unresolved_missing_returns_count?: number;
  coverage_pct?: number;
  coverage_basis?: string;
}

export interface RelativeEligibilityRow {
  fund_code: string;
  fund_name: string;
  benchmark_source_status: string;
  nav_sample_count: number;
  benchmark_sample_count: number;
  return_window_status: string;
  relative_label_status: string;
  blocking_reason: string;
  blocking_components: string;
}

export interface RelativeBlockerGroup {
  key: string;
  status: string;
  component: string;
  count: number;
  sample_fund_codes: string[];
}

export interface RelativeEligibilityResponse {
  run_id: string;
  total_funds: number;
  ready_count: number;
  ready_exact_count?: number;
  ready_approx_count?: number;
  blocked_count: number;
  status_counts: Record<string, number>;
  benchmark_source_counts: Record<string, number>;
  blocker_groups: RelativeBlockerGroup[];
  filters: {
    status: "all" | "ready" | "blocked";
    limit: number;
  };
  results: RelativeEligibilityRow[];
}

export async function fetchRelativeEligibility(
  runId: string,
  status: "all" | "ready" | "blocked" = "all",
  fundCode?: string
): Promise<RelativeEligibilityResponse> {
  const params = new URLSearchParams({ status, limit: "300" });
  if (fundCode) params.set("fund_code", fundCode);
  return json(`/v1/runs/${runId}/relative-label-eligibility?${params}`);
}

export async function fetchFundPercentile(
  runId: string,
  fundCode: string,
  labelCode?: string
): Promise<FundPercentileResponse> {
  const q = labelCode ? `?label_code=${encodeURIComponent(labelCode)}` : "";
  return json(`/v1/runs/${runId}/funds/${fundCode}/percentile${q}`);
}

export async function fetchTopFunds(
  runId: string,
  labelCode: string,
  metricCode: string = "annualized_return_1y",
  limit: number = 5
): Promise<TopFundsResponse> {
  return json(
    `/v1/runs/${runId}/top-funds?label_code=${encodeURIComponent(labelCode)}&metric_code=${metricCode}&limit=${limit}`
  );
}

// ---------- 竞品横评 ----------

export interface CompareFundLabelsEntry {
  label_code: string;
  label_name: string;
  status: string;
  category: string;
}

export interface CompareFactorExposure {
  factor_code: string;
  exposure_value: number;
  [key: string]: unknown;
}

export interface CompareFundEntry {
  fund_code: string;
  labels: CompareFundLabelsEntry[];
  factor_exposures: CompareFactorExposure[];
  metrics: Record<string, number>;
  percentiles: Record<string, { percentile: number; rank_value: number; peer_count: number }>;
  not_found?: boolean;
}

export interface CompareMetricDef {
  metric_code: string;
  name: string;
  direction: "higher_better" | "lower_better";
}

export interface CompareResponse {
  run_id: string;
  funds: CompareFundEntry[];
  metric_defs: CompareMetricDef[];
}

export interface PairwiseOverlap {
  overlap_weight: number;
  overlap_count: number;
}

export interface CommonHolding {
  stock_code: string;
  stock_name: string;
  weights: Record<string, number>;
}

export interface HoldingsOverlapResponse {
  fund_codes: string[];
  pairwise_overlap: Record<string, PairwiseOverlap>;
  common_holdings: CommonHolding[];
  error?: string;
}

export async function fetchCompare(
  runId: string,
  fundCodes: string[]
): Promise<CompareResponse> {
  const funds = fundCodes.join(",");
  return json(`/v1/runs/${runId}/compare?funds=${encodeURIComponent(funds)}`);
}

export async function fetchHoldingsOverlap(
  fundCodes: string[],
  topN: number = 10
): Promise<HoldingsOverlapResponse> {
  const funds = fundCodes.join(",");
  return json(`/v1/holdings-overlap?funds=${encodeURIComponent(funds)}&top_n=${topN}`);
}

export interface CorrelationPair {
  fund_a: string;
  fund_b: string;
  correlation: number;
  level: "very_high" | "high" | "moderate" | "low";
}

export interface CorrelationResponse {
  fund_codes: string[];
  matrix: number[][];
  sample_count: number;
  pairs: CorrelationPair[];
  error?: string;
}

export async function fetchCorrelation(
  fundCodes: string[]
): Promise<CorrelationResponse> {
  const funds = fundCodes.join(",");
  return json(`/v1/correlation?funds=${encodeURIComponent(funds)}`);
}

export interface PortfolioRiskResponse {
  fund_codes: string[];
  weights: number[];
  raw_weights: number[];
  sample_count: number;
  fund_volatilities: number[];
  fund_returns: number[];
  portfolio_volatility: number;
  portfolio_return: number;
  portfolio_sharpe: number;
  weighted_avg_volatility: number;
  diversification_ratio: number;
  risk_reduction: number;
  error?: string;
}

export async function fetchPortfolioRisk(
  fundCodes: string[],
  weights: number[]
): Promise<PortfolioRiskResponse> {
  const funds = fundCodes.join(",");
  const w = weights.join(",");
  return json(`/v1/portfolio-risk?funds=${encodeURIComponent(funds)}&weights=${encodeURIComponent(w)}`);
}

export interface WorkbenchTask {
  task_id: string;
  task_type: "benchmark_gap" | "manual_review" | "observe_signal" | "calibration_signal" | string;
  priority: "high" | "medium" | "low" | string;
  fund_code: string | null;
  fund_name: string | null;
  label_code: string | null;
  label_name: string | null;
  reason_code: string;
  reason_text: string;
  suggested_action: string;
}

export interface WorkbenchTasksResponse {
  run_id: string;
  total_count: number;
  task_type_counts: Record<string, number>;
  results: WorkbenchTask[];
}

export interface WorkbenchSummary {
  run_id: string;
  run_at: string;
  rule_version: string;
  status: string;
  total_funds: number;
  ready_count: number;
  blocked_count: number;
  manual_review_count: number;
  task_type_counts: Record<string, number>;
  blocker_groups: RelativeBlockerGroup[];
  group_distribution: { group_type: string; group_code: string; group_name: string; fund_count: number }[];
  classification_distribution: { dimension: string; classification_code: string; classification_name: string; fund_count: number }[];
}

// ===================================================================
// 数据质量巡检
// ===================================================================

export interface DataQualityOverview {
  total_funds: number;
  nav_covered_funds: number;
  nav_missing_funds: number;
  holding_covered_funds: number;
  holding_missing_funds: number;
  latest_nav_date: string | null;
  latest_holding_period: string | null;
  factor_stock_count: number;
  latest_factor_as_of: string | null;
  benchmark_resolved_funds: number;
  benchmark_total_funds: number;
}

export interface DataQualityFinding {
  severity: "critical" | "warning" | "info" | string;
  category: string;
  title: string;
  detail: string;
  count: number;
  samples: string[];
}

export interface DataQualityReport {
  inspected_at: string;
  overview: DataQualityOverview;
  summary: Record<string, number>;
  findings: DataQualityFinding[];
  run_id?: string;
  run_coverage?: unknown;
}

export async function fetchDataQuality(): Promise<DataQualityReport> {
  return json("/v1/data-quality");
}

export async function fetchRunDataQuality(runId: string): Promise<DataQualityReport> {
  return json(`/v1/runs/${runId}/data-quality`);
}

export async function fetchWorkbenchTasks(runId: string): Promise<WorkbenchTasksResponse> {
  return json(`/v1/runs/${runId}/workbench-tasks?limit=500`);
}

export async function fetchWorkbenchSummary(runId: string): Promise<WorkbenchSummary> {
  return json(`/v1/runs/${runId}/workbench-summary`);
}

export async function fetchBenchmarkComponents(
  runId: string,
  fundCode: string
): Promise<BenchmarkComponents> {
  return json(`/v1/runs/${runId}/funds/${fundCode}/benchmark-components`);
}

export async function searchFunds(
  runId: string,
  params: {
    fund_code?: string;
    label_code?: string;
    review_action?: string;
    group_code?: string;
    group_type?: string;
    classification_code?: string;
  }
): Promise<SearchResponse> {
  const qs = new URLSearchParams();
  if (params.fund_code) qs.set("fund_code", params.fund_code);
  if (params.label_code) qs.set("label_code", params.label_code);
  if (params.review_action) qs.set("review_action", params.review_action);
  if (params.group_code) qs.set("group_code", params.group_code);
  if (params.group_type) qs.set("group_type", params.group_type);
  if (params.classification_code) qs.set("classification_code", params.classification_code);
  const q = qs.toString();
  return json(`/v1/runs/${runId}/search${q ? "?" + q : ""}`);
}

export async function fetchReviewQueue(runId: string): Promise<SearchResponse> {
  return json(`/v1/runs/${runId}/review-queue`);
}

export interface PortfolioMatrixRow {
  fund_code: string;
  allocation_status: string;
  portfolio_roles: string[];
  style_tags: string[];
  return_tags: string[];
  risk_tags: string[];
  data_tags: string[];
  blocking_reasons: string[];
  watch_reasons: string[];
  features: Record<string, number | string | null>;
  benchmark_precision?: "exact" | "approx" | "none";
}

export interface PortfolioMatrixResponse {
  run_id: string;
  run_at: string;
  rule_version: string;
  status: string;
  total_count: number;
  rows: PortfolioMatrixRow[];
}

export interface PortfolioDraftRow {
  fund_code: string;
  bucket: "core" | "satellite" | "index_tool" | string;
  draft_weight_pct: number;
  optimized_weight_pct?: number;
  optimized_status?: "ok" | "capped" | string;
  optimization_method?: string;
  max_weight_pct: number;
  score: number;
  portfolio_roles: string[];
  risk_tags: string[];
  manual_role_review?: string;
}

export interface PortfolioOptimizationSummary {
  total_weight_pct: number;
  optimized_funds: number;
  capped_count: number;
  method: string;
}

export type PortfolioDraftMode = "research" | "accepted";

export interface PortfolioDraftResponse {
  run_id: string;
  run_at: string;
  rule_version: string;
  objective: string;
  config_version: string;
  mode: PortfolioDraftMode;
  rows: PortfolioDraftRow[];
  excluded: { fund_code: string; reasons: string[]; manual_role_review?: string }[];
  optimization_summary?: PortfolioOptimizationSummary;
}

export interface PortfolioRoleReview {
  run_id: string;
  fund_code: string;
  role_code: string;
  decision: "accept" | "reject" | "needs_more_data" | string;
  target_bucket: "core" | "satellite" | "index_tool" | "cash_buffer" | "exclude" | string;
  max_weight_pct: number;
  rationale: string;
  reviewer: string;
  reviewed_at: string;
}

export interface PortfolioRoleReviewPayload {
  fund_code: string;
  role_code: string;
  decision: "accept" | "reject" | "needs_more_data";
  target_bucket: "core" | "satellite" | "index_tool" | "cash_buffer" | "exclude";
  max_weight_pct?: number;
  rationale?: string;
  reviewer?: string;
}

export async function fetchPortfolioMatrix(runId: string): Promise<PortfolioMatrixResponse> {
  return json(`/v1/runs/${runId}/portfolio-matrix`);
}

export async function fetchPortfolioDraft(runId: string, mode: PortfolioDraftMode = "research"): Promise<PortfolioDraftResponse> {
  return json(`/v1/runs/${runId}/portfolio-draft?mode=${mode}`);
}

export async function fetchPortfolioRoleReviews(runId: string): Promise<PortfolioRoleReview[]> {
  const data: { reviews: PortfolioRoleReview[] } = await json(`/v1/runs/${runId}/portfolio-role-reviews`);
  return data.reviews;
}

export async function postPortfolioRoleReview(
  runId: string,
  payload: PortfolioRoleReviewPayload
): Promise<PortfolioRoleReview> {
  return postJSON(`/v1/runs/${runId}/portfolio-role-reviews`, payload);
}

export async function deletePortfolioRoleReview(
  runId: string,
  fundCode: string,
  roleCode: string
): Promise<{ deleted: boolean }> {
  return deleteJSON(
    `/v1/runs/${runId}/portfolio-role-reviews/${encodeURIComponent(fundCode)}/${encodeURIComponent(roleCode)}`
  );
}

export interface RunSummary {
  run_id: string;
  run_at: string;
  rule_version: string;
  status: string;
  counts: {
    processed: number;
    failed: number;
    data_insufficient: number;
    manual_review: number;
    return_window_insufficient: number;
  };
  label_distribution: {
    label_code: string;
    label_name: string;
    category: string;
    fund_count: number;
  }[];
  review_action_distribution: {
    review_action: string;
    fund_count: number;
  }[];
  category_distribution: { category: string; label_count: number }[];
}

export async function fetchRunSummary(runId: string): Promise<RunSummary> {
  return json(`/v1/runs/${runId}/summary`);
}

export interface RunStyleSummary {
  run_id: string;
  run_at: string;
  rule_version: string;
  styles: Record<
    "deep_value" | "quality_growth" | "dividend_steady",
    { count: number; funds: string[] }
  >;
  boundary_counts: {
    stock_factors_missing: number;
    style_pending_rule_definition: number;
  };
}

export async function fetchRunStyle(runId: string): Promise<RunStyleSummary> {
  return json(`/v1/runs/${runId}/style`);
}

export interface RunDiffLabelRow {
  label_code: string;
  label_name: string;
  category: string;
  added_funds: string[];
  removed_funds: string[];
  delta: number;
}

export interface RunDiffFundRow {
  fund_code: string;
  added_labels: string[];
  removed_labels: string[];
}

export interface RunDiff {
  base_run_id: string;
  target_run_id: string;
  totals: {
    base_fund_count: number;
    target_fund_count: number;
    common_fund_count: number;
    only_in_base_count: number;
    only_in_target_count: number;
    added_pair_count: number;
    removed_pair_count: number;
    changed_fund_count: number;
  };
  summary_by_label: RunDiffLabelRow[];
  details_by_fund: RunDiffFundRow[];
  only_in_base: string[];
  only_in_target: string[];
}

export async function fetchRunDiff(base: string, target: string): Promise<RunDiff> {
  return json(`/v1/runs/diff?base=${encodeURIComponent(base)}&target=${encodeURIComponent(target)}`);
}

export interface TriggerRunResponse {
  run_id: string;
  processed: number;
  status: string;
  source: string;
  rule_version: string;
}

export async function triggerRun(
  source: "auto" | "engine" | "funddata" = "auto"
): Promise<TriggerRunResponse> {
  return postJSON(`/v1/runs`, { source });
}

export async function postReview(
  runId: string,
  fundCode: string,
  labelCode: string,
  decision: string,
  reviewer: string,
  comment: string
): Promise<unknown> {
  return postJSON(`/v1/runs/${runId}/funds/${fundCode}/labels/${labelCode}/reviews`, {
    decision,
    reviewer,
    comment,
  });
}

// ===================================================================
// 标签变化检测
// ===================================================================
export interface LabelChange {
  run_id: string;
  previous_run_id: string;
  fund_code: string;
  label_code: string;
  change_type: "added" | "removed" | "status_changed";
  previous_status: string | null;
  current_status: string | null;
  is_risk_warning: number;
  detected_at: string;
}

export interface LabelChangeSummary {
  total: number;
  risk_warnings: number;
  by_type: Record<string, number>;
}

export interface LabelChangesResponse {
  run_id: string;
  summary: LabelChangeSummary;
  count: number;
  changes: LabelChange[];
}

export async function fetchLabelChanges(
  runId: string,
  opts?: { riskWarningsOnly?: boolean; fundCode?: string }
): Promise<LabelChangesResponse> {
  const params = new URLSearchParams();
  if (opts?.riskWarningsOnly) params.set("risk_warnings_only", "true");
  if (opts?.fundCode) params.set("fund_code", opts.fundCode);
  const qs = params.toString();
  return json(`/v1/runs/${runId}/label-changes${qs ? `?${qs}` : ""}`);
}

// ===================================================================
// 覆盖率报告
// ===================================================================
export interface CoverageFieldStat {
  field: string;
  pass_count: number;
  fail_count: number;
  total: number;
  pass_rate: number;
}

export interface CoverageByFundType {
  fund_type: string;
  fields: CoverageFieldStat[];
  review_action_counts: Record<string, number>;
}

export interface CoverageRejectionReason {
  field: string;
  reason: string;
  fund_count: number;
}

export interface CoverageReport {
  run_id: string;
  run_at: string;
  rule_version: string;
  status: string;
  total_funds: number;
  by_fund_type: CoverageByFundType[];
  rejection_reasons_top: CoverageRejectionReason[];
}

export async function fetchCoverageReport(runId: string): Promise<CoverageReport> {
  return json(`/v1/runs/${runId}/coverage`);
}

// ===================================================================
// 标签定义和规则版本
// ===================================================================
export interface LabelDefinition {
  label_code: string;
  label_name: string;
  category: string;
  fund_types: string;
  rule_version: string;
  enabled: number;
  description: string;
  thresholds: Record<string, unknown> | null;
}

export async function fetchLabelDefinitions(
  ruleVersion?: string
): Promise<LabelDefinition[]> {
  const qs = ruleVersion ? `?rule_version=${encodeURIComponent(ruleVersion)}` : "";
  return json(`/v1/label-definitions${qs}`);
}

export interface RuleVersionInfo {
  rule_version: string;
  run_count: number;
  last_run_at: string;
}

export async function fetchRuleVersions(): Promise<RuleVersionInfo[]> {
  return json(`/v1/rule-versions`);
}

// ===================================================================
// 组合角色建议 + 一键应用
// ===================================================================
export interface RoleReviewSuggestion {
  fund_code: string;
  role_code: string;
  decision: string;
  target_bucket: string;
  recommended_max_weight_pct: number;
  rationale: string;
}

export interface PortfolioRoleReviewSuggestions {
  run_id: string;
  suggestions: RoleReviewSuggestion[];
}

export async function fetchPortfolioRoleReviewSuggestions(
  runId: string
): Promise<PortfolioRoleReviewSuggestions> {
  return json(`/v1/runs/${runId}/portfolio-role-reviews/suggest`);
}

export interface ApplySuggestionsItem {
  fund_code: string;
  role_code: string;
  decision: string;
  target_bucket: string;
  max_weight_pct: number;
  rationale: string;
}

export interface ApplySuggestionsRequest {
  reviewer: string;
  items: ApplySuggestionsItem[];
}

export interface ApplySuggestionsResponse {
  run_id: string;
  applied_count: number;
  applied_funds: string[];
}

export async function applyPortfolioRoleReviewSuggestions(
  runId: string,
  payload: ApplySuggestionsRequest
): Promise<ApplySuggestionsResponse> {
  return postJSON(
    `/v1/runs/${runId}/portfolio-role-reviews/apply-suggestions`,
    payload as unknown as Record<string, unknown>
  );
}

// ===================================================================
// 认知引擎
// ===================================================================
export interface ThemeInfo {
  key: string;
  name: string;
  belief: string;
  logic_chain: string[];
  chain_links: string[];
  defense_theme: string | null;
}

// === 认知引擎（5步推导） ===
export interface ChainLink {
  link_name: string;
  pe: number | null;
  growth_pct: number | null;
  peg: number | null;
  val_pct: number | null;
  roe: number | null;
  dividend_yield: number | null;
  expectation_gap: string;  // positive/neutral/negative/unknown
  gap_reason: string;
  score: number;
  certainty: string;
  elasticity: string;
  matched_weight: number;
  matched_stocks: string[];
  benefit_logic: string;
}

export interface Evidence {
  claim: string;
  source: string;
  source_type: "chain_analysis" | "market_data" | "estimate" | "trend";
  raw_data?: Record<string, unknown>;
  context?: string;
}

export interface ReasoningChainNode {
  step: string;
  description: string;
  evidence_ref: string;
}

export interface CognitionValidation {
  supporting_evidence: Evidence[];
  opposing_evidence: Evidence[];
  warnings: Evidence[];
  verdict: string;
  verdict_detail: string;
  evidence_counts: { supporting: number; opposing: number };
  reasoning_chain: ReasoningChainNode[];
  debate?: DebateRound[];
  cognition_feedback?: CognitionFeedback;
}

export interface DebateRound {
  round: number;
  bull_argument: Evidence;
  bear_rebuttal: Evidence | null;
  bull_response: Evidence | null;
}

export interface CognitionFeedback {
  original_belief: string;
  validation_verdict: string;
  correction_suggestions: string[];
  adjusted_belief: string;
}

export interface GateResult {
  passed: boolean;
  violations: string[];
}

export interface FundManager {
  name: string;
  tenure_days: number | null;
  return_pct: number | null;
  is_current: number;
}

export interface GatedOutFund {
  fund_code: string;
  fund_name: string;
  match_pct: number;
  gate: GateResult;
}

export interface OverlapAnalysis {
  max_overlap_pct: number;
  high_overlap_pairs: Array<[string, string]>;
}

export interface CognitionResponse {
  direction: string;
  available_links: string[];
  belief_link: string | null;
  conviction: string;
  step1_judgment: {
    direction: string;
    belief: string;
    level: string;
    time_horizon: string;
    valuation_tolerance: string;
    key_metric: string;
    hard_limits?: Record<string, number>;
  };
  step2_chain: ChainLink[];
  step3_expectation_gap: {
    positive: ChainLink[];
    neutral: ChainLink[];
    negative: ChainLink[];
    best_link: ChainLink | null;
    summary: string;
  };
  step4_fund_matches: Array<{
    fund_code: string;
    fund_name: string;
    match_pct: number;
    chain_breakdown: Record<string, number>;
    valuation: Record<string, unknown>;
    trend: {
      trend: string;
      diff: number;
      periods: Array<{ period: string; weight: number }>;
    };
    gate?: GateResult;
    manager?: FundManager;
    holdings?: Array<{
      stock_code: string;
      stock_name: string;
      weight: number;
    }>;
  }>;
  gated_out_funds?: GatedOutFund[];
  step5_validation?: CognitionValidation;
  step5_portfolio: {
    role: string;
    suggested_weight: number;
    weight_range: [number, number];
    defense_weight: number;
    cash_pct: number;
    total_invested?: number;
    top_funds: Array<Record<string, unknown>>;
    defense_fund: Record<string, unknown> | null;
    rationale: string;
    overlap_analysis?: OverlapAnalysis;
    metrics?: PortfolioMetrics;
  };
}

export interface PortfolioMetrics {
  portfolio_pe: number | null;
  portfolio_volatility: number | null;
  portfolio_max_drawdown: number | null;
  holdings_penetration: Array<{
    stock_code: string;
    stock_name: string;
    weight: number;
    industry_name: string;
    sector_group: string;
    pe?: number | null;
    roe?: number | null;
  }>;
  industry_exposure: Array<{ name: string; weight: number }>;
  sector_exposure: Array<{ name: string; weight: number }>;
}

export async function fetchThemes(): Promise<{ themes: ThemeInfo[] }> {
  return json("/v1/themes");
}

// 产业链环节信息（选环节阶段展示用）
export interface ChainLinkInfo {
  name: string;
  stocks: string[];
  benefit_logic: string;
  certainty: string;
  elasticity: string;
}

export interface DirectionLinksResponse {
  direction: string;
  links: ChainLinkInfo[];
  is_custom: boolean;
}

export async function fetchDirectionLinks(direction: string): Promise<DirectionLinksResponse> {
  return json(`/v1/cognition/${encodeURIComponent(direction)}/links`);
}

export async function postCognition(
  direction: string,
  beliefLink?: string,
  conviction?: string,
): Promise<CognitionResponse> {
  return postJSON("/v1/cognition", {
    theme_key: direction,
    belief_link: beliefLink ?? null,
    conviction: conviction ?? "medium",
  });
}

// === 概念板块搜索 ===

export interface ConceptBoard {
  code: string;
  name: string;
  stock_count: number;
}

export async function searchConcepts(keyword: string): Promise<ConceptBoard[]> {
  const r = await json(
    `/v1/concepts/search?keyword=${encodeURIComponent(keyword)}`,
  ) as { concepts: ConceptBoard[] };
  return r.concepts;
}

export async function postConceptCognition(
  conceptCode: string,
  conceptName: string,
  conviction?: string,
): Promise<CognitionResponse> {
  return postJSON("/v1/cognition/concept", {
    concept_code: conceptCode,
    concept_name: conceptName,
    conviction: conviction ?? "medium",
  });
}

// === 个股认知 ===

export interface StockSearchResult {
  stock_code: string;
  stock_name: string;
  industry_name: string;
  sector_group: string;
  fund_count: number;
  pe: number | null;
  roe: number | null;
  val_pct: number | null;
}

export async function searchStocks(keyword: string): Promise<StockSearchResult[]> {
  const r = await json(
    `/v1/stocks/search?keyword=${encodeURIComponent(keyword)}`,
  ) as { stocks: StockSearchResult[] };
  return r.stocks;
}

export async function postStockCognition(
  stockCode: string,
  stockName?: string,
  conviction?: string,
): Promise<CognitionResponse & { stock_info?: Record<string, unknown>; valuation_assessment?: string }> {
  return postJSON("/v1/cognition/stock", {
    stock_code: stockCode,
    stock_name: stockName ?? null,
    conviction: conviction ?? "medium",
  });
}

// === 多认知组合 ===

export interface MultiCognitionItem {
  direction: string;
  belief_link?: string | null;
  conviction?: string;
  weight_pct: number;
}

export async function postMultiCognition(
  items: MultiCognitionItem[],
  riskTolerance?: string,
): Promise<{ cognition_count: number; cognitions: unknown[]; combined_portfolio: unknown }> {
  return postJSON("/v1/cognition/multi", {
    items,
    risk_tolerance: riskTolerance ?? "moderate",
  });
}

// === 认知结果导出 ===

export async function exportCognition(result: unknown, format: "csv" | "xlsx" = "xlsx"): Promise<void> {
  const res = await fetch(`${BASE}/v1/cognition/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result, format }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const fileName = match ? match[1] : "cognition_result.xlsx";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}
