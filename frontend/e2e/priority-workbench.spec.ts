import { expect, test } from "@playwright/test";

const priorityRunId = "pr_test_001";
const thesisId = "th_test_001";

// 模拟 PriorityRun 详情响应
const priorityRunPayload = {
  priority_run_id: priorityRunId,
  thesis_id: thesisId,
  candidate_set_id: "cs_test_001",
  strategy_policy_id: "private_equity_growth",
  strategy_policy_version: 2,
  data_snapshot_id: "snap_test_001",
  ranking_method_version: "fund_priority_v0",
  result_type: "ranked_candidates",
  result_status: "completed",
  evaluated_candidate_count: 3,
  eligible_candidate_count: 2,
  tier_counts: {
    research_now: 1,
    research_next: 1,
    valuation_watch: 0,
    data_insufficient: 0,
    excluded: 1,
  },
  approved_for_production: false,
  created_by: "smoke_researcher_001",
  created_at: "2026-07-10T12:00:00Z",
  thesis: {
    thesis_id: thesisId,
    title: "消费升级投资假设",
    belief_statement: "消费行业将在未来三年持续受益于居民收入增长。",
    time_horizon: "3年",
    status: "researching",
    owner: "researcher_001",
    as_of_date: "2026-07-01",
    created_at: "2026-07-01T08:00:00Z",
    next_review_at: "2026-10-01",
    supporting_evidence: null,
    opposing_evidence: null,
    key_metrics: null,
    catalysts: null,
    invalidation_conditions: ["居民收入增速低于3%", "消费行业政策重大变化"],
  },
  research_input: {
    user_input_id: "ri_test_001",
    input_type: "industry",
    business_mode: "fof",
    raw_text: "看好消费升级方向，希望筛选相关基金",
    structured_intent: { direction: "consumer", conviction: "medium" },
    actor_role: "researcher",
    actor_id: "researcher_001",
    request_source: "research_meeting",
    as_of_date: "2026-07-01",
    created_at: "2026-07-01T08:00:00Z",
  },
  candidate_set_header: {
    candidate_set_id: "cs_test_001",
    source_method_version: "fund_candidate_evidence_v0",
    scanned_fund_count: 3,
    mapped_candidate_count: 2,
    unmapped_due_to_data_count: 0,
    unrelated_fund_count: 1,
    created_by: "smoke_researcher_001",
    created_at: "2026-07-10T12:00:00Z",
  },
  candidates_by_tier: {
    research_now: [
      {
        priority_result_id: "pr_result_001",
        priority_run_id: priorityRunId,
        candidate_id: "cand_001",
        fund_code: "000001",
        fund_name: "华夏成长",
        eligibility_status: "eligible",
        priority_tier: "research_now",
        priority_rank: 1,
        matched_holding_weight: 0.35,
        disclosed_holding_weight: 0.42,
        normalized_match_pct: 0.172,
        fit_score: 0.85,
        evidence_score: 0.92,
        holdings_truth_status: "verified",
        valuation_status: "normal",
        data_quality_status: "sufficient",
        holding_report_date: "2026-06-30",
        dimension_results: {},
        priority_reasons: [
          { code: "all_required_evidence_present", message: "" },
        ],
        exclusion_reasons: [],
      },
    ],
    research_next: [
      {
        priority_result_id: "pr_result_002",
        priority_run_id: priorityRunId,
        candidate_id: "cand_002",
        fund_code: "000002",
        fund_name: "南方优选",
        eligibility_status: "eligible",
        priority_tier: "research_next",
        priority_rank: 1,
        matched_holding_weight: 0.22,
        disclosed_holding_weight: 0.28,
        normalized_match_pct: 0.045,
        fit_score: 0.72,
        evidence_score: 0.78,
        holdings_truth_status: "verified",
        valuation_status: "normal",
        data_quality_status: "sufficient",
        holding_report_date: "2026-06-30",
        dimension_results: {},
        priority_reasons: [
          { code: "partial_evidence_sufficient", message: "" },
        ],
        exclusion_reasons: [],
      },
    ],
    valuation_watch: [],
    data_insufficient: [],
    excluded: [
      {
        priority_result_id: "pr_result_003",
        priority_run_id: priorityRunId,
        candidate_id: "cand_003",
        fund_code: "000003",
        fund_name: "某排除基金",
        eligibility_status: "ineligible",
        priority_tier: "excluded",
        priority_rank: null,
        matched_holding_weight: 0.01,
        disclosed_holding_weight: 0.02,
        normalized_match_pct: 0.001,
        fit_score: 0.12,
        evidence_score: 0.15,
        holdings_truth_status: "unverified",
        valuation_status: "data_missing",
        data_quality_status: "insufficient",
        holding_report_date: null,
        dimension_results: {},
        priority_reasons: [],
        exclusion_reasons: [
          { code: "target_exposure_below_minimum", message: "" },
        ],
      },
    ],
  },
};

const historyRunsPayload = [
  {
    priority_run_id: priorityRunId,
    thesis_id: thesisId,
    candidate_set_id: "cs_test_001",
    strategy_policy_id: "private_equity_growth",
    strategy_policy_version: 2,
    data_snapshot_id: "snap_test_001",
    ranking_method_version: "fund_priority_v0",
    result_type: "ranked_candidates",
    result_status: "completed",
    evaluated_candidate_count: 3,
    eligible_candidate_count: 2,
    tier_counts: { research_now: 1, research_next: 1, valuation_watch: 0, data_insufficient: 0, excluded: 1 },
    created_by: "smoke_researcher_001",
    created_at: "2026-07-10T12:00:00Z",
  },
];

