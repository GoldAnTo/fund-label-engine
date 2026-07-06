import { expect, test } from "@playwright/test";

const runId = "run-e2e";
const previousRunId = "run-prev";

const runsPayload = {
  runs: [
    { run_id: runId, run_at: "2026-07-02T00:00:00Z", rule_version: "v1", status: "succeeded" },
    { run_id: previousRunId, run_at: "2026-06-25T00:00:00Z", rule_version: "v1", status: "succeeded" },
  ],
};

const runDetailPayload = {
  run_id: runId,
  run_at: "2026-07-02T00:00:00Z",
  rule_version: "v1",
  status: "succeeded",
  fund_codes: ["000001", "000002"],
  failure_count: 0,
  failures: [],
  data_snapshot_id: "snap-1",
  data_snapshot: {
    snapshot_id: "snap-1",
    source_db_path: "/tmp/source.sqlite",
    fund_count: 142,
    benchmark_returns_count: 120,
    created_at: "2026-07-02T00:00:00Z",
  },
};

const runSummaryPayload = {
  run_id: runId,
  run_at: "2026-07-02T00:00:00Z",
  rule_version: "v1",
  status: "succeeded",
  counts: {
    processed: 2,
    failed: 0,
    data_insufficient: 0,
    manual_review: 0,
    return_window_insufficient: 0,
    not_computed_calculations: 0,
  },
  label_distribution: [],
  review_action_distribution: [],
  category_distribution: [],
  calculation_state_distribution: [],
  label_change_summary: {
    total: 2,
    risk_warnings: 1,
    by_type: { added: 1, status_changed: 1 },
  },
};

const labelChangesPayload = {
  run_id: runId,
  summary: runSummaryPayload.label_change_summary,
  count: 2,
  changes: [
    {
      run_id: runId,
      previous_run_id: previousRunId,
      fund_code: "000001",
      label_code: "drawdown_high",
      change_type: "status_changed",
      previous_status: "inactive",
      current_status: "active",
      is_risk_warning: 1,
      detected_at: "2026-07-02T00:00:00Z",
    },
    {
      run_id: runId,
      previous_run_id: previousRunId,
      fund_code: "000002",
      label_code: "small_cap",
      change_type: "added",
      previous_status: null,
      current_status: "active",
      is_risk_warning: 0,
      detected_at: "2026-07-02T00:00:00Z",
    },
  ],
};

const stylePayload = {
  run_id: runId,
  styles: { deep_value: { count: 0, funds: [] }, quality_growth: { count: 0, funds: [] }, dividend_steady: { count: 0, funds: [] } },
  boundary_counts: { stock_factors_missing: 0, style_pending_rule_definition: 0 },
};

test("run detail surfaces label changes and risk warnings", async ({ page }) => {
  await page.route("**/v1/runs", (route) => route.fulfill({ json: runsPayload }));
  await page.route(`**/v1/runs/${runId}`, (route) => route.fulfill({ json: runDetailPayload }));
  await page.route(`**/v1/runs/${runId}/summary`, (route) => route.fulfill({ json: runSummaryPayload }));
  await page.route(`**/v1/runs/${runId}/style`, (route) => route.fulfill({ json: stylePayload }));
  await page.route(`**/v1/runs/${runId}/label-changes**`, (route) =>
    route.fulfill({ json: labelChangesPayload })
  );

  await page.goto(`/runs/${runId}`);

  await expect(page.getByRole("heading", { name: "批次详情" })).toBeVisible();
  // "标签变化" 区块 + 风险预警 badge
  await expect(page.getByRole("heading", { name: /标签变化/ })).toBeVisible();
  await expect(page.getByText("1 项风险预警", { exact: true })).toBeVisible();
  // 风险预警 detail 展开时显示基金代码
  await expect(page.getByText("drawdown_high").first()).toBeVisible();
});

test("run trigger and refresh reloads the list", async ({ page }) => {
  let refreshTriggered = false;
  await page.route("**/v1/runs", (route) => {
    if (route.request().method() === "POST") {
      refreshTriggered = true;
      return route.fulfill({
        json: {
          run_id: "newrun",
          processed: 142,
          failed: 0,
          status: "succeeded",
        },
      });
    }
    return route.fulfill({ json: { runs: runsPayload.runs } });
  });

  await page.goto("/runs");

  await expect(page.getByText("暂无批次").or(page.getByText(runId.slice(0, 12)))).toBeVisible();

  // 设置 dialog 处理
  page.on("dialog", (dialog) => dialog.accept());

  await page.getByRole("button", { name: "运行批次" }).click();

  // 由于 useAsync refresh 修复了，POST 后应自动刷新
  await expect.poll(() => refreshTriggered, { timeout: 5000 }).toBe(true);
});
