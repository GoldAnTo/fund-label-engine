import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  downloadFile,
  fetchBenchmarkComponents,
  fetchFundReport,
  postReview,
  type FundLabel,
} from "../api";
import { useAsync, LabelStatusBadge, ReviewActionBadge } from "../components";

const STYLE_WEIGHT_CODES = [
  "deep_value_weight",
  "quality_growth_weight",
  "dividend_steady_weight",
] as const;
const STYLE_LABELS: Record<string, string> = {
  deep_value_weight: "深度价值",
  quality_growth_weight: "质量成长",
  dividend_steady_weight: "红利稳健",
};

interface StylePeriod {
  period: string;
  coverage: number;
  dominantStyle: string;
  dominantValue: number;
  weights: Record<string, number>;
}

function deriveStylePeriods(
  exposures: { report_date: string; factor_code: string; exposure_value: number }[]
): StylePeriod[] {
  const byPeriod: Record<string, Record<string, number>> = {};
  for (const row of exposures) {
    const period = row.report_date;
    if (!period) continue;
    if (
      row.factor_code === "factor_coverage_weight" ||
      STYLE_WEIGHT_CODES.includes(row.factor_code as (typeof STYLE_WEIGHT_CODES)[number])
    ) {
      (byPeriod[period] ||= {})[row.factor_code] = Number(row.exposure_value) || 0;
    }
  }
  const periods: StylePeriod[] = [];
  for (const [period, values] of Object.entries(byPeriod)) {
    const coverage = values["factor_coverage_weight"] ?? 0;
    const weights: Record<string, number> = {};
    let dominantStyle = "-";
    let dominantValue = -1;
    for (const code of STYLE_WEIGHT_CODES) {
      const v = values[code] ?? 0;
      weights[code] = v;
      if (v > dominantValue) {
        dominantValue = v;
        dominantStyle = STYLE_LABELS[code];
      }
    }
    periods.push({ period, coverage, dominantStyle, dominantValue, weights });
  }
  return periods.sort((a, b) => a.period.localeCompare(b.period));
}

