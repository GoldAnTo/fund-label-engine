import { expect, test } from "@playwright/test";

const runId = "run-e2e";

const matrixPayload = {
  run_id: runId,
  run_at: "2026-07-02T00:00:00Z",
  rule_version: "v1",
  status: "succeeded",
  total_count: 1,
  rows: [
    {
      fund_code: "000001",
      allocation_status: "eligible",
      portfolio_roles: ["active_equity_candidate", "satellite_alpha"],
      style_tags: ["style_quality_growth"],
      return_tags: ["alpha_positive"],
      risk_tags: [],
      data_tags: ["data_sufficient"],
      blocking_reasons: [],
      watch_reasons: [],
      features: {},
    },
  ],
};

const eligibilityPayload = {
  run_id: runId,
  total_funds: 1,
  ready_count: 1,
  blocked_count: 0,
  status_counts: { relative_label_ready: 1 },
  benchmark_source_counts: { ready: 1 },
  blocker_groups: [],
  filters: { status: "all", limit: 300 },
  results: [
    {
      fund_code: "000001",
      fund_name: "测试基金一号",
      benchmark_source_status: "ready",
      nav_sample_count: 260,
      benchmark_sample_count: 260,
      return_window_status: "ready",
      relative_label_status: "relative_label_ready",
      blocking_reason: "",
      blocking_components: "",
    },
  ],
};

const fundReportPayload = {
  run_id: runId,
  fund_code: "000001",
  review_action: "confirm",
  coverage: { nav: true },
  missing_fields: [],
  labels: [
    {
      label_code: "alpha_positive",
      label_name: "Alpha 为正",
      category: "relative",
      confidence: 0.82,
      status: "active",
    },
    {
      label_code: "style_stable",
      label_name: "风格稳定",
      category: "style",
      confidence: 0.76,
      status: "observe",
    },
  ],
  evidence: [
    {
      label_code: "alpha_positive",
      metric: "alpha_1y",
      value: "0.052",
      threshold: "> 0",
      source: "nav_and_benchmark",
      message: "近一年 Alpha 为正，满足相对基准标签阈值。",
    },
  ],
  features: [
    { feature_code: "annualized_return_1y", value: "0.128", source: "nav" },
  ],
  factor_exposures: [
    {
      fund_code: "000001",
      report_date: "2026-06-30",
      factor_code: "factor_coverage_weight",
      exposure_value: 0.86,
      coverage_weight: 0.86,
      holding_total_weight: 0.92,
      stock_count: 60,
      covered_stock_count: 54,
      source: "holdings",
      as_of_date: "2026-06-30",
      computed_at: "2026-07-02T00:00:00Z",
    },
  ],
  reviews: [],
  calculations: [],
  summary: {
    label_count: 2,
    feature_count: 1,
    factor_exposure_count: 1,
    evidence_count: 1,
    missing_field_count: 0,
    review_count: 0,
    review_action: "confirm",
  },
};

function draftPayload(manual = false) {
  return {
    run_id: runId,
    run_at: "2026-07-02T00:00:00Z",
    rule_version: "v1",
    objective: "core_satellite_equity_pool",
    config_version: "v1",
    mode: "research",
    rows: [
      {
        fund_code: "000001",
        bucket: manual ? "core" : "satellite",
        draft_weight_pct: 100,
        max_weight_pct: 8,
        score: 10,
        portfolio_roles: ["active_equity_candidate", "satellite_alpha"],
        risk_tags: [],
        ...(manual ? { manual_role_review: "core" } : {}),
      },
    ],
    excluded: [],
  };
}

test("portfolio workbench shows fund labels and clears manual override", async ({ page }) => {
  let manualReview = false;

  await page.route("**/v1/runs", (route) =>
    route.fulfill({ json: { runs: [{ run_id: runId, run_at: "2026-07-02T00:00:00Z" }] } })
  );
  await page.route(`**/v1/runs/${runId}/portfolio-matrix`, (route) =>
    route.fulfill({ json: matrixPayload })
  );
  await page.route(`**/v1/runs/${runId}/portfolio-draft**`, (route) =>
    route.fulfill({ json: draftPayload(manualReview) })
  );
  await page.route(`**/v1/runs/${runId}/relative-label-eligibility**`, (route) =>
    route.fulfill({ json: eligibilityPayload })
  );
  await page.route(`**/v1/runs/${runId}/funds/000001/report`, (route) =>
    route.fulfill({ json: fundReportPayload })
  );
  await page.route(`**/v1/runs/${runId}/portfolio-role-reviews`, async (route) => {
    if (route.request().method() === "POST") {
      manualReview = true;
      await route.fulfill({
        json: {
          run_id: runId,
          fund_code: "000001",
          role_code: "manual_portfolio_role",
          decision: "accept",
          target_bucket: "core",
          max_weight_pct: 0,
          rationale: "portfolio workbench calibration",
          reviewer: "researcher-a",
          reviewed_at: "2026-07-02T00:00:01Z",
        },
      });
      return;
    }
    await route.fulfill({ json: { run_id: runId, reviews: [] } });
  });
  await page.route(`**/v1/runs/${runId}/portfolio-role-reviews/000001/manual_portfolio_role`, async (route) => {
    manualReview = false;
    await route.fulfill({ json: { deleted: true } });
  });

  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "从标签引擎，到可审计的基金研究与组合工作台" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "现在交付的是研究基础设施，不是一个标签小工具" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "基金地图：点一只基金，马上看到标签和证据" })).toBeVisible();
  await expect(page.getByText("000001").first()).toBeVisible();
  await expect(page.getByText("Alpha 为正").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "为什么这样打标签" })).toBeVisible();

  await page.locator("select").last().selectOption("core");
  await expect(page.getByText("人工覆盖：核心").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "撤销" })).toBeVisible();

  await page.getByRole("button", { name: "撤销" }).click();
  await expect(page.getByText("人工覆盖：核心")).toHaveCount(0);
});
