import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchPriorityRun,
  fetchPriorityRunsByThesis,
  type PriorityCandidate,
  type PriorityRunDetail,
  type PriorityRunSummary,
} from "../api";
import { Card, Badge, Table, Th, Td } from "../components/ui";

// 请求来源中文映射
const REQUEST_SOURCE_LABELS: Record<string, string> = {
  research_meeting: "研究会议",
  ad_hoc_research: "临时研究",
  portfolio_review: "组合复核",
  risk_review: "风险复核",
};

// 投资假设状态中文映射
const THESIS_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  researching: "研究中",
  validated: "已验证",
  approved: "已批准",
  watching: "观察中",
  invalidated: "已失效",
  closed: "已关闭",
};

// 五档固定顺序
const TIER_ORDER = [
  "research_now",
  "research_next",
  "valuation_watch",
  "data_insufficient",
  "excluded",
] as const;

type TierKey = (typeof TIER_ORDER)[number];

// 五档标签配置：中文标签 + Badge variant
const TIER_CONFIG: Record<TierKey, { label: string; variant: "pos" | "accent" | "warn" | "neutral" | "neg" }> = {
  research_now: { label: "立即研究", variant: "pos" },
  research_next: { label: "下一步研究", variant: "accent" },
  valuation_watch: { label: "估值观察", variant: "warn" },
  data_insufficient: { label: "数据不足", variant: "neutral" },
  excluded: { label: "排除", variant: "neg" },
};

// 原因码中文映射
const REASON_LABELS: Record<string, string> = {
  all_required_evidence_present: "全部必需证据齐全",
  partial_evidence_sufficient: "部分证据充足",
  valuation_soft_breach: "估值软性超标",
  valuation_hard_breach: "估值硬性超标",
  valuation_data_missing: "估值数据缺失",
  holding_data_missing: "持仓数据缺失",
  holding_data_stale: "持仓数据过期",
  holding_report_date_missing: "持仓报告期缺失",
  disclosed_holding_weight_low: "已披露持仓权重不足",
  factor_coverage_insufficient: "因子覆盖不足",
  manager_identity_missing: "基金经理信息缺失",
  policy_asset_type_not_allowed: "资产类型不在策略允许范围",
  policy_universe_excluded: "基金在策略排除清单中",
  target_exposure_below_minimum: "目标持仓低于最低要求",
};

// 权重格式化：0-1 转百分比，保留1位小数
function fmtWeight(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `${(v * 100).toFixed(1)}%`;
}

// 评分格式化：保留2位小数
function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return v.toFixed(2);
}

// 文本格式化：空值显示 "-"
function fmtText(v: string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "-";
  return v;
}

// 原因码转中文
function reasonLabel(code: string): string {
  return REASON_LABELS[code] ?? code;
}

