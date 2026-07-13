import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchPriorityRun,
  fetchPriorityRunsByThesis,
  type PriorityCandidate,
  type PriorityRunDetail,
  type PriorityRunSummary,
} from "../api";

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

// 百分比格式化：已是 0-100，保留1位小数
function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `${v.toFixed(1)}%`;
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
  const [runId, setRunId] = useState(searchParams.get("run") || "");
  const [runInput, setRunInput] = useState("");
  const [detail, setDetail] = useState<PriorityRunDetail | null>(null);
  const [historyRuns, setHistoryRuns] = useState<PriorityRunSummary[]>([]);
  const [selectedResultId, setSelectedResultId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // 加载 PriorityRun 详情
  useEffect(() => {
    if (!runId) {
      setDetail(null);
      setHistoryRuns([]);
      setSelectedResultId("");
      return;
    }
    setLoading(true);
    setError(null);
    fetchPriorityRun(runId)
      .then((data) => {
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
        setDetail(null);
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setLoading(false));
  }, [runId]);

  // 加载同 Thesis 的历史运行列表
  useEffect(() => {
    if (!detail?.thesis_id) {
      setHistoryRuns([]);
      return;
    }
    fetchPriorityRunsByThesis(detail.thesis_id)
      .then((runs) => setHistoryRuns(runs))
      .catch(() => setHistoryRuns([]));
  }, [detail?.thesis_id]);

  // 同步 runId 到 URL 参数
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (runId) next.set("run", runId);
    else next.delete("run");
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  // 手动输入加载
  const handleLoadInput = () => {
    const trimmed = runInput.trim();
    if (trimmed) setRunId(trimmed);
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

  // 没有 run 参数时，显示输入入口
  if (!runId) {
    return (
      <div>
        <div className="card">
          <h2>投资假设详情 / 基金研究优先级</h2>
          <p className="muted" style={{ marginBottom: 12 }}>
            请输入 PriorityRun ID 加载工作台，或通过 URL 参数 ?run=xxx 直接访问。
          </p>
          <div className="toolbar">
            <input
              style={{ flex: "0 0 320px" }}
              placeholder="输入 priority_run_id"
              value={runInput}
              onChange={(e) => setRunInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLoadInput();
              }}
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
      {/* 错误提示 */}
      {error && <div className="alert alert-warn">{error}</div>}
      {loading && <div className="alert alert-info">加载中...</div>}

      {/* 顶部信息条 */}
      {detail && (
        <div className="card" style={{ padding: 12, marginBottom: 12 }}>
          <div
            className="kv"
            style={{ gridTemplateColumns: "140px 1fr 140px 1fr" }}
          >
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
            <dt>评估候选数</dt>
            <dd>{detail.evaluated_candidate_count}</dd>
            <dt>合格候选数</dt>
            <dd>{detail.eligible_candidate_count}</dd>
          </div>

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
            onChange={(e) => setRunId(e.target.value)}
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
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) 360px",
            gap: 12,
            alignItems: "start",
          }}
        >
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
                    <table>
                      <thead>
                        <tr>
                          <th style={{ width: 56 }}>档内排名</th>
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
                            onClick={() => setSelectedResultId(c.priority_result_id)}
                            style={{
                              cursor: "pointer",
                              background:
                                selectedResultId === c.priority_result_id
                                  ? "var(--accent-soft)"
                                  : undefined,
                            }}
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
                  )}
                </div>
              );
            })}
          </div>

          {/* 右侧：选中基金详情侧栏 */}
          <div
            style={{
              position: "sticky",
              top: 8,
              maxHeight: "calc(100vh - 16px)",
              overflow: "auto",
            }}
          >
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
          {fmtPct(candidate.normalized_match_pct)}
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
