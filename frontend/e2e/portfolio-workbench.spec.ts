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
      data_tags: [],
      blocking_reasons: [],
      watch_reasons: [],
      features: {},
    },
  ],
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

test("portfolio workbench shows and clears manual override", async ({ page }) => {
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
  await expect(page.getByRole("heading", { name: "组合工作台" })).toBeVisible();
  await expect(page.getByText("000001")).toBeVisible();

  await page.locator("select").last().selectOption("core");
  await expect(page.getByText("人工覆盖：核心")).toBeVisible();
  await expect(page.getByRole("button", { name: "撤销" })).toBeVisible();

  await page.getByRole("button", { name: "撤销" }).click();
  await expect(page.getByText("人工覆盖：核心")).toHaveCount(0);
});