export default function PriorityWorkbenchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  // 直接从 URL 读取运行 ID，不维护独立 state
  const runId = searchParams.get("run") || "";
  const [runInput, setRunInput] = useState("");
  const [detail, setDetail] = useState<PriorityRunDetail | null>(null);
  const [historyRuns, setHistoryRuns] = useState<PriorityRunSummary[]>([]);
  const [selectedResultId, setSelectedResultId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // 加载 PriorityRun 详情：依赖 URL 的 run 值，使用 AbortController + cancelled flag
  useEffect(() => {
    if (!runId) {
      setDetail(null);
      setHistoryRuns([]);
      setSelectedResultId("");
      setError(null);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchPriorityRun(runId, controller.signal)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setSelectedResultId("");
        // 默认选中第一档第一个候选
        for (const tier of TIER_ORDER) {
          const candidates = data.candidates_by_tier?.[tier] ?? [];
          if (candidates.length > 0) {
            setSelectedResultId(candidates[0].priority_result_id);
            break;
          }
        }
      })
      .catch((e) => {
        if (cancelled || e?.name === "AbortError") return;
        setDetail(null);
        let msg = e instanceof Error ? e.message : String(e);
        // 转换常见错误为中文
        if (msg.includes("404")) msg = `未找到 PriorityRun: ${runId}`;
        else if (msg.includes("500")) msg = "服务器内部错误，请稍后重试";
        else if (msg.includes("Failed to fetch")) msg = "网络连接失败，请检查后端服务是否运行";
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [runId]);

  // 加载同 Thesis 的历史运行列表（带取消）
  useEffect(() => {
    if (!detail?.thesis_id) {
      setHistoryRuns([]);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    fetchPriorityRunsByThesis(detail.thesis_id, controller.signal)
      .then((runs) => {
        if (!cancelled) setHistoryRuns(runs);
      })
      .catch((e) => {
        if (cancelled || e?.name === "AbortError") return;
        setHistoryRuns([]);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [detail?.thesis_id]);

  // 切换运行：直接更新 URL，由 URL 变化触发 useEffect
  const handleRunChange = (newId: string) => {
    setSearchParams(newId ? { run: newId } : {}, { replace: true });
  };

  // 手动输入加载
  const handleLoadInput = () => {
    const trimmed = runInput.trim();
    if (trimmed) handleRunChange(trimmed);
  };

  // 选中基金行
  const handleSelect = (resultId: string) => {
    setSelectedResultId(resultId);
  };

  // 查找当前选中的候选对象
  const selectedCandidate: PriorityCandidate | null = (() => {
    if (!detail || !selectedResultId) return null;
    for (const tier of TIER_ORDER) {
      const candidates = detail.candidates_by_tier?.[tier] ?? [];
      const found = candidates.find((c) => c.priority_result_id === selectedResultId);
      if (found) return found;
    }
    return null;
  })();

  // 错误状态或没有 runId 时，显示输入框卡片
  if (error || !runId) {
    return (
      <div className="space-y-4">
        <Card>
          <div className="p-4 space-y-3">
            <h2 className="text-base font-semibold text-text m-0">
              投资假设详情 / 基金研究优先级
            </h2>
            {error && (
              <div
                className="rounded-lg border border-warn/30 bg-warn-soft px-3 py-2 text-warn-text text-sm flex items-center gap-3"
                role="alert"
              >
                <span className="flex-1">{error}</span>
                <button
                  className="text-xs px-3 py-1 border border-warn/40 bg-surface text-warn-text rounded hover:bg-warn-soft transition-colors"
                  onClick={() => {
                    setError(null);
                    // 重新触发加载：先清除再恢复 URL 参数
                    const current = runId;
                    setSearchParams({}, { replace: true });
                    setTimeout(() => setSearchParams({ run: current }, { replace: true }), 0);
                  }}
                >
                  重试
                </button>
              </div>
            )}
            <p className="text-sm text-text-2">
              请输入 PriorityRun ID 加载工作台，或通过 URL 参数 ?run=xxx 直接访问。
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <label
                htmlFor="priority-run-input"
                className="text-xs text-text-2"
              >
                PriorityRun ID
              </label>
              <input
                id="priority-run-input"
                className="flex-0 w-80 px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
                placeholder="输入 priority_run_id"
                value={runInput}
                onChange={(e) => setRunInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLoadInput();
                }}
                aria-label="PriorityRun ID 输入框"
              />
              <button
                className="px-4 py-1.5 text-sm font-semibold bg-accent text-surface border border-accent rounded hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={handleLoadInput}
                disabled={!runInput.trim()}
              >
                加载
              </button>
            </div>
            <p className="text-xs text-text-3">免责声明：研究顺序，不是买入建议。</p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 加载提示 */}
      {!error && loading && (
        <div
          className="rounded-lg border border-accent/30 bg-accent-soft px-3 py-2 text-accent-text text-sm"
          role="status"
          aria-live="polite"
        >
          加载中...
        </div>
      )}

      {/* === 第 1 层：头部摘要 (Header Summary) === */}
      {detail && (
        <Card>
          <div className="p-4 space-y-3">
            {/* PriorityRun 标签 + 政策版本 + 快照版本 + 方法版本 + 非生产 */}
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={
                  detail.result_status === "completed"
                    ? "pos"
                    : detail.result_status === "running"
                      ? "accent"
                      : detail.result_status === "failed"
                        ? "neg"
                        : "neutral"
                }
              >
                PriorityRun：{detail.result_status}
              </Badge>
              <Badge variant="neutral">
                Strategy Policy: {detail.strategy_policy_id} v{detail.strategy_policy_version}
              </Badge>
              {detail.data_snapshot_id && (
                <Badge variant="neutral">Snapshot: {detail.data_snapshot_id.slice(0, 12)}</Badge>
              )}
              <Badge variant="neutral">Method: {detail.ranking_method_version}</Badge>
              {!detail.approved_for_production && (
                <Badge variant="neg">非生产</Badge>
              )}
              <span className="text-xs text-text-3">免责声明：研究顺序，不是买入建议。</span>
            </div>

            {/* URL 输入框 + 历史运行选择器 */}
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border">
              <label className="text-xs text-text-2">PriorityRun URL</label>
              <input
                className="flex-1 min-w-0 max-w-md px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
                placeholder="输入 priority_run_id"
                value={runInput}
                onChange={(e) => setRunInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLoadInput();
                }}
                aria-label="PriorityRun ID 输入框"
              />
              <button
                className="px-4 py-1.5 text-sm font-semibold bg-accent text-surface border border-accent rounded hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={handleLoadInput}
                disabled={!runInput.trim()}
              >
                加载
              </button>
              <label className="text-xs text-text-2 ml-2">历史运行</label>
              <select
                className="min-w-70 px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
                value={runId}
                onChange={(e) => handleRunChange(e.target.value)}
              >
                {historyRuns.length === 0 ? (
                  <option value={runId}>{runId.slice(0, 16)}</option>
                ) : (
                  <>
                    {!historyRuns.some((r) => r.priority_run_id === runId) && (
                      <option value={runId}>{runId.slice(0, 16)} (当前)</option>
                    )}
                    {historyRuns.map((r) => (
                      <option key={r.priority_run_id} value={r.priority_run_id}>
                        {r.created_at?.slice(0, 19).replace("T", " ")} (
                        {r.priority_run_id.slice(0, 8)})
                      </option>
                    ))}
                  </>
                )}
              </select>
              <span className="text-xs text-text-3">
                共 {historyRuns.length} 个历史运行
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* === 第 2 层：投资假设详情 (Thesis Card) === */}
      {detail && (
        <Card>
          <div className="p-4 space-y-4">
            {/* 标题 + 信念陈述 */}
            {detail.thesis && (
              <div>
                <h2 className="text-base font-semibold text-text m-0 mb-2">
                  {detail.thesis.title || "投资假设"}
                </h2>
                <p className="text-sm text-text-2 leading-relaxed m-0">
                  {detail.thesis.belief_statement}
                </p>
              </div>
            )}

            {/* 研究请求原文 */}
            {detail.research_input?.raw_text && (
              <div className="px-3 py-2 bg-surface-2 rounded border border-border text-xs text-text-3">
                <strong className="text-text-2">研究请求：</strong>
                {detail.research_input.raw_text}
              </div>
            )}

            {/* 元数据栅格 */}
            <div className="grid grid-cols-1 md:grid-cols-[140px_1fr_140px_1fr] gap-x-4 gap-y-1 text-sm">
              <div className="text-text-3">Thesis ID</div>
              <div className="font-mono font-medium">{fmtText(detail.thesis_id)}</div>
              <div className="text-text-3">Strategy Policy</div>
              <div className="font-mono font-medium">
                {fmtText(detail.strategy_policy_id)} (v{detail.strategy_policy_version})
              </div>
              <div className="text-text-3">Data Snapshot</div>
              <div className="font-mono font-medium">{fmtText(detail.data_snapshot_id)}</div>
              <div className="text-text-3">Ranking Method</div>
              <div className="font-mono font-medium">
                {fmtText(detail.ranking_method_version)}
              </div>
              <div className="text-text-3">PriorityRun ID</div>
              <div className="font-mono text-xs">{fmtText(detail.priority_run_id)}</div>
              <div className="text-text-3">CandidateSet ID</div>
              <div className="font-mono text-xs">{fmtText(detail.candidate_set_id)}</div>
              <div className="text-text-3">创建人</div>
              <div className="font-medium">{fmtText(detail.created_by)}</div>
              <div className="text-text-3">创建时间</div>
              <div className="font-medium">
                {detail.created_at?.slice(0, 19).replace("T", " ") || "-"}
              </div>
            </div>

            {/* 投资假设状态条 */}
            {detail.thesis && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-2">
                {detail.thesis.status && (
                  <span>
                    状态：
                    <strong className="text-text font-semibold">
                      {THESIS_STATUS_LABELS[detail.thesis.status] ?? detail.thesis.status}
                    </strong>
                  </span>
                )}
                {detail.thesis.time_horizon && (
                  <span>
                    时间范围：<strong className="text-text font-semibold">{detail.thesis.time_horizon}</strong>
                  </span>
                )}
                {detail.thesis.owner && (
                  <span>
                    研究员：<strong className="text-text font-semibold">{detail.thesis.owner}</strong>
                  </span>
                )}
                {detail.thesis.as_of_date && (
                  <span>
                    截止日期：<strong className="text-text font-semibold">{detail.thesis.as_of_date}</strong>
                  </span>
                )}
                {detail.thesis.next_review_at && (
                  <span>
                    下次复审：
                    <strong className="text-text font-semibold">
                      {detail.thesis.next_review_at.slice(0, 10)}
                    </strong>
                  </span>
                )}
                {detail.research_input && (
                  <span>
                    来源：
                    <strong className="text-text font-semibold">
                      {REQUEST_SOURCE_LABELS[detail.research_input.request_source] ??
                        detail.research_input.request_source}
                    </strong>
                  </span>
                )}
              </div>
            )}

            {/* 候选集统计 */}
            {detail.candidate_set_header && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 bg-surface-2 rounded text-xs">
                <span>
                  扫描基金：
                  <strong className="font-semibold text-text">
                    {detail.candidate_set_header.scanned_fund_count}
                  </strong>
                </span>
                <span>
                  映射候选：
                  <strong className="font-semibold text-text">
                    {detail.candidate_set_header.mapped_candidate_count}
                  </strong>
                </span>
                <span>
                  数据不足：
                  <strong className="font-semibold text-text">
                    {detail.candidate_set_header.unmapped_due_to_data_count}
                  </strong>
                </span>
                <span>
                  不相关：
                  <strong className="font-semibold text-text">
                    {detail.candidate_set_header.unrelated_fund_count}
                  </strong>
                </span>
                <span className="text-text-3">
                  Source: {detail.candidate_set_header.source_method_version}
                </span>
              </div>
            )}

            {/* 失效条件 */}
            {detail.thesis?.invalidation_conditions &&
              Array.isArray(detail.thesis.invalidation_conditions) &&
              detail.thesis.invalidation_conditions.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wide text-neg-text m-0 mb-1">
                    失效条件
                  </h3>
                  <ul className="m-0 pl-5 text-xs text-text-2 space-y-0.5">
                    {detail.thesis.invalidation_conditions.map((c, i) => (
                      <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* 支持证据 */}
            {detail.thesis?.supporting_evidence &&
              Array.isArray(detail.thesis.supporting_evidence) &&
              detail.thesis.supporting_evidence.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wide text-pos-text m-0 mb-1">
                    支持证据
                  </h3>
                  <ul className="m-0 pl-5 text-xs text-text-2 space-y-0.5">
                    {detail.thesis.supporting_evidence.map((c, i) => (
                      <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* 反对证据 */}
            {detail.thesis?.opposing_evidence &&
              Array.isArray(detail.thesis.opposing_evidence) &&
              detail.thesis.opposing_evidence.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wide text-warn-text m-0 mb-1">
                    反对证据
                  </h3>
                  <ul className="m-0 pl-5 text-xs text-text-2 space-y-0.5">
                    {detail.thesis.opposing_evidence.map((c, i) => (
                      <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* 催化剂 */}
            {detail.thesis?.catalysts &&
              Array.isArray(detail.thesis.catalysts) &&
              detail.thesis.catalysts.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wide text-accent-text m-0 mb-1">
                    催化剂
                  </h3>
                  <ul className="m-0 pl-5 text-xs text-text-2 space-y-0.5">
                    {detail.thesis.catalysts.map((c, i) => (
                      <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* 关键指标 */}
            {detail.thesis?.key_metrics &&
              Array.isArray(detail.thesis.key_metrics) &&
              detail.thesis.key_metrics.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wide text-text-2 m-0 mb-1">
                    关键指标
                  </h3>
                  <ul className="m-0 pl-5 text-xs text-text-2 space-y-0.5">
                    {detail.thesis.key_metrics.map((c, i) => (
                      <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* 非生产警告条 */}
            {!detail.approved_for_production && (
              <div className="px-3 py-2 rounded-lg bg-neg-soft text-neg-text font-bold text-sm border border-neg/40">
                非生产：该 PriorityRun 尚未批准用于生产环境，结果仅供研究参考。
              </div>
            )}

            {/* 免责声明 */}
            <div className="text-xs text-text-3 pt-2 border-t border-border">
              免责声明：研究顺序，不是买入建议。
            </div>
          </div>
        </Card>
      )}

      {/* === 第 3 层：基金候选 (Main Content) === */}
      {detail && (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-3 items-start">
          {/* 左侧：5 档基金列表 */}
          <div className="space-y-3 min-w-0">
            {TIER_ORDER.map((tier) => {
              const config = TIER_CONFIG[tier];
              const candidates = detail.candidates_by_tier?.[tier] ?? [];
              const count = detail.tier_counts?.[tier] ?? candidates.length;
              return (
                <Card key={tier}>
                  <div className="p-4">
                    {/* 档位标题 + 数量 */}
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant={config.variant}>{config.label}</Badge>
                      <span className="text-xs text-text-3">{count} 只</span>
                    </div>

                    {/* 基金表格（空档位不显示表格） */}
                    {candidates.length > 0 ? (
                      <Table>
                        <thead>
                          <tr>
                            <Th className="w-14 text-right">档内排名</Th>
                            <Th className="w-24">基金代码</Th>
                            <Th>基金名称</Th>
                            <Th className="w-28 text-right">真实目标持仓</Th>
                            <Th className="w-24 text-right">披露覆盖</Th>
                            <Th className="w-28">数据质量</Th>
                            <Th className="w-28">估值状态</Th>
                            <Th className="w-20 text-right">证据分</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {candidates.map((c) => (
                            <tr
                              key={c.priority_result_id}
                              tabIndex={0}
                              aria-selected={selectedResultId === c.priority_result_id}
                              onClick={() => handleSelect(c.priority_result_id)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  handleSelect(c.priority_result_id);
                                }
                              }}
                              className={`cursor-pointer outline-none focus:outline-2 focus:outline-accent focus:-outline-offset-2 ${
                                selectedResultId === c.priority_result_id
                                  ? "bg-accent-soft"
                                  : "hover:bg-surface-2"
                              }`}
                            >
                              <Td className="text-right tabular-nums">
                                {c.priority_rank ?? "-"}
                              </Td>
                              <Td className="font-mono font-bold">{c.fund_code}</Td>
                              <Td className="text-text-2">{fmtText(c.fund_name)}</Td>
                              <Td className="text-right tabular-nums">
                                {fmtWeight(c.matched_holding_weight)}
                              </Td>
                              <Td className="text-right tabular-nums">
                                {fmtWeight(c.disclosed_holding_weight)}
                              </Td>
                              <Td>{fmtText(c.data_quality_status)}</Td>
                              <Td>{fmtText(c.valuation_status)}</Td>
                              <Td className="text-right tabular-nums">
                                {fmtScore(c.evidence_score)}
                              </Td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    ) : (
                      <div className="text-center py-6 text-xs text-text-3">
                        该档位暂无候选
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          {/* 右侧：选中基金详情侧栏 */}
          <div className="lg:sticky lg:top-2 lg:max-h-[calc(100vh-16px)] lg:overflow-auto space-y-3">
            {selectedCandidate ? (
              <CandidateDetail candidate={selectedCandidate} />
            ) : (
              <Card>
                <div className="p-4 space-y-2">
                  <h2 className="text-base font-semibold text-text m-0">选中基金详情</h2>
                  <p className="text-sm text-text-3 m-0">点击左侧基金行查看详情。</p>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* 底部免责声明 */}
      {detail && (
        <div className="text-xs text-text-3 text-center py-2">
          免责声明：研究顺序，不是买入建议。
        </div>
      )}
    </div>
  );
}

// 选中基金详情侧栏
function CandidateDetail({ candidate }: { candidate: PriorityCandidate }) {
  const tier = candidate.priority_tier as TierKey | undefined;
  const config = tier ? TIER_CONFIG[tier] : undefined;

  return (
    <Card>
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-border pb-2">
          <h2 className="text-base font-semibold text-text m-0">基金详情</h2>
          {config ? (
            <Badge variant={config.variant}>{config.label}</Badge>
          ) : (
            <Badge variant="neutral">{candidate.priority_tier}</Badge>
          )}
        </div>

        {/* 基本信息 */}
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-text-2 m-0 mb-2">
            基本信息
          </h3>
          <div className="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1 text-sm">
            <div className="text-text-3">基金代码</div>
            <div className="font-mono font-bold">{candidate.fund_code}</div>
            <div className="text-text-3">基金名称</div>
            <div className="font-medium">{fmtText(candidate.fund_name)}</div>
            <div className="text-text-3">档内排名</div>
            <div className="font-medium">{candidate.priority_rank ?? "-"}</div>
          </div>
        </div>

        {/* 稳定原因码 */}
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-text-2 m-0 mb-2">
            稳定原因码
          </h3>
          {candidate.priority_reasons.length > 0 ? (
            <ul className="m-0 pl-5 text-xs space-y-0.5">
              {candidate.priority_reasons.map((r, i) => (
                <li key={`${r.code}-${i}`}>
                  <strong className="font-semibold">{reasonLabel(r.code)}</strong>
                  {r.message && (
                    <span className="text-text-3 ml-1.5">· {r.message}</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-xs text-text-3">无</span>
          )}
        </div>

        {/* 排除原因码（如有） */}
        {candidate.exclusion_reasons.length > 0 && (
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-neg-text m-0 mb-2">
              排除原因码
            </h3>
            <ul className="m-0 pl-5 text-xs space-y-0.5 text-neg-text">
              {candidate.exclusion_reasons.map((r, i) => (
                <li key={`${r.code}-${i}`}>
                  <strong className="font-semibold">{reasonLabel(r.code)}</strong>
                  {r.message && (
                    <span className="text-text-3 ml-1.5">· {r.message}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 关键指标 */}
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-text-2 m-0 mb-2">
            关键指标
          </h3>
          <div className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">
            <div className="text-text-3">真实目标持仓</div>
            <div className="font-mono tabular-nums">
              {fmtWeight(candidate.matched_holding_weight)}
            </div>
            <div className="text-text-3">已披露持仓</div>
            <div className="font-mono tabular-nums">
              {fmtWeight(candidate.disclosed_holding_weight)}
            </div>
            <div className="text-text-3">归一化匹配率</div>
            <div className="font-mono tabular-nums">
              {fmtWeight(candidate.normalized_match_pct)}
            </div>
            <div className="text-text-3">适配分</div>
            <div className="font-mono tabular-nums">{fmtScore(candidate.fit_score)}</div>
            <div className="text-text-3">证据分</div>
            <div className="font-mono tabular-nums">
              {fmtScore(candidate.evidence_score)}
            </div>
          </div>
        </div>

        {/* 持仓报告日期 */}
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-text-2 m-0 mb-2">
            持仓报告日期
          </h3>
          <div className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">
            <div className="text-text-3">报告日期</div>
            <div className="font-medium">{fmtText(candidate.holding_report_date)}</div>
          </div>
        </div>

        {/* 状态信息 */}
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-text-2 m-0 mb-2">
            状态信息
          </h3>
          <div className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">
            <div className="text-text-3">数据质量</div>
            <div className="font-medium">{fmtText(candidate.data_quality_status)}</div>
            <div className="text-text-3">估值状态</div>
            <div className="font-medium">{fmtText(candidate.valuation_status)}</div>
            <div className="text-text-3">持仓真实度</div>
            <div className="font-medium">{fmtText(candidate.holdings_truth_status)}</div>
            <div className="text-text-3">资格状态</div>
            <div className="font-medium">{fmtText(candidate.eligibility_status)}</div>
          </div>
        </div>
      </div>
    </Card>
  );
}