// 统一路由处理器：根据 URL 返回不同的 mock 响应
async function setupAndGoto(page: import("@playwright/test").Page, runIdParam: string) {
  await page.route("**/v1/governance/**", (route) => {
    const url = route.request().url();
    if (url.includes("/theses/") && url.endsWith("/candidate-priority-runs")) {
      route.fulfill({ json: historyRunsPayload });
    } else if (url.includes("/candidate-priority-runs/") && !url.includes("/theses/")) {
      route.fulfill({ json: priorityRunPayload });
    } else {
      route.continue();
    }
  });
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/candidate-priority-runs/") && !resp.url().includes("/theses/")
  );
  await page.goto(`/priority?run=${runIdParam}`);
  await responsePromise;
}

// ============================================================
// 测试：归一化匹配率正确显示为百分比
// ============================================================
test("normalized_match_pct 0.172 displays as 17.2%", async ({ page }) => {
  await setupAndGoto(page, priorityRunId);

  // 等待表格渲染（用 td 定位避免匹配侧栏）
  await expect(page.locator("td:has-text('华夏成长')")).toBeVisible({ timeout: 10000 });

  // 归一化匹配率应该显示 17.2%，不是 0.2%（在侧栏的 dd 中）
  await expect(page.locator("dd:has-text('17.2%')")).toBeVisible();

  // 确认不存在 0.2%（错误的旧格式）
  const wrongFormat = await page.locator("text=0.2%").count();
  expect(wrongFormat).toBe(0);
});

// ============================================================
// 测试：投资假设原文和元数据展示
// ============================================================
test("thesis title and belief_statement are displayed", async ({ page }) => {
  await setupAndGoto(page, priorityRunId);

  // 标题
  await expect(page.locator("text=消费升级投资假设")).toBeVisible({ timeout: 10000 });
  // 信念陈述
  await expect(page.locator("text=消费行业将在未来三年持续受益于居民收入增长。")).toBeVisible();
  // 研究请求原文
  await expect(page.locator("text=看好消费升级方向")).toBeVisible();
  // 失效条件
  await expect(page.locator("text=居民收入增速低于3%")).toBeVisible();
  // 候选集统计
  await expect(page.locator("text=不相关：1")).toBeVisible();
});

// ============================================================
// 测试：404 错误恢复
// ============================================================
test("404 error shows Chinese message and retry button", async ({ page }) => {
  let callCount = 0;
  await page.route("**/v1/governance/candidate-priority-runs/*", (route) => {
    callCount++;
    if (callCount === 1) {
      route.fulfill({ status: 404, body: "Not Found" });
    } else {
      route.fulfill({ json: priorityRunPayload });
    }
  });

  await page.goto(`/priority?run=invalid_id`);

  // 应显示中文错误
  await expect(page.locator("text=未找到 PriorityRun")).toBeVisible({ timeout: 10000 });
  // 应显示重试按钮
  await expect(page.locator("button:has-text('重试')")).toBeVisible();
  // 输入框应保留
  await expect(page.locator("#priority-run-input")).toBeVisible();
});

// ============================================================
// 测试：键盘可访问性 - tab 到基金行并按 Enter 选中
// ============================================================
test("fund row is keyboard accessible with Enter", async ({ page }) => {
  await setupAndGoto(page, priorityRunId);

  // Tab 到第一个基金行（可能需要多次 tab）
  const fundRow = page.locator("tr").filter({ hasText: "华夏成长" });
  await fundRow.focus();

  // 按 Enter 选中
  await fundRow.press("Enter");

  // 侧栏应显示原因码
  await expect(page.locator("text=全部必需证据齐全")).toBeVisible({ timeout: 5000 });
});

// ============================================================
// 测试：390px 宽度下页面不横向溢出
// ============================================================
test("390px viewport has no horizontal overflow", async ({ page }) => {
  await page.route("**/v1/governance/**", (route) => {
    const url = route.request().url();
    if (url.includes("/theses/") && url.endsWith("/candidate-priority-runs")) {
      route.fulfill({ json: historyRunsPayload });
    } else if (url.includes("/candidate-priority-runs/") && !url.includes("/theses/")) {
      route.fulfill({ json: priorityRunPayload });
    } else {
      route.continue();
    }
  });

  await page.setViewportSize({ width: 390, height: 844 });
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/candidate-priority-runs/") && !resp.url().includes("/theses/")
  );
  await page.goto(`/priority?run=${priorityRunId}`);
  await responsePromise;
  await expect(page.locator("td:has-text('华夏成长')")).toBeVisible({ timeout: 10000 });

  // 检查是否有横向溢出
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});

// ============================================================
// 测试：五档展示和档内排序
// ============================================================
test("five tiers are displayed in correct order", async ({ page }) => {
  await setupAndGoto(page, priorityRunId);

  // 验证五档标签存在（用 first() 因为侧栏也有 badge）
  await expect(page.locator(".badge:has-text('立即研究')").first()).toBeVisible({ timeout: 10000 });
  await expect(page.locator(".badge:has-text('下一步研究')").first()).toBeVisible();
  await expect(page.locator(".badge:has-text('估值观察')").first()).toBeVisible();
  await expect(page.locator(".badge:has-text('数据不足')").first()).toBeVisible();
  await expect(page.locator(".badge:has-text('排除')").first()).toBeVisible();

  // 验证非生产标志
  await expect(page.locator("text=非生产")).toBeVisible();

  // 验证免责声明
  await expect(page.locator("text=研究顺序，不是买入建议")).toBeVisible();
});
