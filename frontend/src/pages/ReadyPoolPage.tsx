import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  fetchRelativeEligibility,
  fetchRuns,
  fetchRunSummary,
  fetchPortfolioMatrix,
  fetchTopFunds,
  fetchWorkbenchSummary,
  fetchDataQuality,
  fetchRuleVersions,
  postRunReplay,
  downloadFile,
  type RelativeEligibilityResponse,
  type RunSummary,
  type PortfolioMatrixResponse,
  type TopFundsResponse,
  type WorkbenchSummary,
  type DataQualityReport,
  type Run,
  type RuleVersionInfo,
} from "../api";
import { ALL_STYLE_CODES, STYLE_GROUPS, styleTagClass, styleName } from "../styleConfig";

const STATUS_LABELS: Record<string, string> = {
  relative_label_ready: "可展示",
  relative_label_ready_approx: "可展示（近似）",
  benchmark_source_missing: "缺基准源",
  benchmark_mapping_required: "需确认映射",
  benchmark_unresolved: "组件未解析",
  benchmark_missing: "未配置基准",
  nav_window_insufficient: "收益窗口不足",
};

function isReadyStatus(value: string) {
  return value === "relative_label_ready" || value === "relative_label_ready_approx";
}

function statusVerdict(value: string) {
  if (isReadyStatus(value)) return "go";
  if (value === "nav_window_insufficient" || value === "benchmark_source_missing") return "watch";
  return "block";
}

function StatusPill({ status }: { status: string }) {
  const v = statusVerdict(status);
  return (
    <span className={`status-pill is-${v}`}>{STATUS_LABELS[status] ?? status}</span>
  );
}

type StatusFilter = "all" | "ready" | "blocked";

const FILTER_OPTIONS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "ready", label: "可展示" },
  { key: "blocked", label: "不可展示" },
];

// TOP 基金指标选项
const METRIC_OPTIONS: { code: string; label: string; fmt: (v: number | null) => string }[] = [
  { code: "annualized_return_1y", label: "年化收益", fmt: (v) => (v !== null ? `${(v * 100).toFixed(1)}%` : "—") },
  { code: "sharpe_ratio_1y", label: "夏普比率", fmt: (v) => (v !== null ? v.toFixed(2) : "—") },
  { code: "max_drawdown_1y", label: "最大回撤", fmt: (v) => (v !== null ? `${(v * 100).toFixed(1)}%` : "—") },
  { code: "annualized_excess_return_1y", label: "超额收益", fmt: (v) => (v !== null ? `${(v * 100).toFixed(1)}%` : "—") },
  { code: "information_ratio_1y", label: "信息比率", fmt: (v) => (v !== null ? v.toFixed(2) : "—") },
];

// TOP 基金展示的风格
const TOP_STYLES = ["quality_growth", "large_cap", "high_valuation", "low_valuation", "dividend_steady", "small_cap"];

const PAGE_SIZE = 50;

