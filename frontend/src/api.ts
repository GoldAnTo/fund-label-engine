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
  reviews: Review[];
  calculations: Calculation[];
  summary: {
    label_count: number;
    feature_count: number;
    factor_exposure_count: number;
    evidence_count: number;
    missing_field_count: number;
    review_count: number;
    review_action: string;
  };
}

export interface SearchResult {
  fund_code: string;
  label_count: number;
  review_action: string;
  missing_field_count: number;
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
  status: "all" | "ready" | "blocked" = "all"
): Promise<RelativeEligibilityResponse> {
  return json(`/v1/runs/${runId}/relative-label-eligibility?status=${status}&limit=300`);
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
  max_weight_pct: number;
  score: number;
  portfolio_roles: string[];
  risk_tags: string[];
  manual_role_review?: string;
}

export interface PortfolioDraftResponse {
  run_id: string;
  run_at: string;
  rule_version: string;
  objective: string;
  config_version: string;
  rows: PortfolioDraftRow[];
  excluded: { fund_code: string; reasons: string[]; manual_role_review?: string }[];
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

export async function fetchPortfolioDraft(runId: string): Promise<PortfolioDraftResponse> {
  return json(`/v1/runs/${runId}/portfolio-draft`);
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
