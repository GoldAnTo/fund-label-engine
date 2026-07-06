import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchRelativeEligibility,
  fetchRuns,
  fetchRunSummary,
  fetchPortfolioMatrix,
  fetchTopFunds,
  type RelativeEligibilityResponse,
  type RunSummary,
  type PortfolioMatrixResponse,
  type TopFundsResponse,
  type RelativeEligibilityRow as EligibilityRow,
} from "../api";
import { ALL_STYLE_CODES, styleTagClass, styleName } from "../styleConfig";

const STATUS_LABELS: Record<string, string> = {
  relative_label_ready: "可展示",
  relative_label_ready_approx: "可展示（近似）",
  benchmark_source_missing: "缺基准源",
  benchmark_mapping_required: "需确认映射",
  benchmark_unresolved: "组件未解析",
  benchmark_missing: "未配置基准",
  nav_window_insufficient: "收益窗口不足",
};

type Verdict = "go" | "watch" | "block" | "info";

function statusLabel(value: string) {
  return STATUS_LABELS[value] ?? value;
}

function statusVerdict(value: string): Verdict {
  if (value === "relative_label_ready" || value === "relative_label_ready_approx") return "go";
  if (value === "nav_window_insufficient" || value === "benchmark_source_missing") return "watch";
  return "block";
}

function StatusPill({ status }: { status: string }) {
  const verdict = statusVerdict(status);
  return (
    <span className={`status-pill is-${verdict}`}>
      <span className="pulse" />
      {statusLabel(status)}
    </span>
  );
}

type StatusFilter = "all" | "ready" | "blocked" | "missing-source" | "mapping-required";

const FILTER_OPTIONS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "ready", label: "可展示" },
  { key: "blocked", label: "不可展示" },
  { key: "missing-source", label: "缺基准源" },
  { key: "mapping-required", label: "需确认映射" },
];

function statusFilterMatches(row: EligibilityRow, filter: StatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "ready")
    return (
      row.relative_label_status === "relative_label_ready" ||
      row.relative_label_status === "relative_label_ready_approx"
    );
  if (filter === "blocked")
    return !(
      row.relative_label_status === "relative_label_ready" ||
      row.relative_label_status === "relative_label_ready_approx"
    );
  if (filter === "missing-source") return row.relative_label_status === "benchmark_source_missing";
  if (filter === "mapping-required") return row.relative_label_status === "benchmark_mapping_required";
  return true;
}

