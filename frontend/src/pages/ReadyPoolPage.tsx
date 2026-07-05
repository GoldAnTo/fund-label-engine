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
} from "../api";
import { STYLE_GROUPS, ALL_STYLE_CODES, styleTagClass, styleName } from "../styleConfig";

const STATUS_LABELS: Record<string, string> = {
  relative_label_ready: "可展示",
  relative_label_ready_approx: "可展示（近似）",
  benchmark_source_missing: "缺基准源",
  benchmark_mapping_required: "需确认映射",
  benchmark_unresolved: "组件未解析",
  benchmark_missing: "未配置基准",
  nav_window_insufficient: "收益窗口不足",
};

function statusLabel(value: string) {
  return STATUS_LABELS[value] ?? value;
}

function statusClass(value: string) {
  return value === "relative_label_ready" || value === "relative_label_ready_approx"
    ? "badge-observe"
    : "badge-manual_review";
}

export default function ReadyPoolPage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [eligibility, setEligibility] = useState<RelativeEligibilityResponse | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [matrix, setMatrix] = useState<PortfolioMatrixResponse | null>(null);
  const [topFundsByStyle, setTopFundsByStyle] = useState<Record<string, TopFundsResponse>>({});
  const [error, setError] = useState<string | null>(null);

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

    // 拉取 4 个代表性风格标签的 TOP 5 基金（按年化收益）
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
      m.set(row.fund_code, (row.style_tags || []).filter((t) => ALL_STYLE_CODES.has(t) && t !== "style_pending_rule_definition"));
    }
    return m;
  }, [matrix]);

  const totalFunds = eligibility?.total_funds ?? 142;
  const fundsWithStyle = Array.from(fundStyleMap.values()).filter((tags) => tags.length > 0).length;
  const fundsNoStyle = totalFunds - fundsWithStyle;

  // 按风格分组统计
  const groupStats = useMemo(() => {
    return STYLE_GROUPS.map((group) => {
      const count = new Set<string>();
      for (const tags of fundStyleMap.values()) {
        if (tags.some((t) => group.codes.includes(t))) {
          for (const fund of fundStyleMap.keys()) {
            const t = fundStyleMap.get(fund) || [];
            if (t.some((c) => group.codes.includes(c))) count.add(fund);
          }
        }
      }
      return { ...group, fundCount: count.size };
    });
  }, [fundStyleMap]);

  return (
    <div>
      <div className="page-head">
        <h1>风格总览</h1>
        <p>{totalFunds} 只权益基金的风格标签分布和展示池状态</p>
      </div>

      <div className="toolbar">
        <label>
          批次
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id.slice(0, 8)}… ({r.run_at})
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="alert alert-warn">{error}</div>}

      {/* 核心指标 */}
      {eligibility && (
        <div className="metric-grid">
          <div className="metric-tile"><span>正式清单</span><strong>{eligibility.total_funds}</strong></div>
          <div className="metric-tile"><span>可展示</span><strong>{eligibility.ready_count}</strong></div>
          <div className="metric-tile"><span>暂不可展示</span><strong>{eligibility.blocked_count}</strong></div>
          <div className="metric-tile"><span>有风格标签</span><strong>{fundsWithStyle}</strong></div>
          <div className="metric-tile"><span>风格未定</span><strong>{fundsNoStyle}</strong></div>
        </div>
      )}

      {/* 风格分布概览 */}
      <div className="card">
        <h2>风格分布</h2>
        {styleDistribution.length > 0 ? (
          <div className="style-overview">
            {styleDistribution.map((d) => (
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
        ) : (
          <p className="muted">暂无风格标签数据。请先跑批生成风格标签。</p>
        )}
      </div>

      {/* 风格维度统计 */}
      {groupStats.length > 0 && fundsWithStyle > 0 && (
        <div className="card">
          <h2>风格维度统计</h2>
          <p className="muted">每个维度有多少只基金命中</p>
          <table>
            <thead><tr><th>维度</th><th>基金数</th><th>标签</th></tr></thead>
            <tbody>
              {groupStats.map((g) => (
                <tr key={g.title}>
                  <td><strong>{g.title}</strong></td>
                  <td className="num">{g.fundCount}</td>
                  <td>
                    <div className="style-labels-grid">
                      {g.codes.map((code) => (
                        <span key={code} className={styleTagClass(code)}>{styleName(code)}</span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 同类 TOP 5：按风格分组查看年化收益排名靠前的基金 */}
      {Object.keys(topFundsByStyle).length > 0 && (
        <div className="card">
          <h2>同类 TOP 5</h2>
          <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
            4 个代表性风格标签里年化收益排名前 5 的基金（点击进入诊断报告查看分位详情）。
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
            {Object.entries(topFundsByStyle).map(([styleCode, resp]) => (
              <div key={styleCode} style={{ border: "1px solid var(--border)", borderRadius: 6, padding: 10, background: "var(--surface-2)" }}>
                <div style={{ marginBottom: 8 }}>
                  <span className={`style-tag ${styleTagClass(styleCode)}`}>
                    {styleName(styleCode)}
                  </span>
                  <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>
                    同类 {resp.results[0]?.peer_count ?? 0} 只
                  </span>
                </div>
                <ol style={{ margin: 0, paddingLeft: 20, fontSize: 12 }}>
                  {resp.results.map((f) => (
                    <li key={f.fund_code} style={{ margin: "3px 0" }}>
                      <Link to={`/funds/${f.fund_code}?run_id=${runId}`} style={{ fontFamily: "ui-monospace, monospace" }}>
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

      {/* 展示池门禁 */}
      {eligibility && eligibility.blocked_count > 0 && (
        <div className="card">
          <h2>暂不可展示原因</h2>
          <table>
            <thead><tr><th>原因</th><th className="num">基金数</th></tr></thead>
            <tbody>
              {Object.entries(eligibility.status_counts)
                .filter(([key]) => key !== "relative_label_ready" && key !== "relative_label_ready_approx")
                .map(([key, count]) => (
                  <tr key={key}>
                    <td><span className={`badge ${statusClass(key)}`}>{statusLabel(key)}</span></td>
                    <td className="num">{count}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 基金列表 */}
      {eligibility && (
        <div className="card">
          <h2>基金列表</h2>
          <table className="fund-table">
            <thead>
              <tr><th>基金</th><th>风格标签</th><th>展示状态</th><th></th></tr>
            </thead>
            <tbody>
              {eligibility.results.map((row) => {
                const tags = fundStyleMap.get(row.fund_code) || [];
                return (
                  <tr key={row.fund_code}>
                    <td>
                      <div className="fund-code-cell">{row.fund_code}</div>
                      <div className="fund-name-cell">{row.fund_name}</div>
                    </td>
                    <td>
                      {tags.length > 0 ? (
                        <div className="style-labels-grid">
                          {tags.map((code) => (
                            <span key={code} className={styleTagClass(code)}>{styleName(code)}</span>
                          ))}
                        </div>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${statusClass(row.relative_label_status)}`}>
                        {statusLabel(row.relative_label_status)}
                      </span>
                    </td>
                    <td>
                      <Link to={`/runs/${eligibility.run_id}/funds/${row.fund_code}`}>查看</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
