import { Link, useParams } from "react-router-dom";
import {
  downloadFile,
  fetchLabelChanges,
  fetchRun,
  fetchRunStyle,
  fetchRunSummary,
} from "../api";
import { useAsync, runStatusLabel } from "../components";

const CATEGORY_LABELS: Record<string, string> = {
  data_quality: "数据质量",
  return_risk: "收益风险",
  holding: "持仓结构",
  holding_style: "持仓风格",
  relative_benchmark: "相对基准",
  manager: "基金经理",
  fee: "费率",
  fund_size: "规模",
  review: "复核",
  description: "描述性",
};

function statusPillClass(status: string): "is-go" | "is-watch" | "is-block" | "" {
  if (status === "succeeded") return "is-go";
  if (status === "running") return "is-watch";
  if (status === "failed" || status === "partial") return "is-block";
  return "";
}

function changeTypeDelta(type: string): { label: string; cls: string } {
  if (type === "added") return { label: "新增", cls: "delta-pos" };
  if (type === "removed") return { label: "消失", cls: "delta-neg" };
  if (type === "status_changed") return { label: "状态变更", cls: "delta-zero" };
  return { label: type, cls: "" };
}

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const { data, error, loading } = useAsync(() => fetchRun(runId), [runId]);
  const { data: summary } = useAsync(() => fetchRunSummary(runId), [runId]);
  const { data: style } = useAsync(() => fetchRunStyle(runId), [runId]);
  const { data: labelChanges } = useAsync(
    () => fetchLabelChanges(runId),
    [runId]
  );

  const successRate =
    data && data.fund_codes.length > 0
      ? Math.round(
          ((data.fund_codes.length - (data.failure_count ?? 0)) /
            data.fund_codes.length) *
            100
        )
      : 0;

  return (
    <div>
      {/* 页面标题 */}
      <div className="page-head-v2">
        <div>
          <span className="eyebrow">OPS · 批次详情</span>
          <h1>批次详情与审计</h1>
          <p>
            单次跑批的完整快照：处理结果、失败原因、风格分布、相对上次的变化、规则快照。
            适合运维追溯和研究员复盘。
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
          <div className="flow-steps">
            <span className="flow-step is-done">
              <span className="step-num">✓</span>批次完成
            </span>
            <span className="flow-arrow">→</span>
            <span className="flow-step is-current">审计</span>
            <span className="flow-arrow">→</span>
            <span className="flow-step">导出</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="secondary"
              onClick={() =>
                downloadFile(`/v1/runs/${runId}/export?format=xlsx`, `run_${runId}.xlsx`)
              }
            >
              导出 XLSX
            </button>
            <button
              className="secondary"
              onClick={() =>
                downloadFile(`/v1/runs/${runId}/export?format=csv`, `run_${runId}.zip`)
              }
            >
              导出 CSV
            </button>
          </div>
        </div>
      </div>

      {/* 上下文栏 */}
      <div className="context-bar">
        <div className="chip chip-mono">
          <span className="label">Run ID</span>
          <span className="value">{runId.slice(0, 12)}…</span>
        </div>
        {data && (
          <>
            <div className={`chip chip-status ${data.status === "succeeded" ? "" : "is-stale"}`}>
              <span className="dot" />
              <span className="label">状态</span>
              <span className="value">{runStatusLabel(data.status)}</span>
            </div>
            <div className="chip">
              <span className="label">规则版本</span>
              <span className="value">{data.rule_version}</span>
            </div>
            <div className="chip">
              <span className="label">开始时间</span>
              <span className="value">{data.run_at}</span>
            </div>
          </>
        )}
        <div className="spacer" />
        <Link to="/runs" className="link-btn" style={{ fontSize: 12 }}>
          批次列表 →
        </Link>
      </div>

      {loading && (
        <div className="filter-empty" style={{ marginBottom: 12 }}>
          加载中…
        </div>
      )}
      {error && <div className="alert alert-warn">{error}</div>}

      {/* 顶部决策摘要 */}
      {data && (
        <div className="decision-card">
          <span className={`verdict ${statusPillClass(data.status) ? `is-${statusPillClass(data.status).replace("is-", "")}` : "is-info"}`}>
            {data.status === "succeeded" ? "OK" : data.status === "running" ? "RUN" : "ATTN"}
          </span>
          <div className="takeaway">
            批次 <strong>{runId.slice(0, 8)}</strong> 处理{" "}
            <strong>{data.fund_codes.length}</strong> 只基金，失败{" "}
            <strong>{data.failure_count ?? 0}</strong> 只，成功率{" "}
            <strong>{successRate}%</strong>。风格命中率{" "}
            <strong>
              {style
                ? Object.values(style.styles).reduce((s, v) => s + v.count, 0)
                : "—"}
            </strong>{" "}
            条标签。
            {labelChanges && labelChanges.summary.risk_warnings > 0 && (
              <>
                {" "}
                <strong>本次 {labelChanges.summary.risk_warnings} 项风险预警</strong>，需研究员复盘。
              </>
            )}
          </div>
          <div className="actions">
            <Link to="/diff" className="secondary">
              对比上次
            </Link>
            <Link to="/review-queue" className="primary">
              进入复核
            </Link>
          </div>
        </div>
      )}

      {/* 核心指标卡 */}
      {summary && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 10,
            marginBottom: 16,
          }}
        >
          <div className="metric-card-v2 is-pos">
            <div className="label">已处理</div>
            <div className="value">{summary.counts.processed}</div>
            <div className="sub">完成计算</div>
          </div>
          <div className="metric-card-v2 is-neg">
            <div className="label">失败</div>
            <div className="value">{summary.counts.failed}</div>
            <div className="sub">需关注</div>
          </div>
          <div className="metric-card-v2 is-warn">
            <div className="label">数据不足</div>
            <div className="value">{summary.counts.data_insufficient}</div>
            <div className="sub">影响 gate</div>
          </div>
          <div className="metric-card-v2 is-warn">
            <div className="label">需人工复核</div>
            <div className="value">{summary.counts.manual_review}</div>
            <div className="sub">已加队列</div>
          </div>
          <div className="metric-card-v2">
            <div className="label">收益窗口不足</div>
            <div className="value">{summary.counts.return_window_insufficient}</div>
            <div className="sub">需拉取更长 NAV</div>
          </div>
        </div>
      )}

      {/* 批次摘要 + 标签分布 */}
      {summary && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="section-head">
            <h2>标签命中分布 TOP 10</h2>
            <div className="meta">按命中基金数排序</div>
          </div>
          <table className="table-v2">
            <thead>
              <tr>
                <th>标签</th>
                <th>分类</th>
                <th className="num">命中基金数</th>
              </tr>
            </thead>
            <tbody>
              {summary.label_distribution.slice(0, 10).map((row) => (
                <tr key={row.label_code}>
                  <td>
                    <strong>{row.label_name}</strong>
                  </td>
                  <td className="muted">{CATEGORY_LABELS[row.category] ?? row.category}</td>
                  <td className="num">{row.fund_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 风格分布 */}
      {style && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="section-head">
            <h2>风格分布</h2>
            <div className="meta">
              基于股票因子聚合 · 规则版本 <code>{style.rule_version}</code>
            </div>
          </div>
          <table className="table-v2">
            <thead>
              <tr>
                <th>风格</th>
                <th className="num">命中基金数</th>
                <th>示例基金</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(style.styles).map(([code, info]) => (
                <tr key={code}>
                  <td>
                    <code>{code}</code>
                  </td>
                  <td className="num">{info.count}</td>
                  <td className="muted">
                    {info.funds.slice(0, 5).join(", ")}
                    {info.funds.length > 5 ? ` … (+${info.funds.length - 5})` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="filter-empty" style={{ marginTop: 10 }}>
            未出风格：缺少股票因子{" "}
            <strong>{style.boundary_counts.stock_factors_missing}</strong>；
            因子存在但未达任何阈值{" "}
            <strong>{style.boundary_counts.style_pending_rule_definition}</strong>
          </div>
        </div>
      )}

      {/* 标签变化 */}
      {labelChanges && labelChanges.summary.total > 0 && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="section-head">
            <h2>
              标签变化
              {labelChanges.summary.risk_warnings > 0 && (
                <span
                  className="status-pill is-block"
                  style={{ marginLeft: 8 }}
                  title="风险标签从非 active 变为 active"
                >
                  <span className="pulse" />
                  {labelChanges.summary.risk_warnings} 项风险预警
                </span>
              )}
            </h2>
            <div className="meta">相对上一次成功批次</div>
          </div>
          <div style={{ display: "flex", gap: 12, marginBottom: 10, flexWrap: "wrap" }}>
            {Object.entries(labelChanges.summary.by_type).map(([type, count]) => {
              const d = changeTypeDelta(type);
              return (
                <span key={type} style={{ fontSize: 12 }}>
                  <span className={d.cls}>{d.label}</span>{" "}
                  <strong style={{ fontVariantNumeric: "tabular-nums" }}>{count as number}</strong>
                </span>
              );
            })}
          </div>
          {labelChanges.changes.filter((c) => c.is_risk_warning).length > 0 && (
            <details open>
              <summary style={{ cursor: "pointer", fontWeight: 700, padding: "6px 0" }}>
                风险预警详情（{labelChanges.changes.filter((c) => c.is_risk_warning).length}）
              </summary>
              <table className="table-v2">
                <thead>
                  <tr>
                    <th>基金</th>
                    <th>风险标签</th>
                    <th>状态变化</th>
                  </tr>
                </thead>
                <tbody>
                  {labelChanges.changes
                    .filter((c) => c.is_risk_warning)
                    .slice(0, 50)
                    .map((c, i) => (
                      <tr key={`${c.fund_code}-${c.label_code}-${i}`}>
                        <td>
                          <Link to={`/runs/${runId}/funds/${c.fund_code}`}>
                            <code>{c.fund_code}</code>
                          </Link>
                        </td>
                        <td>
                          <code>{c.label_code}</code>
                        </td>
                        <td>
                          <span className="muted">{c.previous_status || "无"}</span>
                          {" → "}
                          <strong>{c.current_status || "无"}</strong>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </details>
          )}
        </div>
      )}

      {/* 失败记录 */}
      {data && data.failures && data.failures.length > 0 && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="section-head">
            <h2>
              失败记录
              <span className="status-pill is-block" style={{ marginLeft: 8 }}>
                <span className="pulse" />
                {data.failures.length} 项
              </span>
            </h2>
            <div className="meta">本批次隔离的失败项，不影响其它基金</div>
          </div>
          <table className="table-v2">
            <thead>
              <tr>
                <th>基金</th>
                <th>阶段</th>
                <th>错误类型</th>
                <th>消息</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {data.failures.map((f, i) => (
                <tr key={`${f.fund_code}-${i}`}>
                  <td>
                    <code>{f.fund_code}</code>
                  </td>
                  <td>{f.stage}</td>
                  <td>{f.error_type}</td>
                  <td className="muted">{f.message}</td>
                  <td>{f.recorded_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 规则快照 */}
      {data && data.rule_snapshot && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div className="section-head">
            <h2>规则快照</h2>
            <div className="meta">
              本次使用的全部阈值参数 · 规则版本 {data.rule_version}
            </div>
          </div>
          <table className="table-v2">
            <thead>
              <tr>
                <th>参数</th>
                <th>值</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.rule_snapshot).map(([k, v]) => (
                <tr key={k}>
                  <td>
                    <code>{k}</code>
                  </td>
                  <td>{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 基金列表 */}
      {data && (
        <div className="card">
          <div className="section-head">
            <h2>基金列表</h2>
            <div className="meta">共 {data.fund_codes.length} 只</div>
          </div>
          {data.fund_codes.length === 0 ? (
            <div className="empty-state">
              <div className="icon">∅</div>
              <div className="title">本批次没有处理任何基金</div>
            </div>
          ) : (
            <table className="table-v2">
              <thead>
                <tr>
                  <th>基金代码</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.fund_codes.map((code) => (
                  <tr key={code}>
                    <td>
                      <code>{code}</code>
                    </td>
                    <td className="num">
                      <Link to={`/runs/${runId}/funds/${code}`}>查看报告 →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
