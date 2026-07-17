import { expect, test } from "@playwright/test";

const recommendationRunId = "frr_fixture";
const thesisId = "th_fixture_001";

// 模拟 RecommendationRun 详情响应
const recommendationRunPayload = {
  recommendation_run_id: recommendationRunId,
  thesis_id: thesisId,
  candidate_set_id: "cs_fixture_001",
  strategy_policy_id: "private_equity_growth",
  strategy_policy_version: 1,
  data_snapshot_id: "snap_fixture_001",
  recommendation_method_version: "fund_recommendation_v1",
  result_type: "ranked_recommendations",
  result_status: "completed",
  evaluated_candidate_count: 4,
  recommended_count: 2,
  tier_counts: {
    candidate_pool: 2,
    alternative: 1,
    watch: 0,
    excluded: 1,
    data_insufficient: 0,
  },
  created_by: "smoke_researcher_001",
  created_at: "2026-07-16T12:00:00Z",
  thesis: {
    thesis_id: thesisId,
    title: "消费升级投资假设",
    belief_statement: "消费行业将在未来三年持续受益于居民收入增长。",
    as_of_date: "2026-07-01",
    status: "researching",
  },
  candidate_set_header: {
    candidate_set_id: "cs_fixture_001",
    scanned_fund_count: 10,
    mapped_candidate_count: 4,
  },
  candidates_by_category: {
    active_fund: [
      {
        recommendation_result_id: "frrr_001",
        recommendation_run_id: recommendationRunId,
        candidate_id: "cand_001",
        fund_code: "000001",
        fund_name: "华夏成长",
        product_category: "active_fund",
        recommendation_tier: "candidate_pool",
        category_rank: 1,
        theme_exposure_score: 0.82,
        thesis_alignment_score: 0.75,
        risk_return_score: 0.68,
        fund_quality_score: 0.90,
        total_score: 0.79,
        recommendation_reasons: [
          { code: "high_theme_exposure", message: "主题暴露纯度达标" },
          { code: "strong_quality", message: "基金经理稳定" },
        ],
        exclusion_reasons: [],
        frozen_evidence: {
          holding_report_date: "2026-06-30",
          product_category: "active_fund",
        },
      },
      {
        recommendation_result_id: "frrr_002",
        recommendation_run_id: recommendationRunId,
        candidate_id: "cand_002",
        fund_code: "000002",
        fund_name: "南方优选",
        product_category: "active_fund",
        recommendation_tier: "alternative",
        category_rank: 2,
        theme_exposure_score: 0.45,
        thesis_alignment_score: 0.60,
        risk_return_score: 0.55,
        fund_quality_score: 0.70,
        total_score: 0.52,
        recommendation_reasons: [
          { code: "moderate_theme_exposure", message: "主题暴露中等" },
        ],
        exclusion_reasons: [],
        frozen_evidence: {
          holding_report_date: "2026-06-30",
          product_category: "active_fund",
        },
      },
    ],
    etf_or_index: [
      {
        recommendation_result_id: "frrr_003",
        recommendation_run_id: recommendationRunId,
        candidate_id: "cand_003",
        fund_code: "159001",
        fund_name: "消费ETF",
        product_category: "etf_or_index",
        recommendation_tier: "candidate_pool",
        category_rank: 1,
        theme_exposure_score: 0.95,
        thesis_alignment_score: 0.80,
        risk_return_score: 0.60,
        fund_quality_score: 0.85,
        total_score: 0.84,
        recommendation_reasons: [
          { code: "high_purity", message: "指数纯度高" },
        ],
        exclusion_reasons: [],
        frozen_evidence: {
          holding_report_date: "2026-06-30",
          product_category: "etf_or_index",
        },
      },
      {
        recommendation_result_id: "frrr_004",
        recommendation_run_id: recommendationRunId,
        candidate_id: "cand_004",
        fund_code: "510100",
        fund_name: "某排除指数",
        product_category: "etf_or_index",
        recommendation_tier: "excluded",
        category_rank: null,
        theme_exposure_score: 0.10,
        thesis_alignment_score: 0.20,
        risk_return_score: 0.30,
        fund_quality_score: 0.40,
        total_score: 0.18,
        recommendation_reasons: [],
        exclusion_reasons: [
          { code: "below_minimum_theme_exposure", message: "主题暴露低于门槛" },
        ],
        frozen_evidence: {
          holding_report_date: "2026-05-31",
          product_category: "etf_or_index",
        },
      },
    ],
  },
  recommended_universe: [],
  portfolio: {
    selection_source: "recommended_universe",
    recommendation_run_ids: [recommendationRunId],
    status: "complete",
    holdings: [
      { fund_code: "000001", fund_name: "华夏成长", weight: 45.0 },
      { fund_code: "159001", fund_name: "消费ETF", weight: 40.0 },
      { fund_code: "000002", fund_name: "南方优选", weight: 15.0 },
    ],
    enforced_actions: [
      { type: "concentration_cap", fund_code: "000001", detail: "权重超限，调减至 45%" },
    ],
    metrics: {
      max_holding_weight: 45.0,
      portfolio_volatility: 18.0,
      portfolio_drawdown: 12.0,
    },
  },
};