export default function ReadyPoolPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState("");
  const [eligibility, setEligibility] = useState<RelativeEligibilityResponse | null>(null);
  const [prevEligibility, setPrevEligibility] = useState<RelativeEligibilityResponse | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [workbench, setWorkbench] = useState<WorkbenchSummary | null>(null);
  const [matrix, setMatrix] = useState<PortfolioMatrixResponse | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQualityReport | null>(null);
  const [dqOpen, setDqOpen] = useState(false);
  const [ruleVersions, setRuleVersions] = useState<RuleVersionInfo[]>([]);
  const [replayTarget, setReplayTarget] = useState<string>("");
  const [replayBusy, setReplayBusy] = useState(false);
  const [replayResult, setReplayResult] = useState<{ new_run_id: string; processed: number } | null>(null);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [topFundsByStyle, setTopFundsByStyle] = useState<Record<string, TopFundsResponse>>({});
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");
  const [blockerFilter, setBlockerFilter] = useState<string | null>(null);
  const [metricCode, setMetricCode] = useState("annualized_return_1y");
  const [page, setPage] = useState(0);
  const [showAllStyles, setShowAllStyles] = useState(false);

  useEffect(() => {
    fetchRuns()
      .then((rs) => {
        setRuns(rs);
        if (rs.length > 0) setRunId(rs[0].run_id);
      })
      .catch((e) => setError(e.message));
    fetchRuleVersions()
      .then((r) => {
        setRuleVersions(r);
        // 默认选中"非当前" 的最近版本，方便回放
        if (r.length > 1) setReplayTarget(r[1].rule_version);
        else if (r.length === 1) setReplayTarget(r[0].rule_version);
      })
      .catch(() => {
        /* ignore */
      });
  }, []);

  // 当前批次数据
  useEffect(() => {
    if (!runId) return;
    setError(null);
    setBlockerFilter(null);
    setPage(0);
    Promise.all([
      fetchRelativeEligibility(runId, "all"),
      fetchRunSummary(runId),
      fetchPortfolioMatrix(runId),
      fetchWorkbenchSummary(runId).catch(() => null),
      fetchDataQuality().catch(() => null),
    ])
      .then(([elig, summ, mat, wb, dq]) => {
        setEligibility(elig);
        setSummary(summ);
        setMatrix(mat);
        setWorkbench(wb);
        setDataQuality(dq);
      })
      .catch((e) => setError(e.message));

    // 获取上一批次的 eligibility 用于覆盖率环比
    const currentIdx = runs.findIndex((r) => r.run_id === runId);
    if (currentIdx >= 0 && currentIdx < runs.length - 1) {
      const prevId = runs[currentIdx + 1].run_id;
      fetchRelativeEligibility(prevId, "all")
        .then((elig) => setPrevEligibility(elig))
        .catch(() => setPrevEligibility(null));
    } else {
      setPrevEligibility(null);
    }
  }, [runId, runs]);

  // TOP 基金（依赖 metricCode）
  useEffect(() => {
    if (!runId) return;
    Promise.all(
      TOP_STYLES.map((s) =>
        fetchTopFunds(runId, s, metricCode, 5)
          .then((resp) => [s, resp] as const)
          .catch(() => [s, null] as const)
      )
    ).then((results) => {
      const map: Record<string, TopFundsResponse> = {};
      for (const [s, resp] of results) if (resp) map[s] = resp;
      setTopFundsByStyle(map);
    });
  }, [runId, metricCode]);

  const styleDistribution = useMemo(() => {
    if (!summary) return [];
    return summary.label_distribution
      .filter((d) => ALL_STYLE_CODES.has(d.label_code) && d.label_code !== "style_pending_rule_definition")
      .sort((a, b) => b.fund_count - a.fund_count);
  }, [summary]);

  // 按分组组织风格分布
  const styleByGroup = useMemo(() => {
    const map = new Map<string, typeof styleDistribution>();
    for (const d of styleDistribution) {
      const group = STYLE_GROUPS.find((g) => g.codes.includes(d.label_code));
      const key = group ? group.title : "其它";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(d);
    }
    return map;
  }, [styleDistribution]);

  const fundStyleMap = useMemo(() => {
    if (!matrix) return new Map<string, string[]>();
    const m = new Map<string, string[]>();
    for (const row of matrix.rows) {
      m.set(
        row.fund_code,
        (row.style_tags || []).filter((t) => ALL_STYLE_CODES.has(t) && t !== "style_pending_rule_definition")
      );
    }
    return m;
  }, [matrix]);

  const totalFunds = eligibility?.total_funds ?? 0;
  const readyCount = eligibility?.ready_count ?? 0;
  const blockedCount = eligibility?.blocked_count ?? 0;
  const readyExact = eligibility?.ready_exact_count ?? 0;
  const readyApprox = eligibility?.ready_approx_count ?? 0;
  const coveragePct = totalFunds > 0 ? Math.round((readyCount / totalFunds) * 100) : 0;

  // 覆盖率环比
  const coverageTrend = useMemo(() => {
    if (!prevEligibility || prevEligibility.total_funds === 0) return null;
    const prevPct = Math.round((prevEligibility.ready_count / prevEligibility.total_funds) * 100);
    const delta = coveragePct - prevPct;
    return { prevPct, delta };
  }, [prevEligibility, coveragePct]);

  // 数据日期
  const currentRun = runs.find((r) => r.run_id === runId);
  const dataDate = currentRun?.data_as_of ?? currentRun?.run_at?.slice(0, 10) ?? "—";

  const blockedStatusEntries = useMemo(() => {
    if (!eligibility) return [];
    return Object.entries(eligibility.status_counts)
      .filter(([status, count]) => !isReadyStatus(status) && count > 0)
      .sort((a, b) => b[1] - a[1]);
  }, [eligibility]);

  const filteredRows = useMemo(() => {
    if (!eligibility) return [];
    const q = query.trim().toLowerCase();
    return eligibility.results.filter((row) => {
      if (statusFilter === "ready" && !isReadyStatus(row.relative_label_status)) return false;
      if (statusFilter === "blocked" && isReadyStatus(row.relative_label_status)) return false;
      if (blockerFilter && row.relative_label_status !== blockerFilter) return false;
      if (!q) return true;
      return row.fund_code.toLowerCase().includes(q) || row.fund_name.toLowerCase().includes(q);
    });
  }, [eligibility, statusFilter, query, blockerFilter]);

  // 分页
  const pageCount = Math.ceil(filteredRows.length / PAGE_SIZE);
  const pagedRows = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filteredRows.slice(start, start + PAGE_SIZE);
  }, [filteredRows, page]);

  const activeMetric = METRIC_OPTIONS.find((m) => m.code === metricCode)!;

  const goToFund = (fundCode: string) => {
    if (runId) navigate(`/runs/${runId}/funds/${fundCode}`);
  };

  const handleExport = () => {
    if (runId) downloadFile(`/v1/runs/${runId}/export?format=xlsx`, `run_${runId}.xlsx`);
  };

  // 点击阻塞原因时，滚动到基金清单并设置筛选
  const handleBlockerClick = (status: string) => {
    setBlockerFilter(blockerFilter === status ? null : status);
    setStatusFilter("blocked");
    setPage(0);
    setTimeout(() => {
      document.getElementById("fund-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  return (
    <div>
      {/* 上下文栏 */}
      <div className="context-bar">
        <div className="chip chip-mono">
          <span className="label">批次</span>
          <span className="value">{runId ? runId.slice(0, 12) : "—"}</span>
        </div>
        <div className="chip">
          <span className="label">数据截止</span>
          <span className="value">{dataDate}</span>
        </div>
        <div className="chip">
          <span className="label">基金池</span>
          <span className="value">{totalFunds} 只</span>
        </div>
        <div className="chip">
          <span className="label">规则</span>
          <span className="value">v1</span>
        </div>
        <div className="spacer" />
        {runs.length > 1 && (
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_at.slice(0, 10)} ({r.run_id.slice(0, 8)})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* 规则回放 */}
      <div className="card replay-card">
        <div className="replay-head">
          <div>
            <h2>规则回放</h2>
            <p className="meta">
              用指定规则版本在当前批次的数据基础上重新跑一遍，结果写入新 run_id。可用来验证规则改动。
            </p>
          </div>
          <div className="replay-form">
            <label className="field">
              <span>目标规则版本</span>
              <select
                value={replayTarget}
                onChange={(e) => setReplayTarget(e.target.value)}
                disabled={ruleVersions.length === 0}
              >
                {ruleVersions.map((v) => (
                  <option key={v.rule_version} value={v.rule_version}>
                    {v.rule_version}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="btn btn-accent"
              disabled={!runId || !replayTarget || replayBusy}
              onClick={async () => {
                if (!runId || !replayTarget) return;
                setReplayBusy(true);
                setReplayError(null);
                setReplayResult(null);
                try {
                  const r = await postRunReplay(runId, replayTarget);
                  setReplayResult({ new_run_id: r.new_run_id, processed: r.processed });
                } catch (e) {
                  setReplayError(e instanceof Error ? e.message : String(e));
                } finally {
                  setReplayBusy(false);
                }
              }}
            >
              {replayBusy ? "回放中…" : "执行回放"}
            </button>
          </div>
        </div>
        {replayError && <div className="alert alert-bad">回放失败：{replayError}</div>}
        {replayResult && (
          <div className="alert alert-ok">
            ✅ 回放成功 → 新 run_id <code>{replayResult.new_run_id}</code>（处理{" "}
            {replayResult.processed} 只基金）。可在批次下拉框中切换查看。
          </div>
        )}
      </div>

      {error && <div className="alert alert-warn">{error}</div>}

      {/* 概览指标 */}
      <div className="metric-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <div className="metric-card-v2 is-pos">
          <div className="label">可展示</div>
          <div className="value">{readyCount}<span style={{ fontSize: 13, color: "var(--text-3)", fontWeight: 500 }}> / {totalFunds}</span></div>
          <div className="sub">
            覆盖率 {coveragePct}%
            {coverageTrend && (
              <span className={`trend ${coverageTrend.delta > 0 ? "up" : coverageTrend.delta < 0 ? "down" : "flat"}`} style={{ marginLeft: 6 }}>
                {coverageTrend.delta > 0 ? "▲" : coverageTrend.delta < 0 ? "▼" : "—"} {Math.abs(coverageTrend.delta)}pp 较上批
              </span>
            )}
          </div>
        </div>
        <div className="metric-card-v2">
          <div className="label">精确基准</div>
          <div className="value">{readyExact}</div>
          <div className="sub">完整基准源</div>
        </div>
        <div className="metric-card-v2">
          <div className="label">近似基准</div>
          <div className="value">{readyApprox}</div>
          <div className="sub">近似债券指数</div>
        </div>
        <div className="metric-card-v2 is-warn">
          <div className="label">暂不可展示</div>
          <div className="value">{blockedCount}</div>
          <div className="sub">
            {blockedStatusEntries.slice(0, 2).map(([k, v]) => `${STATUS_LABELS[k] ?? k} ${v}`).join("、") || "全量就绪"}
          </div>
        </div>
      </div>

      {/* 风格分布 */}
      {styleDistribution.length > 0 && (
        <div className="card">
          <div className="section-head">
            <h2>风格画像分布</h2>
            <div className="meta">
              {totalFunds} 只基金 · {showAllStyles ? "按分组展示" : "Top 9 · 按触发数排序"}
              <button className="link-btn" style={{ marginLeft: 8 }} onClick={() => setShowAllStyles(!showAllStyles)}>
                {showAllStyles ? "收起" : "查看全部"}
              </button>
            </div>
          </div>
          {showAllStyles ? (
            <div style={{ display: "grid", gap: 14 }}>
              {STYLE_GROUPS.map((group) => {
                const items = styleByGroup.get(group.title) || [];
                if (items.length === 0) return null;
                return (
                  <div key={group.title}>
                    <div className="style-group-bar">
                      <span className={`style-filter-btn active`} style={{ cursor: "default" }}>{group.title}</span>
                      <span className="muted" style={{ fontSize: 10.5 }}>{items.reduce((s, d) => s + d.fund_count, 0)} 次命中</span>
                    </div>
                    <div className="style-overview">
                      {items.map((d) => (
                        <Link
                          key={d.label_code}
                          to={`/search?run_id=${encodeURIComponent(runId)}&label_code=${d.label_code}`}
                          className="style-card"
                        >
                          <div className="style-card-head">
                            <strong>{d.label_name}</strong>
                            <span>{d.fund_count}</span>
                          </div>
                          <p>{((d.fund_count / totalFunds) * 100).toFixed(0)}% 覆盖</p>
                        </Link>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="style-overview">
              {styleDistribution.slice(0, 9).map((d) => (
                <Link
                  key={d.label_code}
                  to={`/search?run_id=${encodeURIComponent(runId)}&label_code=${d.label_code}`}
                  className="style-card"
                >
                  <div className="style-card-head">
                    <strong>{d.label_name}</strong>
                    <span>{d.fund_count}</span>
                  </div>
                  <p>{((d.fund_count / totalFunds) * 100).toFixed(0)}% 覆盖</p>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 同类 TOP 5 */}
      {Object.keys(topFundsByStyle).length > 0 && (
        <div className="card">
          <div className="section-head">
            <h2>同类 TOP 5（{activeMetric.label}）</h2>
            <div className="meta" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>切换指标</span>
              <select value={metricCode} onChange={(e) => setMetricCode(e.target.value)} style={{ fontSize: 11.5, padding: "2px 6px" }}>
                {METRIC_OPTIONS.map((m) => (
                  <option key={m.code} value={m.code}>{m.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
            {Object.entries(topFundsByStyle).map(([styleCode, resp]) => (
              <div key={styleCode} style={{ padding: 10, background: "var(--surface-2)", borderRadius: "var(--r)", border: "1px solid var(--border)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                  <span className={`style-tag ${styleTagClass(styleCode)}`}>{styleName(styleCode)}</span>
                  <span className="muted" style={{ fontSize: 10.5 }}>同类 {resp.results[0]?.peer_count ?? 0} 只</span>
                </div>
                <table style={{ fontSize: 11.5 }}>
                  <tbody>
                    {resp.results.map((f, i) => (
                      <tr key={f.fund_code}>
                        <td style={{ width: 16, color: "var(--text-3)", padding: "3px 4px" }}>{i + 1}</td>
                        <td style={{ padding: "3px 4px" }}>
                          <Link to={`/runs/${runId}/funds/${f.fund_code}`} style={{ fontFamily: "ui-monospace, monospace", fontSize: 11.5 }}>
                            {f.fund_code}
                          </Link>
                        </td>
                        <td className="num" style={{ padding: "3px 4px", fontVariantNumeric: "tabular-nums" }}>
                          {activeMetric.fmt(f.metric_value !== null ? Number(f.metric_value) : null)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 数据健康（点击展开） */}
      {dataQuality && (
        <div className="card">
          <div className="section-head">
            <h2>
              数据健康
              <span className="dq-headline" style={{ marginLeft: 10 }}>
                {(() => {
                  const s = dataQuality.summary || {};
                  const crit = s.critical || 0;
                  const warn = s.warning || 0;
                  if (crit > 0) return <span className="dq-pill dq-pill-bad">✗ {crit} critical</span>;
                  if (warn > 0) return <span className="dq-pill dq-pill-warn">⚠ {warn} warning</span>;
                  return <span className="dq-pill dq-pill-ok">✓ 健康</span>;
                })()}
              </span>
            </h2>
            <div className="meta">
              {dataQuality.overview.total_funds} 只基金 · NAV {dataQuality.overview.nav_covered_funds}/{dataQuality.overview.total_funds} · 持仓 {dataQuality.overview.holding_covered_funds}/{dataQuality.overview.total_funds}
              <button
                className="link-btn"
                style={{ marginLeft: 8 }}
                onClick={() => setDqOpen(!dqOpen)}
              >
                {dqOpen ? "收起详情" : "查看详情"}
              </button>
            </div>
          </div>
          {dqOpen && (
            <div>
              {dataQuality.findings.length === 0 ? (
                <div className="alert alert-ok">未发现数据质量问题。</div>
              ) : (
                <ul className="dq-findings">
                  {dataQuality.findings.map((f, i) => (
                    <li key={i} className={`dq-finding dq-finding-${f.severity}`}>
                      <div className="dq-finding-head">
                        <span className={`dq-finding-sev sev-${f.severity}`}>
                          {f.severity === "critical" ? "✗" : f.severity === "warning" ? "⚠" : "·"} {f.severity}
                        </span>
                        <span className="dq-finding-title">{f.title}</span>
                        <span className="dq-finding-cat">{f.category}</span>
                      </div>
                      {f.detail && <div className="dq-finding-detail">{f.detail}</div>}
                      {f.samples && f.samples.length > 0 && (
                        <div className="dq-finding-samples">
                          样本：{f.samples.slice(0, 5).join("、")}
                          {f.samples.length > 5 && ` 等 ${f.samples.length} 个`}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {/* 分类 / 分组分布（点击进入筛选） */}
      {workbench && (workbench.group_distribution.length > 0 || workbench.classification_distribution.length > 0) && (
        <div className="card">
          <div className="section-head">
            <h2>分类 / 分组分布</h2>
            <div className="meta">点击任意条目跳转到风格筛选页带入筛选条件</div>
          </div>
          <div className="dist-grid">
            {workbench.classification_distribution.length > 0 && (
              <div className="dist-section">
                <h3>分类（按维度）</h3>
                {Object.entries(
                  workbench.classification_distribution.reduce<
                    Record<string, typeof workbench.classification_distribution>
                  >((acc, item) => {
                    (acc[item.dimension] = acc[item.dimension] || []).push(item);
                    return acc;
                  }, {})
                ).map(([dimension, items]) => (
                  <div key={dimension} className="dist-dim">
                    <div className="dist-dim-label">{dimension}</div>
                    <div className="dist-items">
                      {items.map((d) => (
                        <Link
                          key={d.classification_code}
                          to={`/search?run_id=${encodeURIComponent(runId)}&classification_code=${encodeURIComponent(d.classification_code)}`}
                          className="dist-item"
                        >
                          <span className="dist-item-name">{d.classification_name}</span>
                          <span className="dist-item-count">{d.fund_count}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {workbench.group_distribution.length > 0 && (
              <div className="dist-section">
                <h3>分组（按 type）</h3>
                {Object.entries(
                  workbench.group_distribution.reduce<
                    Record<string, typeof workbench.group_distribution>
                  >((acc, item) => {
                    (acc[item.group_type] = acc[item.group_type] || []).push(item);
                    return acc;
                  }, {})
                ).map(([gtype, items]) => (
                  <div key={gtype} className="dist-dim">
                    <div className="dist-dim-label">{gtype}</div>
                    <div className="dist-items">
                      {items.map((d) => (
                        <Link
                          key={d.group_code}
                          to={`/search?run_id=${encodeURIComponent(runId)}&group_code=${encodeURIComponent(d.group_code)}&group_type=${encodeURIComponent(d.group_type)}`}
                          className="dist-item"
                        >
                          <span className="dist-item-name">{d.group_name}</span>
                          <span className="dist-item-count">{d.fund_count}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 暂不可展示原因 */}
      {eligibility && blockedCount > 0 && (
        <div className="card">
          <div className="section-head">
            <h2>暂不可展示原因</h2>
            <div className="meta">
              影响 {blockedCount} 只基金
              {blockerFilter && (
                <>
                  <span style={{ marginLeft: 6 }}>· 已筛选: {STATUS_LABELS[blockerFilter] ?? blockerFilter}</span>
                  <button className="link-btn" style={{ marginLeft: 6 }} onClick={() => setBlockerFilter(null)}>清除</button>
                </>
              )
              }
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {blockedStatusEntries.map(([key, count]) => (
              <button
                key={key}
                onClick={() => handleBlockerClick(key)}
                className={`blocker-chip ${blockerFilter === key ? "active" : ""}`}
                title="点击筛选该原因的基金"
              >
                <StatusPill status={key} />
                <strong style={{ fontVariantNumeric: "tabular-nums" }}>{count}</strong>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 基金清单 */}
      <div className="card" id="fund-list">
        <div className="toolbar-v2">
          <div className="filter-group">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                className={statusFilter === opt.key ? "active" : ""}
                onClick={() => { setStatusFilter(opt.key); setBlockerFilter(null); setPage(0); }}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="search">
            <input type="search" placeholder="搜索基金代码或名称" value={query} onChange={(e) => { setQuery(e.target.value); setPage(0); }} />
          </div>
          <div className="spacer" />
          <button className="compact-button" onClick={handleExport} style={{ border: "1px solid var(--border-2)", borderRadius: "var(--r-s)", background: "var(--surface)", cursor: "pointer", fontWeight: 600, color: "var(--text-2)" }}>
            导出 Excel
          </button>
          <div className="meta">{filteredRows.length} 只</div>
        </div>

        {filteredRows.length === 0 ? (
          <div className="empty-state">
            <div className="title">没有匹配的基金</div>
            <div className="hint">尝试切换过滤器或清除搜索词</div>
          </div>
        ) : (
          <>
            <table className="table-v2">
              <thead>
                <tr>
                  <th>基金代码</th>
                  <th>基金名称</th>
                  <th>风格标签</th>
                  <th>展示状态</th>
                </tr>
              </thead>
              <tbody>
                {pagedRows.map((row) => {
                  const tags = fundStyleMap.get(row.fund_code) || [];
                  return (
                    <tr key={row.fund_code} onClick={() => goToFund(row.fund_code)}>
                      <td>
                        <span style={{ fontFamily: "ui-monospace, monospace", fontWeight: 700, fontSize: 12 }}>
                          {row.fund_code}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: 11.5, color: "var(--text-2)" }}>{row.fund_name}</span>
                      </td>
                      <td>
                        {tags.length > 0 ? (
                          tags.slice(0, 3).map((code) => (
                            <span key={code} className={styleTagClass(code)} style={{ marginRight: 3 }}>
                              {styleName(code)}
                            </span>
                          ))
                        ) : (
                          <span className="muted">—</span>
                        )}
                        {tags.length > 3 && <span className="muted" style={{ fontSize: 10.5 }}> +{tags.length - 3}</span>}
                      </td>
                      <td><StatusPill status={row.relative_label_status} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {pageCount > 1 && (
              <div className="pager">
                <button disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button>
                <span className="pager-info">第 {page + 1} / {pageCount} 页</span>
                <button disabled={page >= pageCount - 1} onClick={() => setPage(page + 1)}>下一页</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
