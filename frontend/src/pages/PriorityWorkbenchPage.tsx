import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchPriorityRun,
  fetchPriorityRunsByThesis,
  type PriorityCandidate,
  type PriorityRunDetail,
  type PriorityRunSummary,
} from "../api";

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
];

// 五档标签配置：中文标签 + 配色
const TIER_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  research_now: { label: "立即研究", color: "var(--pos-text)", bg: "var(--pos-soft)" },
  research_next: { label: "下一步研究", color: "var(--accent-text)", bg: "var(--accent-soft)" },
  valuation_watch: { label: "估值观察", color: "var(--warn-text)", bg: "var(--warn-soft)" },
  data_insufficient: { label: "数据不足", color: "var(--text-2)", bg: "var(--surface-2)" },
  excluded: { label: "排除", color: "var(--neg-text)", bg: "var(--neg-soft)" },
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
      <div>
        <div className="card">
          <h2>投资假设详情 / 基金研究优先级</h2>
          {error && (
            <div className="alert alert-warn" style={{ marginBottom: 12 }} role="alert">
              {error}
              <button
                className="secondary"
                style={{ marginLeft: 12, fontSize: 11.5 }}
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
          <p className="muted" style={{ marginBottom: 12 }}>
            请输入 PriorityRun ID 加载工作台，或通过 URL 参数 ?run=xxx 直接访问。
          </p>
          <div className="toolbar">
            <label htmlFor="priority-run-input" style={{ fontSize: 12.5, color: "var(--text-2)" }}>
              PriorityRun ID
            </label>
            <input
              id="priority-run-input"
              style={{ flex: "0 0 320px" }}
              placeholder="输入 priority_run_id"
              value={runInput}
              onChange={(e) => setRunInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLoadInput();
              }}
              aria-label="PriorityRun ID 输入框"
            />
            <button onClick={handleLoadInput} disabled={!runInput.trim()}>
              加载
            </button>
          </div>
          <p className="muted" style={{ fontSize: 11, marginTop: 8 }}>
            免责声明：研究顺序，不是买入建议。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* 加载提示 */}
      {!error && loading && (
        <div className="alert alert-info" role="status" aria-live="polite">
          加载中...
        </div>
      )}

      {/* 顶部信息条 */}
      {detail && (
        <div className="card" style={{ padding: 12, marginBottom: 12 }}>
          {/* 投资假设原文 */}
          {detail.thesis && (
            <div style={{ marginBottom: 14 }}>
              <h2 style={{ margin: "0 0 6px" }}>{detail.thesis.title || "投资假设"}</h2>
              <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
                {detail.thesis.belief_statement}
              </p>
              {/* 研究请求原文 */}
              {detail.research_input?.raw_text && (
                <div
                  style={{
                    padding: "8px 10px",
                    background: "var(--surface-2)",
                    borderRadius: "var(--r-s)",
                    fontSize: 12,
                    color: "var(--text-3)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <strong style={{ color: "var(--text-2)" }}>研究请求：</strong>
                  {detail.research_input.raw_text}
                </div>
              )}
            </div>
          )}

          {/* 元数据网格 */}
          <div className="kv priority-meta-grid">
            <dt>Thesis ID</dt>
            <dd style={{ fontFamily: "ui-monospace, monospace" }}>
              {fmtText(detail.thesis_id)}
            </dd>
            <dt>Strategy Policy</dt>
            <dd style={{ fontFamily: "ui-monospace, monospace" }}>
              {fmtText(detail.strategy_policy_id)} (v{detail.strategy_policy_version})
            </dd>
            <dt>Data Snapshot</dt>
            <dd style={{ fontFamily: "ui-monospace, monospace" }}>
              {fmtText(detail.data_snapshot_id)}
            </dd>
            <dt>Ranking Method</dt>
            <dd style={{ fontFamily: "ui-monospace, monospace" }}>
              {fmtText(detail.ranking_method_version)}
            </dd>
            <dt>PriorityRun ID</dt>
            <dd style={{ fontFamily: "ui-monospace, monospace", fontSize: 11.5 }}>
              {fmtText(detail.priority_run_id)}
            </dd>
            <dt>CandidateSet ID</dt>
            <dd style={{ fontFamily: "ui-monospace, monospace", fontSize: 11.5 }}>
              {fmtText(detail.candidate_set_id)}
            </dd>
            <dt>创建人</dt>
            <dd>{fmtText(detail.created_by)}</dd>
            <dt>创建时间</dt>
            <dd>{detail.created_at?.slice(0, 19).replace("T", " ") || "-"}</dd>
          </div>

          {/* 投资假设状态条 */}
          {detail.thesis && (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 12,
                marginTop: 10,
                fontSize: 12,
                color: "var(--text-2)",
              }}
            >
              {detail.thesis.status && (
                <span>
                  状态：<strong>{THESIS_STATUS_LABELS[detail.thesis.status] ?? detail.thesis.status}</strong>
                </span>
              )}
              {detail.thesis.time_horizon && (
                <span>时间范围：<strong>{detail.thesis.time_horizon}</strong></span>
              )}
              {detail.thesis.owner && (
                <span>研究员：<strong>{detail.thesis.owner}</strong></span>
              )}
              {detail.thesis.as_of_date && (
                <span>截止日期：<strong>{detail.thesis.as_of_date}</strong></span>
              )}
              {detail.thesis.next_review_at && (
                <span>下次复审：<strong>{detail.thesis.next_review_at.slice(0, 10)}</strong></span>
              )}
              {detail.research_input && (
                <span>
                  来源：<strong>{REQUEST_SOURCE_LABELS[detail.research_input.request_source] ?? detail.research_input.request_source}</strong>
                </span>
              )}
            </div>
          )}

          {/* 候选集统计 */}
          {detail.candidate_set_header && (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 16,
                marginTop: 10,
                padding: "8px 12px",
                background: "var(--surface-2)",
                borderRadius: "var(--r-s)",
                fontSize: 12,
              }}
            >
              <span>扫描基金：<strong>{detail.candidate_set_header.scanned_fund_count}</strong></span>
              <span>映射候选：<strong>{detail.candidate_set_header.mapped_candidate_count}</strong></span>
              <span>数据不足：<strong>{detail.candidate_set_header.unmapped_due_to_data_count}</strong></span>
              <span>不相关：<strong>{detail.candidate_set_header.unrelated_fund_count}</strong></span>
              <span className="muted">
                Source: {detail.candidate_set_header.source_method_version}
              </span>
            </div>
          )}

          {/* 失效条件 */}
          {detail.thesis?.invalidation_conditions &&
            Array.isArray(detail.thesis.invalidation_conditions) &&
            detail.thesis.invalidation_conditions.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <h3 style={{ margin: "0 0 4px", color: "var(--neg-text)" }}>失效条件</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-2)" }}>
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
              <div style={{ marginTop: 10 }}>
                <h3 style={{ margin: "0 0 4px", color: "var(--pos-text)" }}>支持证据</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-2)" }}>
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
              <div style={{ marginTop: 10 }}>
                <h3 style={{ margin: "0 0 4px", color: "var(--warn-text)" }}>反对证据</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-2)" }}>
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
              <div style={{ marginTop: 10 }}>
                <h3 style={{ margin: "0 0 4px", color: "var(--accent-text)" }}>催化剂</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-2)" }}>
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
              <div style={{ marginTop: 10 }}>
                <h3 style={{ margin: "0 0 4px" }}>关键指标</h3>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-2)" }}>
                  {detail.thesis.key_metrics.map((c, i) => (
                    <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                  ))}
                </ul>
              </div>
            )}

          {/* 非生产警告条 */}
          {!detail.approved_for_production && (
            <div
              style={{
                marginTop: 10,
                padding: "8px 12px",
                borderRadius: "var(--r-s)",
                background: "var(--neg-soft)",
                color: "var(--neg-text)",
                fontWeight: 700,
                fontSize: 12.5,
                border: "1px solid var(--neg)",
              }}
            >
              非生产：该 PriorityRun 尚未批准用于生产环境，结果仅供研究参考。
            </div>
          )}

          {/* 免责声明 */}
          <div className="muted" style={{ marginTop: 8, fontSize: 11.5 }}>
            免责声明：研究顺序，不是买入建议。
          </div>
        </div>
      )}

      {/* 历史运行选择器 */}
      {detail && (
        <div className="toolbar" style={{ marginBottom: 12 }}>
          <label>历史运行</label>
          <select
            value={runId}
            onChange={(e) => handleRunChange(e.target.value)}
            style={{ minWidth: 280 }}
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
          <span className="muted" style={{ fontSize: 11.5 }}>
            共 {historyRuns.length} 个历史运行
          </span>
        </div>
      )}

      {/* 主区：五档基金列表 + 侧栏 */}
      {detail && (
        <div className="priority-layout">
          {/* 左侧：五档基金列表 */}
          <div>
            {TIER_ORDER.map((tier) => {
              const config = TIER_CONFIG[tier];
              const candidates = detail.candidates_by_tier?.[tier] ?? [];
              const count = detail.tier_counts?.[tier] ?? candidates.length;
              return (
                <div className="card" key={tier} style={{ marginBottom: 12 }}>
                  {/* 档位标题 + 数量 */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: candidates.length > 0 ? 10 : 0,
                    }}
                  >
                    <span
                      className="badge"
                      style={{
                        background: config.bg,
                        color: config.color,
                        fontSize: 11.5,
                        padding: "2px 8px",
                      }}
                    >
                      {config.label}
                    </span>
                    <span className="muted" style={{ fontSize: 11.5 }}>
                      {count} 只
                    </span>
                  </div>

                  {/* 基金表格（空档位不显示表格） */}
                  {candidates.length > 0 && (
                    <div className="priority-table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th className="num" style={{ width: 56 }}>档内排名</th>
                            <th style={{ width: 90 }}>基金代码</th>
                            <th>基金名称</th>
                            <th className="num" style={{ width: 100 }}>
                              真实目标持仓
                            </th>
                            <th className="num" style={{ width: 80 }}>
                              披露覆盖
                            </th>
                            <th style={{ width: 90 }}>数据质量</th>
                            <th style={{ width: 90 }}>估值状态</th>
                            <th className="num" style={{ width: 70 }}>
                              证据分
                            </th>
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
                              className={
                                selectedResultId === c.priority_result_id
                                  ? "priority-row-selected priority-row-focus"
                                  : "priority-row-focus"
                              }
                              style={{ cursor: "pointer" }}
                            >
                              <td className="num">{c.priority_rank ?? "-"}</td>
                              <td
                                style={{
                                  fontFamily: "ui-monospace, monospace",
                                  fontWeight: 700,
                                }}
                              >
                                {c.fund_code}
                              </td>
                              <td style={{ color: "var(--text-2)" }}>
                                {fmtText(c.fund_name)}
                              </td>
                              <td className="num">
                                {fmtWeight(c.matched_holding_weight)}
                              </td>
                              <td className="num">
                                {fmtWeight(c.disclosed_holding_weight)}
                              </td>
                              <td>{fmtText(c.data_quality_status)}</td>
                              <td>{fmtText(c.valuation_status)}</td>
                              <td className="num">{fmtScore(c.evidence_score)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* 右侧：选中基金详情侧栏 */}
          <div className="priority-sidebar">
            {selectedCandidate ? (
              <CandidateDetail candidate={selectedCandidate} />
            ) : (
              <div className="card">
                <h2>选中基金详情</h2>
                <p className="muted">点击左侧基金行查看详情。</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// 选中基金详情侧栏
function CandidateDetail({ candidate }: { candidate: PriorityCandidate }) {
  const config = TIER_CONFIG[candidate.priority_tier] ?? {
    label: candidate.priority_tier,
    color: "var(--text-2)",
    bg: "var(--surface-2)",
  };

  return (
    <div className="card">
      <h2>基金详情</h2>

      {/* 基本信息 */}
      <h3>基本信息</h3>
      <div className="kv">
        <dt>基金代码</dt>
        <dd style={{ fontFamily: "ui-monospace, monospace", fontWeight: 700 }}>
          {candidate.fund_code}
        </dd>
        <dt>基金名称</dt>
        <dd>{fmtText(candidate.fund_name)}</dd>
        <dt>档位</dt>
        <dd>
          <span
            className="badge"
            style={{
              background: config.bg,
              color: config.color,
              fontSize: 11.5,
              padding: "2px 8px",
            }}
          >
            {config.label}
          </span>
        </dd>
        <dt>档内排名</dt>
        <dd>{candidate.priority_rank ?? "-"}</dd>
      </div>

      {/* 稳定原因码 */}
      <h3>稳定原因码</h3>
      {candidate.priority_reasons.length > 0 ? (
        <ul style={{ margin: "4px 0", paddingLeft: 18, fontSize: 12.5 }}>
          {candidate.priority_reasons.map((r, i) => (
            <li key={`${r.code}-${i}`} style={{ marginBottom: 2 }}>
              <strong>{reasonLabel(r.code)}</strong>
              {r.message && (
                <span className="muted" style={{ marginLeft: 6 }}>
                  · {r.message}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <span className="muted">无</span>
      )}

      {/* 排除原因码（如有） */}
      {candidate.exclusion_reasons.length > 0 && (
        <>
          <h3>排除原因码</h3>
          <ul
            style={{
              margin: "4px 0",
              paddingLeft: 18,
              fontSize: 12.5,
              color: "var(--neg-text)",
            }}
          >
            {candidate.exclusion_reasons.map((r, i) => (
              <li key={`${r.code}-${i}`} style={{ marginBottom: 2 }}>
                <strong>{reasonLabel(r.code)}</strong>
                {r.message && (
                  <span className="muted" style={{ marginLeft: 6 }}>
                    · {r.message}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {/* 关键指标 */}
      <h3>关键指标</h3>
      <div className="kv">
        <dt>真实目标持仓</dt>
        <dd style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtWeight(candidate.matched_holding_weight)}
        </dd>
        <dt>已披露持仓</dt>
        <dd style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtWeight(candidate.disclosed_holding_weight)}
        </dd>
        <dt>归一化匹配率</dt>
        <dd style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtWeight(candidate.normalized_match_pct)}
        </dd>
        <dt>适配分</dt>
        <dd style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtScore(candidate.fit_score)}
        </dd>
        <dt>证据分</dt>
        <dd style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtScore(candidate.evidence_score)}
        </dd>
      </div>

      {/* 持仓报告日期 */}
      <h3>持仓报告日期</h3>
      <div className="kv">
        <dt>报告日期</dt>
        <dd>{fmtText(candidate.holding_report_date)}</dd>
      </div>

      {/* 状态信息 */}
      <h3>状态信息</h3>
      <div className="kv">
        <dt>数据质量</dt>
        <dd>{fmtText(candidate.data_quality_status)}</dd>
        <dt>估值状态</dt>
        <dd>{fmtText(candidate.valuation_status)}</dd>
        <dt>持仓真实度</dt>
        <dd>{fmtText(candidate.holdings_truth_status)}</dd>
        <dt>资格状态</dt>
        <dd>{fmtText(candidate.eligibility_status)}</dd>
      </div>
    </div>
  );
}