const historyRunsPayload = [
  {
    recommendation_run_id: recommendationRunId,
    thesis_id: thesisId,
    candidate_set_id: "cs_fixture_001",
    strategy_policy_id: "private_equity_growth",
    strategy_policy_version: 1,
    data_snapshot_id: "snap_fixture_001",
    recommendation_method_version: "fund_recommendation_v1",
    result_type: "ranked_recommendations",
    result_status: "completed",
    evaluated_candidate_count: 4,
    recommended_count: 2,
    tier_counts: { candidate_pool: 2, alternative: 1, watch: 0, excluded: 1, data_insufficient: 0 },
    created_by: "smoke_researcher_001",
    created_at: "2026-07-16T12:00:00Z",
  },
];

// 统一路由处理器
async function setupAndGoto(page: import("@playwright/test").Page, runIdParam: string) {
  await page.route("**/v1/governance/**", (route) => {
    const url = route.request().url();
    if (url.includes("/theses/") && url.endsWith("/fund-recommendation-runs")) {
      route.fulfill({ json: historyRunsPayload });
    } else if (url.includes("/fund-recommendation-runs/") && !url.includes("/theses/")) {
      route.fulfill({ json: recommendationRunPayload });
    } else {
      route.continue();
    }
  });
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/fund-recommendation-runs/") && !resp.url().includes("/theses/")
  );
  await page.goto(`/recommendations?run=${runIdParam}`);
  await responsePromise;
}

// ============================================================
// 测试：双榜单和组合的固定阅读顺序
// ============================================================
test("shows separate fund lists before the final portfolio", async ({ page }) => {
  await setupAndGoto(page, recommendationRunId);

  await expect(page.getByRole("heading", { name: "主题基金推荐" })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("heading", { name: "主动基金推荐" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ETF / 指数基金推荐" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "最终组合建议" })).toBeVisible();
  await expect(page.getByText("主题暴露纯度").first()).toBeVisible();
});

// ============================================================
// 测试：主动基金榜单展示基金代码和档位
// ============================================================
test("active fund list shows fund codes and tiers", async ({ page }) => {
  await setupAndGoto(page, recommendationRunId);

  await expect(page.locator("td:has-text('000001')").first()).toBeVisible({ timeout: 10000 });
  await expect(page.locator("td:has-text('000002')").first()).toBeVisible();
  // 档位 badge
  await expect(page.getByText("建议纳入候选池", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("备选", { exact: true }).first()).toBeVisible();
});

// ============================================================
// 测试：ETF 榜单展示基金和排除原因
// ============================================================
test("ETF list shows fund and exclusion reason", async ({ page }) => {
  await setupAndGoto(page, recommendationRunId);

  await expect(page.locator("td:has-text('159001')").first()).toBeVisible({ timeout: 10000 });
  // 排除基金的未选原因
  await expect(page.locator("text=below_minimum_theme_exposure").first()).toBeVisible();
});

// ============================================================
// 测试：组合区展示持仓和风险调权
// ============================================================
test("portfolio section shows holdings and risk actions", async ({ page }) => {
  await setupAndGoto(page, recommendationRunId);

  await expect(page.getByRole("heading", { name: "最终组合建议" })).toBeVisible({ timeout: 10000 });
  // 来源标记
  await expect(page.locator("text=来源：推荐池")).toBeVisible();
  // 持仓
  await expect(page.locator("text=45.0%")).toBeVisible();
  // 风险强制调权
  await expect(page.locator("text=风险强制调权")).toBeVisible();
  await expect(page.locator("text=concentration_cap")).toBeVisible();
});

// ============================================================
// 测试：404 错误恢复
// ============================================================
test("404 error shows Chinese message and retry button", async ({ page }) => {
  let callCount = 0;
  await page.route("**/v1/governance/fund-recommendation-runs/*", (route) => {
    callCount++;
    if (callCount === 1) {
      route.fulfill({ status: 404, body: "Not Found" });
    } else {
      route.fulfill({ json: recommendationRunPayload });
    }
  });

  await page.goto(`/recommendations?run=invalid_id`);

  await expect(page.locator("text=未找到推荐运行")).toBeVisible({ timeout: 10000 });
  await expect(page.locator("button:has-text('重试')")).toBeVisible();
  await expect(page.locator("#rec-run-input")).toBeVisible();
});

// ============================================================
// 测试：390px 宽度下页面不横向溢出
// ============================================================
test("390px viewport has no horizontal overflow", async ({ page }) => {
  await setupAndGoto(page, recommendationRunId);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("td:has-text('000001')").first()).toBeVisible({ timeout: 10000 });

  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
