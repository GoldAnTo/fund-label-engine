import { expect, test } from "@playwright/test";

const runId = "run-ready-pool";

const runsPayload = {
  runs: [
    {
      run_id: runId,
      run_at: "2026-07-06T05:46:30Z",
      rule_version: "v1",
      status: "succeeded",
    },
  ],
};

const summaryPayload = {
  run_id: runId,
  run_at: "2026-07-06T05:46:30Z",
  rule_version: "v1",
  status: "succeeded",
  counts: {},
  label_distribution: [],
  review_action_distribution: [],
  category_distribution: [],
  calculation_state_distribution: [],
};

const matrixPayload = {
  run_id: runId,
  run_at: "2026-07-06T05:46:30Z",
  rule_version: "v1",
  status: "succeeded",
  total_count: 2,
  rows: [
    {
      fund_code: "000892",
      allocation_status: "eligible",
      portfolio_roles: [],
      style_tags: [],
      return_tags: [],
      risk_tags: [],
      data_tags: [],
      blocking_reasons: [],
      watch_reasons: [],
      features: {},
    },
    {
      fund_code: "000688",
      allocation_status: "review_required",
      portfolio_roles: [],
      style_tags: [],
      return_tags: [],
      risk_tags: [],
      data_tags: [],
      blocking_reasons: [],
      watch_reasons: ["nav_window_insufficient"],
      features: {},
    },
  ],
};

const eligibilityPayload = {
  run_id: runId,
  total_funds: 142,
  ready_count: 5,
  ready_approx_count: 0,
  blocked_count: 137,
  status_counts: {
    nav_window_insufficient: 137,
    relative_label_ready: 5,
  },
  benchmark_source_counts: { ready: 142 },
  blocker_groups: [
    {
      key: "nav_window_insufficient|nav_sample_count=21<180",
      status: "nav_window_insufficient",
      component: "nav_sample_count=21<180",
      count: 128,
      sample_fund_codes: ["000688", "000689", "000690"],
    },
  ],
  filters: { status: "all", limit: 300 },
  results: [
    {
      fund_code: "000892",
      fund_name: "九泰天宝灵活配置混合A",
      benchmark_source_status: "ready",
      nav_sample_count: 2628,
      benchmark_sample_count: 2753,
      return_window_status: "ready",
      relative_label_status: "relative_label_ready",
      blocking_reason: "",
      blocking_components: "",
    },
    {
      fund_code: "000688",
      fund_name: "景顺长城研究精选股票A",
      benchmark_source_status: "ready",
      nav_sample_count: 21,
      benchmark_sample_count: 2753,
      return_window_status: "nav_window_insufficient",
      relative_label_status: "nav_window_insufficient",
      blocking_reason: "nav_sample_count=21<180",
      blocking_components: "",
    },
  ],
};

test("ready pool summary uses the actual dominant blocker", async ({ page }) => {
  await page.route("**/v1/runs", (route) => route.fulfill({ json: runsPayload }));
  await page.route(`**/v1/runs/${runId}/summary`, (route) =>
    route.fulfill({ json: summaryPayload })
  );
  await page.route(`**/v1/runs/${runId}/portfolio-matrix`, (route) =>
    route.fulfill({ json: matrixPayload })
  );
  await page.route(`**/v1/runs/${runId}/relative-label-eligibility**`, (route) =>
    route.fulfill({ json: eligibilityPayload })
  );
  await page.route(`**/v1/runs/${runId}/top-funds**`, (route) =>
    route.fulfill({
      json: {
        run_id: runId,
        label_code: "quality_growth",
        metric_code: "annualized_return_1y",
        results: [],
      },
    })
  );

  await page.goto("/ready-pool");

  await expect(page.getByText(/主要原因是/)).toContainText("收益窗口不足");
  await expect(page.getByText(/主要原因是/)).not.toContainText("缺基准源 / 需确认映射");
});