export default function ReadyPoolPage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [eligibility, setEligibility] = useState<RelativeEligibilityResponse | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [matrix, setMatrix] = useState<PortfolioMatrixResponse | null>(null);
  const [topFundsByStyle, setTopFundsByStyle] = useState<Record<string, TopFundsResponse>>({});
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");
  const [groupBy, setGroupBy] = useState<"none" | "style">("none");

  useEffect(() => {
    fetchRuns()
      .then((rs) => {
        setRuns(rs);
        if (rs.length > 0) setRunId(rs[0].run_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!runId) return;
    setError(null);
    Promise.all([
      fetchRelativeEligibility(runId, "all"),
      fetchRunSummary(runId),
      fetchPortfolioMatrix(runId),
    ])
      .then(([elig, summ, mat]) => {
        setEligibility(elig);
        setSummary(summ);
        setMatrix(mat);
      })
      .catch((e) => setError(e.message));

    const topStyles = ["quality_growth", "large_cap", "high_valuation", "low_valuation"];
    const requests = topStyles.map((s) =>
      fetchTopFunds(runId, s, "annualized_return_1y", 5)
        .then((resp) => [s, resp] as const)
        .catch(() => [s, null] as const)
    );
    Promise.all(requests).then((results) => {
      const map: Record<string, TopFundsResponse> = {};
      for (const [s, resp] of results) {
        if (resp) map[s] = resp;
      }
      setTopFundsByStyle(map);
    });
  }, [runId]);

  const styleDistribution = useMemo(() => {
    if (!summary) return [];
    return summary.label_distribution
      .filter((d) => ALL_STYLE_CODES.has(d.label_code) && d.label_code !== "style_pending_rule_definition")
      .sort((a, b) => b.fund_count - a.fund_count);
  }, [summary]);

  const fundStyleMap = useMemo(() => {
    if (!matrix) return new Map<string, string[]>();
    const m = new Map<string, string[]>();
    for (const row of matrix.rows) {
      m.set(
        row.fund_code,
        (row.style_tags || []).filter(
          (t) => ALL_STYLE_CODES.has(t) && t !== "style_pending_rule_definition"
        )
      );
    }
    return m;
  }, [matrix]);

  const totalFunds = eligibility?.total_funds ?? 142;
  const readyCount = eligibility?.ready_count ?? 0;
  const blockedCount = eligibility?.blocked_count ?? 0;
  const fundsWithStyle = Array.from(fundStyleMap.values()).filter((tags) => tags.length > 0).length;
  const coveragePct = totalFunds > 0 ? Math.round((readyCount / totalFunds) * 100) : 0;

  // 代理口径说明 banner：当大量基金因 nav_window_insufficient 被屏蔽时给出提示
  // 当前 dea77b0f run 下 5/142 ready + 137 nav_window_insufficient
  const showProxyCaliberBanner =
    eligibility !== null &&
    readyCount > 0 &&
    blockedCount > 0 &&
    totalFunds > 0 &&
    readyCount / totalFunds < 0.1;

  // 主列表过滤
  const filteredRows = useMemo(() => {
    if (!eligibility) return [];
    const q = query.trim().toLowerCase();
    return eligibility.results.filter((row) => {
      if (!statusFilterMatches(row, statusFilter)) return false;
      if (!q) return true;
      return (
        row.fund_code.toLowerCase().includes(q) ||
        row.fund_name.toLowerCase().includes(q)
      );
    });
  }, [eligibility, statusFilter, query]);

  // 按风格分组（当 groupBy=style 时）
  const rowsByStyle = useMemo(() => {
    if (groupBy !== "style") return null;
    const grouped: Record<string, EligibilityRow[]> = {};
    for (const row of filteredRows) {
      const tags = fundStyleMap.get(row.fund_code) || [];
      if (tags.length === 0) {
        (grouped["未分类"] ??= []).push(row);
        continue;
      }
      for (const t of tags) {
        (grouped[t] ??= []).push(row);
      }
    }
    return Object.entries(grouped).sort((a, b) => a[0].localeCompare(b[0]));
  }, [groupBy, filteredRows, fundStyleMap]);

  return (
    <div>
      {/* 页面标题 */}
      <div className="page-head-v2">
        <div>
          <span className="eyebrow">RESEARCH · 风格研究</span>
          <h1>展示池与风格总览</h1>
          <p>
            一屏看清这批 {totalFunds} 只权益基金的风格画像、可展示状态、Top 业绩归属。
            先按"是否可展示"过滤，再按风格下钻，最后进入单基金诊断报告。
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
          <div className="flow-steps">
            <span className="flow-step is-current">
              <span className="step-num">1</span>总览
            </span>
            <span className="flow-arrow">→</span>
            <span className="flow-step">
              <span className="step-num">2</span>单基金诊断
            </span>
            <span className="flow-arrow">→</span>
            <span className="flow-step">
              <span className="step-num">3</span>加入组合
            </span>
          </div>
          <Link to="/search" className="link-btn" style={{ fontSize: 12 }}>
            跳到风格筛选 →
          </Link>
        </div>
      </div>

      {/* 上下文栏：当前批次 + 规则版本 + 数据快照 */}
      <div className="context-bar">
        <div className="chip">
          <span className="label">当前批次</span>
          <span className="value" style={{ fontFamily: "ui-monospace, monospace" }}>
            {runId ? runId.slice(0, 12) + "…" : "—"}
          </span>
        </div>
        <div className="chip chip-status">
          <span className="dot" />
          <span className="label">数据状态</span>
          <span className="value">实时</span>
        </div>
        <div className="chip">
          <span className="label">规则版本</span>
          <span className="value">v1</span>
        </div>
        <div className="chip">
          <span className="label">基金池</span>
          <span className="value">{totalFunds} 只</span>
        </div>
        <div className="spacer" />
        <label className="chip" style={{ background: "var(--surface)", cursor: "pointer" }}>
          <span className="label">切换批次</span>
          <select
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            style={{
              border: "none",
              background: "transparent",
              padding: 0,
              fontWeight: 700,
              fontSize: 12,
              color: "var(--text)",
            }}
          >
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id.slice(0, 8)}… ({r.run_at})
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="alert alert-warn">{error}</div>}

      {/* 代理口径说明 banner：当大量基金因 nav_window_insufficient 被屏蔽时给出提示 */}
      {showProxyCaliberBanner && (
        <div className="proxy-caliber-banner is-warn">
          <span className="caliber-icon">i</span>
          <div className="caliber-body">
            <span className="caliber-title">代理口径说明</span>
            <p>
              当前批次可展示基金占比低于 10%，主要原因为
              <strong> nav_window_insufficient（收益窗口不足）</strong>。
              这通常发生在新成立基金或代理净值序列较短的基金上，并非风格识别或基准配置问题。
              后续可考虑放宽窗口阈值或引入基准代理以提升覆盖率。
            </p>
          </div>
        </div>
      )}

      {/* 顶部决策摘要：覆盖率 + 4 维核心指标 */}
      <div className="decision-card">
        <span className="verdict is-go">展示池健康度 {coveragePct}%</span>
        <div className="takeaway">
          本批次 <strong>{totalFunds}</strong> 只权益基金中，<strong>{readyCount}</strong> 只可立即进入展示池
          （{coveragePct}%），<strong>{blockedCount}</strong> 只因基准或数据问题暂未达标。
          {blockedCount > 0 ? (
            <>
              {" "}
              主要原因是 <strong>缺基准源 / 需确认映射</strong>，已标注在下方"暂不可展示原因"表中。
            </>
          ) : (
            <> 全量已就绪。</>
          )}
        </div>
        <div className="actions">
          <button
            className="secondary"
            onClick={() => {
              setStatusFilter("blocked");
              document
                .getElementById("fund-list-section")
                ?.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
          >
            查看 {blockedCount} 只待修复
          </button>
          <Link to="/search" className="primary">
            风格筛选
          </Link>
        </div>
      </div>

      {/* 核心指标卡：4 维 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 10,
          marginBottom: 18,
        }}
      >
        <div className="metric-card-v2 is-pos">
          <div className="label">可展示</div>
          <div className="value">{readyCount}</div>
          <div className="sub">{coveragePct}% 覆盖率</div>
        </div>
        <div className="metric-card-v2 is-warn">
          <div className="label">暂不可展示</div>
          <div className="value">{blockedCount}</div>
          <div className="sub">需修复后入池</div>
        </div>
        <div className="metric-card-v2 is-accent">
          <div className="label">有风格标签</div>
          <div className="value">{fundsWithStyle}</div>
          <div className="sub">
            {totalFunds > 0 ? Math.round((fundsWithStyle / totalFunds) * 100) : 0}% 风格已识别
          </div>
        </div>
        <div className="metric-card-v2">
          <div className="label">风格未定</div>
          <div className="value">{totalFunds - fundsWithStyle}</div>
          <div className="sub">等待因子或持仓补全</div>
        </div>
      </div>

      {/* 工具栏：状态过滤 + 搜索 + 分组 */}
      <div className="toolbar-v2">
        <div className="filter-group" role="tablist">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              role="tab"
              aria-selected={statusFilter === opt.key}
              className={statusFilter === opt.key ? "active" : ""}
              onClick={() => setStatusFilter(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="search">
          <input
            type="search"
            placeholder="搜索基金代码或名称"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="filter-group" role="tablist">
          <button
            className={groupBy === "none" ? "active" : ""}
            onClick={() => setGroupBy("none")}
          >
            列表
          </button>
          <button
            className={groupBy === "style" ? "active" : ""}
            onClick={() => setGroupBy("style")}
          >
            按风格分组
          </button>
        </div>
        <div className="spacer" />
        <div className="meta">共 {filteredRows.length} 只 / {totalFunds}</div>
      </div>

      {/* 风格分布：仅在未分组时显示 */}
      {groupBy === "none" && styleDistribution.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-head">
            <h2>风格画像分布</h2>
            <div className="meta">按 {totalFunds} 只正式清单统计</div>
            <div className="actions">
              <Link to="/search">查看风格筛选器 →</Link>
            </div>
          </div>
          <div className="style-overview">
            {styleDistribution.slice(0, 9).map((d) => (
              <Link key={d.label_code} to={`/search?label_code=${d.label_code}`} className="style-card">
                <div className="style-card-head">
                  <strong>{d.label_name}</strong>
                  <span>{d.fund_count}</span>
                </div>
                <p>{((d.fund_count / totalFunds) * 100).toFixed(0)}% 的基金</p>
                <div className="style-card-tags">
                  <span className={styleTagClass(d.label_code)}>{styleName(d.label_code)}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* 同类 TOP 5：让研究员快速发现组内强者 */}
      {Object.keys(topFundsByStyle).length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-head">
            <h2>同类 TOP 5（年化收益）</h2>
            <div className="meta">4 个代表性风格标签 · 点击进入诊断报告</div>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: 12,
            }}
          >
            {Object.entries(topFundsByStyle).map(([styleCode, resp]) => (
              <div
                key={styleCode}
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: "var(--r)",
                  padding: 12,
                  background: "var(--surface-2)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  <span className={`style-tag ${styleTagClass(styleCode)}`}>
                    {styleName(styleCode)}
                  </span>
                  <span className="muted" style={{ fontSize: 11 }}>
                    同类 {resp.results[0]?.peer_count ?? 0} 只
                  </span>
                </div>
                <ol style={{ margin: 0, paddingLeft: 20, fontSize: 12 }}>
                  {resp.results.map((f) => (
                    <li key={f.fund_code} style={{ margin: "3px 0" }}>
                      <Link
                        to={`/runs/${runId}/funds/${f.fund_code}`}
                        style={{ fontFamily: "ui-monospace, monospace" }}
                      >
                        {f.fund_code}
                      </Link>
                      <span className="muted" style={{ marginLeft: 6 }}>
                        {f.metric_value !== null ? `${(Number(f.metric_value) * 100).toFixed(1)}%` : "-"}
                        {" · "}第 {f.rank_value} 名
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 暂不可展示原因：让运维/风控能定位修复点 */}
      {eligibility && blockedCount > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-head">
            <h2>暂不可展示原因</h2>
            <div className="meta">运维重点修复项 · 影响 {blockedCount} 只基金</div>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 8,
            }}
          >
            {Object.entries(eligibility.status_counts)
              .filter(
                ([key]) =>
                  key !== "relative_label_ready" && key !== "relative_label_ready_approx"
              )
              .map(([key, count]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setStatusFilter("blocked");
                    document
                      .getElementById("fund-list-section")
                      ?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--r-s)",
                    background: "var(--surface-2)",
                    cursor: "pointer",
                    font: "inherit",
                    textAlign: "left",
                  }}
                >
                  <StatusPill status={key} />
                  <strong style={{ fontVariantNumeric: "tabular-nums" }}>{count}</strong>
                </button>
              ))}
          </div>
        </div>
      )}

      {/* 基金列表 / 分组列表 */}
      <div id="fund-list-section" className="card">
        <div className="section-head">
          <h2>
            {groupBy === "style" ? "按风格分组的展示池" : "展示池清单"}
          </h2>
          <div className="meta">共 {filteredRows.length} 只</div>
        </div>

        {filteredRows.length === 0 ? (
          <div className="empty-state">
            <div className="icon">∅</div>
            <div className="title">没有匹配的基金</div>
            <div className="hint">
              {query
                ? `没有代码或名称包含「${query}」的基金`
                : '当前过滤器下没有基金，试试切换「全部」或其他状态。'}
            </div>
          </div>
        ) : rowsByStyle ? (
          <div style={{ display: "grid", gap: 14 }}>
            {rowsByStyle.map(([styleCode, rows]) => (
              <div key={styleCode} style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 8,
                  }}
                >
                  {styleCode === "未分类" ? (
                    <span className="status-pill">未分类</span>
                  ) : (
                    <span className={`style-tag ${styleTagClass(styleCode)}`}>
                      {styleName(styleCode)}
                    </span>
                  )}
                  <span className="muted" style={{ fontSize: 11 }}>
                    {rows.length} 只
                  </span>
                </div>
                <table className="table-v2">
                  <thead>
                    <tr>
                      <th>基金</th>
                      <th>其他风格</th>
                      <th>展示状态</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const allTags = fundStyleMap.get(row.fund_code) || [];
                      const otherTags = allTags.filter((t) => t !== styleCode);
                      return (
                        <tr
                          key={`${styleCode}-${row.fund_code}`}
                          onClick={() =>
                            (window.location.href = `/runs/${eligibility?.run_id}/funds/${row.fund_code}`)
                          }
                        >
                          <td>
                            <div className="fund-row-code">
                              <span className="code">{row.fund_code}</span>
                              <span className="name">{row.fund_name}</span>
                            </div>
                          </td>
                          <td>
                            {otherTags.length > 0 ? (
                              <div className="style-labels-grid">
                                {otherTags.slice(0, 3).map((code) => (
                                  <span key={code} className={styleTagClass(code)}>
                                    {styleName(code)}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td>
                            <StatusPill status={row.relative_label_status} />
                          </td>
                          <td className="num">
                            <Link
                              to={`/runs/${eligibility?.run_id}/funds/${row.fund_code}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              查看
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        ) : (
          <table className="table-v2">
            <thead>
              <tr>
                <th>基金</th>
                <th>风格标签</th>
                <th>展示状态</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => {
                const tags = fundStyleMap.get(row.fund_code) || [];
                return (
                  <tr
                    key={row.fund_code}
                    onClick={() =>
                      (window.location.href = `/runs/${eligibility?.run_id}/funds/${row.fund_code}`)
                    }
                  >
                    <td>
                      <div className="fund-row-code">
                        <span className="code">{row.fund_code}</span>
                        <span className="name">{row.fund_name}</span>
                      </div>
                    </td>
                    <td>
                      {tags.length > 0 ? (
                        <div className="style-labels-grid">
                          {tags.slice(0, 4).map((code) => (
                            <span key={code} className={styleTagClass(code)}>
                              {styleName(code)}
                            </span>
                          ))}
                          {tags.length > 4 && (
                            <span className="muted" style={{ fontSize: 11 }}>
                              +{tags.length - 4}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <StatusPill status={row.relative_label_status} />
                    </td>
                    <td className="num">
                      <Link
                        to={`/runs/${eligibility?.run_id}/funds/${row.fund_code}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        查看
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