export default function FundReportPage() {
  const { runId = "", fundCode = "" } = useParams();
  const [version, setVersion] = useState(0);
  const { data, error, loading } = useAsync(
    () => fetchFundReport(runId, fundCode),
    [runId, fundCode, version]
  );
  const { data: bench } = useAsync(
    () => fetchBenchmarkComponents(runId, fundCode),
    [runId, fundCode]
  );
  const stylePeriods = useMemo(
    () => (data ? deriveStylePeriods(data.factor_exposures) : []),
    [data]
  );
  const stabilityLabels = useMemo<FundLabel[]>(() => {
    if (!data) return [];
    const codes = new Set([
      "style_stable",
      "style_drift",
      "style_recent_shift",
      "style_exposure_low_coverage",
      "style_exposure_scope_not_applicable",
      "style_exposure_observe",
    ]);
    return data.labels.filter((l) => codes.has(l.label_code));
  }, [data]);
  const unresolvedCalculations = useMemo(() => {
    if (!data?.calculations) return [];
    return data.calculations.filter(
      (c) => c.state !== "active" && c.reason_code && c.reason_code !== "ok"
    );
  }, [data]);

  const [activeLabel, setActiveLabel] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState("researcher");
  const [decision, setDecision] = useState("confirm");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const factorCoverage = data?.factor_exposures.find(
    (f) => f.factor_code === "factor_coverage_weight"
  );
  const factorCoverageValue = factorCoverage ? Number(factorCoverage.exposure_value) : null;

  const submit = async () => {
    if (!activeLabel) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await postReview(runId, fundCode, activeLabel, decision, reviewer, comment);
      setActiveLabel(null);
      setComment("");
      setVersion((v) => v + 1);
    } catch (e: unknown) {
      setSubmitError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>
            基金报告 <code>{fundCode}</code>{" "}
            {data && <ReviewActionBadge value={data.review_action} />}
          </h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() =>
                downloadFile(
                  `/v1/runs/${runId}/funds/${fundCode}/export?format=xlsx`,
                  `fund_${fundCode}.xlsx`
                )
              }
            >
              导出 XLSX
            </button>
            <button
              onClick={() =>
                downloadFile(
                  `/v1/runs/${runId}/funds/${fundCode}/export?format=csv`,
                  `fund_${fundCode}.zip`
                )
              }
            >
              导出 CSV (zip)
            </button>
          </div>
        </div>
        <p className="muted">Run: <code>{runId}</code></p>
        {loading && <p>加载中...</p>}
        {error && <div className="error">{error}</div>}
        {data && (
          <>
            <h3>汇总</h3>
            <dl className="kv">
              <dt>标签数</dt><dd>{data.summary.label_count}</dd>
              <dt>特征数</dt><dd>{data.summary.feature_count}</dd>
              <dt>因子暴露</dt><dd>{data.summary.factor_exposure_count ?? data.factor_exposures.length}</dd>
              <dt>因子覆盖</dt>
              <dd>
                {factorCoverageValue === null
                  ? "未计算"
                  : `${(factorCoverageValue * 100).toFixed(1)}%`}
              </dd>
              <dt>证据条数</dt><dd>{data.summary.evidence_count}</dd>
              <dt>缺失字段数</dt><dd>{data.summary.missing_field_count}</dd>
              <dt>已有复核</dt><dd>{data.summary.review_count}</dd>
            </dl>
            {data.missing_fields.length > 0 && (
              <>
                <h3>缺失字段</h3>
                <p>{data.missing_fields.join("、")}</p>
              </>
            )}
          </>
        )}
      </div>

      {bench && (() => {
        const gap = bench.unresolved_count > 0 || !bench.has_benchmark_returns;
        return (
          <div className="card">
            <h2>
              基准组件缺口
              {gap ? (
                <span className="pill pill-gap">有缺口</span>
              ) : (
                <span className="pill pill-ok">已就绪</span>
              )}
            </h2>
            {gap ? (
              <div className="alert alert-warn">
                {bench.unresolved_count > 0
                  ? `${bench.unresolved_count} 个组件未解析或无日收益源；`
                  : ""}
                {!bench.has_benchmark_returns
                  ? "未能合成基准日收益，相对基准类标签无法计算。"
                  : ""}
              </div>
            ) : (
              <div className="alert alert-ok">
                基准收益已合成（{bench.benchmark_returns_count} 行），全部组件已解析且有收益源。
              </div>
            )}
            {bench.components.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>#</th><th>组件</th><th>权重</th><th>状态</th><th>收益源</th><th>原因</th><th>原文</th>
                  </tr>
                </thead>
                <tbody>
                  {bench.components.map((c) => (
                    <tr key={c.component_order}>
                      <td>{c.component_order}</td>
                      <td>
                        <strong>{c.component_name}</strong>
                        {c.component_code && (
                          <div className="muted"><code>{c.component_code}</code></div>
                        )}
                      </td>
                      <td>{c.weight !== null ? `${(c.weight * 100).toFixed(1)}%` : "-"}</td>
                      <td>{c.status}</td>
                      <td>
                        {c.status === "resolved" && c.reason === "synthetic"
                          ? "合成"
                          : c.has_returns
                          ? "有"
                          : <span style={{ color: "#b91c1c" }}>无</span>}
                      </td>
                      <td className="muted">{c.reason || "-"}</td>
                      <td className="muted">{c.source_text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })()}

      {data && stylePeriods.length > 0 && (
        <div className="card">
          <h2>风格稳定性证据</h2>
          <p className="muted">
            多期基金级因子暴露序列，按报告期排列。覆盖率 ≥70% 的期次参与稳定性判定。
          </p>
          {stabilityLabels.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              {stabilityLabels.map((l) => {
                const ev = data.evidence.filter((e) => e.label_code === l.label_code);
                return (
                  <div key={l.label_code} style={{ marginBottom: 6 }}>
                    <strong>{l.label_name}</strong>{" "}
                    <span className="muted"><code>{l.label_code}</code></span>
                    {ev[0] && <div className="muted">{ev[0].message}</div>}
                  </div>
                );
              })}
            </div>
          )}
          <table>
            <thead>
              <tr>
                <th>报告期</th><th>覆盖率</th><th>主导风格</th><th>深度价值</th><th>质量成长</th><th>红利稳健</th>
              </tr>
            </thead>
            <tbody>
              {stylePeriods.map((p) => (
                <tr key={p.period}>
                  <td><code>{p.period}</code></td>
                  <td>
                    <span style={{ color: p.coverage >= 0.7 ? "#065f46" : "#b45309" }}>
                      {(p.coverage * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td>{p.coverage >= 0.7 ? p.dominantStyle : <span className="muted">未达标</span>}</td>
                  <td>{(p.weights["deep_value_weight"] * 100).toFixed(1)}%</td>
                  <td>{(p.weights["quality_growth_weight"] * 100).toFixed(1)}%</td>
                  <td>{(p.weights["dividend_steady_weight"] * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && unresolvedCalculations.length > 0 && (
        <div className="card">
          <h2>标签计算原因（未触发）</h2>
          <p className="muted">列出未达 active 状态且有具体原因码的标签计算，便于定位数据或阈值缺口。</p>
          <table>
            <thead>
              <tr><th>标签</th><th>状态</th><th>原因码</th><th>观测值</th><th>阈值</th><th>说明</th></tr>
            </thead>
            <tbody>
              {unresolvedCalculations.map((c) => (
                <tr key={c.label_code}>
                  <td>
                    <strong>{c.label_name}</strong>
                    <div className="muted"><code>{c.label_code}</code></div>
                  </td>
                  <td>{c.state}</td>
                  <td><code>{c.reason_code}</code></td>
                  <td>{c.observed ?? "-"}</td>
                  <td>{c.threshold ?? "-"}</td>
                  <td className="muted">{c.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <div className="card">
          <h2>标签与证据</h2>
          <table>
            <thead>
              <tr>
                <th>标签</th><th>分类</th><th>状态</th><th>置信</th><th>证据</th><th>复核</th>
              </tr>
            </thead>
            <tbody>
              {data.labels.map((label) => {
                const ev = data.evidence.filter((e) => e.label_code === label.label_code);
                return (
                  <tr key={label.label_code}>
                    <td>
                      <strong>{label.label_name}</strong>
                      <div className="muted"><code>{label.label_code}</code></div>
                    </td>
                    <td>{label.category}</td>
                    <td><LabelStatusBadge value={label.status} /></td>
                    <td>{(label.confidence * 100).toFixed(0)}%</td>
                    <td>
                      {ev.map((e, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>
                          <div style={{ fontSize: 13 }}>{e.message}</div>
                          <div className="muted">
                            {e.metric} = {e.value} (阈值 {e.threshold}, 来源 {e.source})
                          </div>
                        </div>
                      ))}
                    </td>
                    <td>
                      <button
                        className="secondary"
                        onClick={() => setActiveLabel(label.label_code)}
                      >
                        复核…
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {data && data.factor_exposures.length > 0 && (
        <div className="card">
          <h2>基金级因子暴露</h2>
          <p className="muted">基于持仓和股票因子预聚合，coverage 表示可用因子覆盖的持仓权重。</p>
          <table>
            <thead>
              <tr>
                <th>因子</th><th>暴露值</th><th>覆盖权重</th><th>持仓权重</th><th>股票覆盖</th><th>日期</th>
              </tr>
            </thead>
            <tbody>
              {data.factor_exposures.map((f) => (
                <tr key={`${f.report_date}-${f.factor_code}-${f.as_of_date}`}>
                  <td><code>{f.factor_code}</code></td>
                  <td>{Number(f.exposure_value).toFixed(4)}</td>
                  <td>{(Number(f.coverage_weight) * 100).toFixed(1)}%</td>
                  <td>{(Number(f.holding_total_weight) * 100).toFixed(1)}%</td>
                  <td>{f.covered_stock_count}/{f.stock_count}</td>
                  <td className="muted">{f.report_date} / {f.as_of_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.features.length > 0 && (
        <div className="card">
          <h2>特征值</h2>
          <table>
            <thead>
              <tr><th>特征</th><th>值</th><th>来源</th></tr>
            </thead>
            <tbody>
              {data.features.map((f) => (
                <tr key={f.feature_code}>
                  <td><code>{f.feature_code}</code></td>
                  <td>{f.value}</td>
                  <td className="muted">{f.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.reviews.length > 0 && (
        <div className="card">
          <h2>历史复核</h2>
          <table>
            <thead>
              <tr><th>标签</th><th>决定</th><th>复核人</th><th>备注</th></tr>
            </thead>
            <tbody>
              {data.reviews.map((r) => (
                <tr key={r.review_id}>
                  <td><code>{r.label_code}</code></td>
                  <td>{r.decision}</td>
                  <td>{r.reviewer}</td>
                  <td>{r.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeLabel && (
        <div className="card">
          <h2>提交复核</h2>
          <p className="muted">标签 <code>{activeLabel}</code></p>
          {submitError && <div className="error">{submitError}</div>}
          <div className="toolbar">
            <label>
              决定&nbsp;
              <select value={decision} onChange={(e) => setDecision(e.target.value)}>
                <option value="confirm">confirm</option>
                <option value="reject">reject</option>
                <option value="observe">observe</option>
              </select>
            </label>
            <label>
              复核人&nbsp;
              <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
            </label>
          </div>
          <textarea
            placeholder="备注"
            rows={3}
            style={{ width: "100%", marginBottom: 12 }}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <div className="toolbar">
            <button onClick={submit} disabled={submitting}>
              {submitting ? "提交中…" : "提交"}
            </button>
            <button className="secondary" onClick={() => setActiveLabel(null)}>
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
