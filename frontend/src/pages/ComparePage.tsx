import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchCompare,
  fetchCorrelation,
  fetchHoldingsOverlap,
  fetchPortfolioRisk,
  fetchRuns,
  type CompareResponse,
  type CorrelationResponse,
  type HoldingsOverlapResponse,
  type PortfolioRiskResponse,
} from "../api";
import { ALL_STYLE_CODES, STYLE_GROUPS, styleTagClass, styleName } from "../styleConfig";

// 雷达图用的 5 个风格维度（按分组聚合因子暴露）
const RADAR_AXES: { axis: string; factorCodes: string[]; label: string }[] = [
  { axis: "估值", label: "估值便宜度", factorCodes: ["pb_weighted", "pe_weighted", "valuation_percentile_weighted"] },
  { axis: "成长", label: "成长性", factorCodes: ["profit_growth_weighted", "revenue_growth_weighted", "quality_growth_weight"] },
  { axis: "红利", label: "红利稳健", factorCodes: ["dividend_yield_weighted", "dividend_steady_weight"] },
  { axis: "规模", label: "市值规模", factorCodes: ["log10_market_cap_weighted"] },
  { axis: "盈利", label: "盈利质量", factorCodes: ["roe_weighted"] },
];

// 给定一只基金的 factor_exposures，计算雷达图各维度的归一化值 [0, 1]
function computeRadarValues(factorExposures: { factor_code: string; exposure_value: number }[]): number[] {
  const factorMap = new Map<string, number>();
  for (const fe of factorExposures) {
    factorMap.set(fe.factor_code, fe.exposure_value);
  }
  return RADAR_AXES.map((axis) => {
    // 取该维度下所有因子的平均值
    const vals = axis.factorCodes
      .map((c) => factorMap.get(c))
      .filter((v): v is number => v !== undefined && v !== null && !Number.isNaN(v));
    if (vals.length === 0) return 0;
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    return avg;
  });
}

// 把原始值归一化到 [0, 1] 用于雷达图绘制（基于所有基金的最大最小值）
function normalizeRadar(allFundsValues: number[][]): number[][] {
  if (allFundsValues.length === 0) return [];
  const numAxes = RADAR_AXES.length;
  const mins = new Array(numAxes).fill(Infinity);
  const maxs = new Array(numAxes).fill(-Infinity);
  for (const vals of allFundsValues) {
    for (let i = 0; i < numAxes; i++) {
      if (vals[i] < mins[i]) mins[i] = vals[i];
      if (vals[i] > maxs[i]) maxs[i] = vals[i];
    }
  }
  return allFundsValues.map((vals) =>
    vals.map((v, i) => {
      const range = maxs[i] - mins[i];
      return range === 0 ? 0.5 : (v - mins[i]) / range;
    })
  );
}

// 风格雷达图 SVG 组件
function StyleRadarChart({
  funds,
}: {
  funds: { fund_code: string; factor_exposures: { factor_code: string; exposure_value: number }[] }[];
}) {
  const size = 320;
  const center = size / 2;
  const radius = 120;
  const numAxes = RADAR_AXES.length;

  const rawValues = funds.map((f) => computeRadarValues(f.factor_exposures));
  const normalized = normalizeRadar(rawValues);

  // 颜色调色板
  const colors = ["oklch(0.55 0.15 250)", "oklch(0.55 0.14 25)", "oklch(0.55 0.14 145)", "oklch(0.55 0.14 65)", "oklch(0.55 0.14 330)", "oklch(0.55 0.14 180)"];

  // 各轴角度（从顶部开始顺时针）
  const angles = Array.from({ length: numAxes }, (_, i) => (Math.PI * 2 * i) / numAxes - Math.PI / 2);

  // 网格圆
  const gridLevels = [0.2, 0.4, 0.6, 0.8, 1.0];

  // 计算多边形点
  const polygonPoints = (values: number[]) => {
    return values
      .map((v, i) => {
        const r = v * radius;
        const x = center + r * Math.cos(angles[i]);
        const y = center + r * Math.sin(angles[i]);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  };

  return (
    <svg width={size} height={size} style={{ display: "block", margin: "0 auto" }}>
      {/* 网格 */}
      {gridLevels.map((level) => (
        <polygon
          key={level}
          points={angles
            .map((a) => `${center + level * radius * Math.cos(a)},${center + level * radius * Math.sin(a)}`)
            .join(" ")}
          fill="none"
          stroke="var(--border)"
          strokeWidth={1}
        />
      ))}
      {/* 轴线 */}
      {angles.map((a, i) => (
        <line
          key={i}
          x1={center}
          y1={center}
          x2={center + radius * Math.cos(a)}
          y2={center + radius * Math.sin(a)}
          stroke="var(--border)"
          strokeWidth={1}
        />
      ))}
      {/* 每只基金的多边形 */}
      {normalized.map((vals, idx) => (
        <polygon
          key={idx}
          points={polygonPoints(vals)}
          fill={colors[idx % colors.length]}
          fillOpacity={0.12}
          stroke={colors[idx % colors.length]}
          strokeWidth={2}
        />
      ))}
      {/* 轴标签 */}
      {RADAR_AXES.map((axis, i) => {
        const labelR = radius + 22;
        const x = center + labelR * Math.cos(angles[i]);
        const y = center + labelR * Math.sin(angles[i]);
        return (
          <text
            key={i}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={12}
            fill="var(--text-2)"
            fontWeight={600}
          >
            {axis.axis}
          </text>
        );
      })}
      {/* 图例 */}
      {funds.map((f, idx) => (
        <g key={f.fund_code} transform={`translate(10, ${10 + idx * 18})`}>
          <rect width={12} height={12} fill={colors[idx % colors.length]} rx={2} />
          <text x={18} y={10} fontSize={11} fill="var(--text-2)" fontFamily="ui-monospace, monospace">
            {f.fund_code}
          </text>
        </g>
      ))}
    </svg>
  );
}

// 格式化指标值
function formatMetric(metricCode: string, value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  if (metricCode.includes("return") || metricCode.includes("drawdown")) {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (metricCode === "sharpe_ratio_1y" || metricCode === "information_ratio_1y") {
    return value.toFixed(3);
  }
  return value.toFixed(2);
}

export default function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState(searchParams.get("run_id") || "");
  const [inputCode, setInputCode] = useState("");
  const [fundCodes, setFundCodes] = useState<string[]>(
    searchParams.get("funds") ? searchParams.get("funds")!.split(",") : []
  );
  const [compare, setCompare] = useState<CompareResponse | null>(null);
  const [overlap, setOverlap] = useState<HoldingsOverlapResponse | null>(null);
  const [correlation, setCorrelation] = useState<CorrelationResponse | null>(null);
  const [portfolioRisk, setPortfolioRisk] = useState<PortfolioRiskResponse | null>(null);
  const [portfolioWeights, setPortfolioWeights] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchRuns().then((rs) => {
      setRuns(rs);
      if (!runId && rs.length > 0) setRunId(rs[0].run_id);
    });
  }, []);

  useEffect(() => {
    if (searchParams.get("funds")) {
      setFundCodes(searchParams.get("funds")!.split(","));
    }
    if (searchParams.get("run_id")) {
      setRunId(searchParams.get("run_id")!);
    }
  }, [searchParams]);

  const fetchCompareData = useMemo(() => {
    return async () => {
      if (!runId || fundCodes.length < 2) return;
      setLoading(true);
      setError(null);
      try {
        const [comp, ov, corr] = await Promise.all([
          fetchCompare(runId, fundCodes),
          fetchHoldingsOverlap(fundCodes, 10),
          fetchCorrelation(fundCodes),
        ]);
        setCompare(comp);
        setOverlap(ov);
        setCorrelation(corr);

        // 组合风险：默认等权
        const defaultWeights = fundCodes.map(() => 1 / fundCodes.length);
        setPortfolioWeights(defaultWeights);
        try {
          const pr = await fetchPortfolioRisk(fundCodes, defaultWeights);
          setPortfolioRisk(pr);
        } catch {
          setPortfolioRisk(null);
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
  }, [runId, fundCodes]);

  useEffect(() => {
    fetchCompareData();
  }, [fetchCompareData]);

  const addFund = () => {
    const code = inputCode.trim();
    if (!code) return;
    if (fundCodes.length >= 6) {
      setError("最多支持 6 只基金对比");
      return;
    }
    if (fundCodes.includes(code)) return;
    const next = [...fundCodes, code];
    setFundCodes(next);
    setInputCode("");
    updateUrl(next, runId);
  };

  const removeFund = (code: string) => {
    const next = fundCodes.filter((c) => c !== code);
    setFundCodes(next);
    updateUrl(next, runId);
  };

  const updateUrl = (funds: string[], rid: string) => {
    const params = new URLSearchParams();
    if (rid) params.set("run_id", rid);
    if (funds.length > 0) params.set("funds", funds.join(","));
    setSearchParams(params);
  };

  // 判断某指标的最优值
  const findBest = (metricCode: string, direction: string): string | null => {
    if (!compare) return null;
    let bestCode: string | null = null;
    let bestVal: number | null = null;
    for (const f of compare.funds) {
      const v = f.metrics[metricCode];
      if (v === undefined) continue;
      if (bestVal === null) {
        bestVal = v;
        bestCode = f.fund_code;
      } else if (direction === "higher_better" && v > bestVal) {
        bestVal = v;
        bestCode = f.fund_code;
      } else if (direction === "lower_better" && v < bestVal) {
        bestVal = v;
        bestCode = f.fund_code;
      }
    }
    return bestCode;
  };

  // 收集所有出现过的风格标签
  const allStyleLabels = useMemo(() => {
    if (!compare) return [];
    const set = new Set<string>();
    for (const f of compare.funds) {
      for (const l of f.labels) {
        if (ALL_STYLE_CODES.has(l.label_code)) set.add(l.label_code);
      }
    }
    return Array.from(set).sort((a, b) => {
      // 按分组排序
      const groupOrder = (code: string) => {
        for (let i = 0; i < STYLE_GROUPS.length; i++) {
          if (STYLE_GROUPS[i].codes.includes(code)) return i;
        }
        return 99;
      };
      const ga = groupOrder(a);
      const gb = groupOrder(b);
      if (ga !== gb) return ga - gb;
      return a.localeCompare(b);
    });
  }, [compare]);

  return (
    <div>
      <div className="page-head-v2">
        <div>
          <span className="eyebrow">RESEARCH · 竞品横评</span>
          <h1>竞品横评</h1>
          <p>选 2-6 只基金并排对比风格、指标、持仓重叠度。</p>
        </div>
        <div className="flow-steps" style={{ alignSelf: "flex-start" }}>
          <span className="flow-step is-done">
            <span className="step-num">1</span>总览
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step is-done">
            <span className="step-num">2</span>筛选
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step is-current">
            <span className="step-num">3</span>横评
          </span>
        </div>
      </div>
      <div className="context-bar">
        <div className="chip chip-mono">
          <span className="label">批次</span>
          <span className="value">{runId ? runId.slice(0, 12) + "…" : "—"}</span>
        </div>
        <div className="chip">
          <span className="label">已选</span>
          <span className="value">{fundCodes.length} 只</span>
        </div>
        <div className="spacer" />
        {fundCodes.length > 0 && (
          <span className="meta" style={{ fontSize: 12, color: "var(--text-3)" }}>
            最多 6 只
          </span>
        )}
      </div>

      {/* 选基区 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 10 }}>
          <label style={{ fontSize: 13, color: "var(--text-2)" }}>批次</label>
          <select
            value={runId}
            onChange={(e) => {
              setRunId(e.target.value);
              updateUrl(fundCodes, e.target.value);
            }}
            style={{ minWidth: 220 }}
          >
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id.slice(0, 8)} · {r.run_at.slice(0, 10)}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="text"
            value={inputCode}
            onChange={(e) => setInputCode(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") addFund(); }}
            placeholder="输入基金代码，如 000017"
            style={{ width: 200 }}
          />
          <button onClick={addFund}>加入对比</button>
          <span className="muted" style={{ fontSize: 12 }}>
            已选 {fundCodes.length}/6 只
          </span>
        </div>

        {fundCodes.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            {fundCodes.map((code) => (
              <span
                key={code}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "4px 10px", borderRadius: 999,
                  background: "var(--accent-soft)", border: "1px solid var(--border-2)",
                  fontSize: 13, fontFamily: "ui-monospace, monospace",
                }}
              >
                <Link to={`/runs/${runId}/funds/${code}`}>{code}</Link>
                <button
                  className="secondary"
                  onClick={() => removeFund(code)}
                  style={{ padding: "0 6px", fontSize: 11, lineHeight: "18px" }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        {fundCodes.length < 2 && (
          <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>
            至少添加 2 只基金才能开始对比。
          </p>
        )}
      </div>

      {error && <div className="alert alert-warn">{error}</div>}
      {loading && <p className="muted">加载中...</p>}

      {compare && compare.funds.length >= 2 && (
        <>
          {/* 核心指标对比表 */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h2>核心指标对比</h2>
            <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
              ★ 标识该指标最优值。分位列显示该指标在全市场的百分位（1.0 = 第一）。
            </p>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>指标</th>
                    {compare.funds.map((f) => (
                      <th key={f.fund_code} className="num">
                        <Link to={`/runs/${runId}/funds/${f.fund_code}`} style={{ fontFamily: "ui-monospace, monospace" }}>
                          {f.fund_code}
                        </Link>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {compare.metric_defs.map((m) => {
                    const bestCode = findBest(m.metric_code, m.direction);
                    return (
                      <tr key={m.metric_code}>
                        <td>
                          <strong>{m.name}</strong>
                          <div className="muted" style={{ fontSize: 11 }}>
                            {m.direction === "higher_better" ? "↑ 越大越好" : "↓ 越小越好"}
                          </div>
                        </td>
                        {compare.funds.map((f) => {
                          const v = f.metrics[m.metric_code];
                          const pct = f.percentiles[m.metric_code];
                          const isBest = f.fund_code === bestCode && v !== undefined;
                          return (
                            <td key={f.fund_code} className="num" style={isBest ? { background: "var(--pos-soft)", fontWeight: 700 } : undefined}>
                              {formatMetric(m.metric_code, v)}
                              {isBest && <span style={{ color: "var(--pos-text)" }}> ★</span>}
                              {pct && (
                                <div className="muted" style={{ fontSize: 11 }}>
                                  分位 {pct.percentile.toFixed(2)} · {pct.rank_value}/{pct.peer_count}
                                </div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* 风格雷达图 */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h2>风格雷达图</h2>
            <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
              5 个风格维度的因子暴露对比（已归一化到 [0,1]）。
            </p>
            <StyleRadarChart funds={compare.funds} />
          </div>

          {/* 风格标签对比矩阵 */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h2>风格标签对比矩阵</h2>
            <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
              绿色 = 命中，灰色 = 未命中。
            </p>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>风格标签</th>
                    {compare.funds.map((f) => (
                      <th key={f.fund_code} className="num" style={{ fontFamily: "ui-monospace, monospace" }}>
                        {f.fund_code}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {allStyleLabels.map((labelCode) => (
                    <tr key={labelCode}>
                      <td>
                        <span className={`style-tag ${styleTagClass(labelCode)}`}>
                          {styleName(labelCode)}
                        </span>
                      </td>
                      {compare.funds.map((f) => {
                        const hit = f.labels.some((l) => l.label_code === labelCode && l.status === "active");
                        return (
                          <td key={f.fund_code} className="num" style={{ textAlign: "center" }}>
                            {hit ? (
                              <span style={{ color: "var(--pos-text)", fontWeight: 700 }}>✓</span>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 相关性热力图 */}
          {correlation && !correlation.error && correlation.matrix.length > 0 && (
            <div className="card">
              <h2>基金相关性矩阵</h2>
              <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
                基于日收益率的 Pearson 相关系数，共 {correlation.sample_count} 个交易日。|r| ≥ 0.8 替代性强，&lt; 0.3 分散效果好。
              </p>
              <div style={{ overflowX: "auto" }}>
                <table style={{ borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid var(--border)" }}></th>
                      {correlation.fund_codes.map((fc) => (
                        <th key={fc} style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid var(--border)", fontSize: 11 }}>
                          {fc}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {correlation.matrix.map((row, i) => (
                      <tr key={i}>
                        <td style={{ padding: "4px 8px", fontWeight: 600, fontSize: 11, borderBottom: "1px solid var(--border)" }}>
                          {correlation.fund_codes[i]}
                        </td>
                        {row.map((val, j) => {
                          const isDiagonal = i === j;
                          const absVal = Math.abs(val);
                          // 颜色梯度：红(高相关) → 黄(中等) → 绿(低相关)
                          let bg = "transparent";
                          let color = "var(--text)";
                          if (!isDiagonal) {
                            if (absVal >= 0.8) { bg = "rgba(220, 53, 69, 0.7)"; color = "#fff"; }
                            else if (absVal >= 0.6) { bg = "rgba(240, 173, 78, 0.6)"; color = "#333"; }
                            else if (absVal >= 0.3) { bg = "rgba(255, 235, 59, 0.4)"; color = "#333"; }
                            else { bg = "rgba(40, 167, 69, 0.4)"; color = "#333"; }
                          }
                          return (
                            <td key={j} style={{
                              padding: "6px 10px",
                              textAlign: "center",
                              borderBottom: "1px solid var(--border)",
                              background: bg,
                              color: color,
                              fontWeight: isDiagonal ? 700 : 400,
                              fontFamily: "monospace",
                            }}>
                              {isDiagonal ? "1.00" : val.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* 图例 */}
              <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
                <span><span style={{ display: "inline-block", width: 12, height: 12, background: "rgba(220, 53, 69, 0.7)", marginRight: 4, verticalAlign: "middle" }}></span>≥ 0.8 替代性强</span>
                <span><span style={{ display: "inline-block", width: 12, height: 12, background: "rgba(240, 173, 78, 0.6)", marginRight: 4, verticalAlign: "middle" }}></span>0.6-0.8 较高</span>
                <span><span style={{ display: "inline-block", width: 12, height: 12, background: "rgba(255, 235, 59, 0.4)", marginRight: 4, verticalAlign: "middle" }}></span>0.3-0.6 中等</span>
                <span><span style={{ display: "inline-block", width: 12, height: 12, background: "rgba(40, 167, 69, 0.4)", marginRight: 4, verticalAlign: "middle" }}></span>&lt; 0.3 分散好</span>
              </div>
              {/* 相关性较高的基金对 */}
              {correlation.pairs.filter(p => p.level === "very_high" || p.level === "high").length > 0 && (
                <div style={{ marginTop: 12, padding: 10, background: "rgba(220, 53, 69, 0.08)", borderRadius: 6 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>⚠ 高相关基金对（建议二选一）</p>
                  {correlation.pairs
                    .filter(p => p.level === "very_high" || p.level === "high")
                    .sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation))
                    .map((p, idx) => (
                      <span key={idx} style={{ fontSize: 12, marginRight: 16 }}>
                        {p.fund_a} ↔ {p.fund_b}：<strong>{p.correlation.toFixed(2)}</strong>
                      </span>
                    ))}
                </div>
              )}
            </div>
          )}

          {/* 组合风险预估 */}
          {fundCodes.length >= 2 && (
            <div className="card">
              <h2>组合风险预估</h2>
              <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
                调整各基金权重，实时计算组合波动率和分散化效果。分散化比率越低 = 分散效果越好。
              </p>
              {/* 权重滑块 */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
                {fundCodes.map((fc, idx) => (
                  <div key={fc} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                    <span style={{ width: 80, fontWeight: 600 }}>{fc}</span>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={Math.round((portfolioWeights[idx] || 0) * 100)}
                      onChange={async (e) => {
                        const newWeights = [...portfolioWeights];
                        newWeights[idx] = parseInt(e.target.value) / 100;
                        setPortfolioWeights(newWeights);
                        // 归一化后调用 API
                        const total = newWeights.reduce((a, b) => a + b, 0);
                        if (total > 0) {
                          const normalized = newWeights.map((w) => w / total);
                          fetchPortfolioRisk(fundCodes, normalized).then(setPortfolioRisk).catch(() => {});
                        }
                      }}
                      style={{ flex: 1 }}
                    />
                    <span style={{ width: 50, textAlign: "right", fontFamily: "monospace" }}>
                      {((portfolioWeights[idx] || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
              {/* 组合指标 */}
              {portfolioRisk && !portfolioRisk.error && (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
                    <div style={{ padding: 12, background: "var(--bg-alt)", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>组合年化波动率</div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "monospace" }}>
                        {(portfolioRisk.portfolio_volatility * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div style={{ padding: 12, background: "var(--bg-alt)", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>加权平均波动率</div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "monospace", color: "var(--muted)" }}>
                        {(portfolioRisk.weighted_avg_volatility * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div style={{ padding: 12, background: "var(--bg-alt)", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>风险降低</div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "monospace", color: "var(--pos)" }}>
                        -{(portfolioRisk.risk_reduction * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div style={{ padding: 12, background: "var(--bg-alt)", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>分散化比率</div>
                      <div style={{
                        fontSize: 20,
                        fontWeight: 700,
                        fontFamily: "monospace",
                        color: portfolioRisk.diversification_ratio <= 0.85 ? "var(--pos)" : portfolioRisk.diversification_ratio <= 0.95 ? "var(--warn)" : "var(--neg)"
                      }}>
                        {portfolioRisk.diversification_ratio.toFixed(2)}
                      </div>
                    </div>
                    <div style={{ padding: 12, background: "var(--bg-alt)", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>组合年化收益</div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "monospace" }}>
                        {(portfolioRisk.portfolio_return * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div style={{ padding: 12, background: "var(--bg-alt)", borderRadius: 6, textAlign: "center" }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>组合夏普</div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "monospace" }}>
                        {portfolioRisk.portfolio_sharpe.toFixed(2)}
                      </div>
                    </div>
                  </div>
                  {/* 分散化效果说明 */}
                  <div style={{
                    marginTop: 12,
                    padding: 10,
                    borderRadius: 6,
                    background: portfolioRisk.diversification_ratio <= 0.85
                      ? "rgba(40, 167, 69, 0.1)"
                      : portfolioRisk.diversification_ratio <= 0.95
                      ? "rgba(255, 193, 7, 0.1)"
                      : "rgba(220, 53, 69, 0.1)"
                  }}>
                    <p style={{ fontSize: 12, margin: 0 }}>
                      {portfolioRisk.diversification_ratio <= 0.85
                        ? "✓ 分散化效果良好：组合风险比加权平均降低了 15% 以上，基金之间互补性较强。"
                        : portfolioRisk.diversification_ratio <= 0.95
                        ? "△ 分散化效果一般：组合风险仅降低 5-15%，基金之间有一定相关性。"
                        : "✗ 分散化效果较差：组合风险几乎没有降低，基金之间相关性太高，建议替换部分基金。"}
                      （基于 {portfolioRisk.sample_count} 个交易日数据）
                    </p>
                  </div>
                  {/* 各基金波动率对比条 */}
                  <div style={{ marginTop: 12 }}>
                    <p style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>各基金年化波动率对比</p>
                    {fundCodes.map((fc, idx) => {
                      const vol = portfolioRisk.fund_volatilities[idx] || 0;
                      const maxVol = Math.max(...portfolioRisk.fund_volatilities, 0.01);
                      const w = portfolioRisk.weights[idx] || 0;
                      return (
                        <div key={fc} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, fontSize: 12 }}>
                          <span style={{ width: 80, fontWeight: 600 }}>{fc}</span>
                          <span style={{ width: 40, color: "var(--muted)", fontFamily: "monospace" }}>{(w * 100).toFixed(0)}%</span>
                          <div style={{ flex: 1, height: 16, background: "var(--bg-alt)", borderRadius: 3, overflow: "hidden" }}>
                            <div style={{
                              width: `${(vol / maxVol) * 100}%`,
                              height: "100%",
                              background: vol >= 0.4 ? "var(--neg)" : vol >= 0.25 ? "var(--warn)" : "var(--pos)",
                            }} />
                          </div>
                          <span style={{ width: 60, textAlign: "right", fontFamily: "monospace" }}>{(vol * 100).toFixed(2)}%</span>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          )}

          {/* 持仓重叠度 */}
          {overlap && !overlap.error && (
            <div className="card">
              <h2>持仓重叠度</h2>
              <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
                基于最新一期前 10 大持仓计算。重叠权重越高 = 替代性越强。
              </p>

              {/* 两两重叠度 */}
              <h3 style={{ fontSize: 14, color: "var(--text-2)", margin: "12px 0 6px" }}>两两重叠度</h3>
              <table>
                <thead>
                  <tr>
                    <th>基金对</th>
                    <th className="num">重叠股票数</th>
                    <th className="num">重叠权重</th>
                    <th>重叠度</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(overlap.pairwise_overlap).map(([pair, data]) => {
                    const pct = (data.overlap_weight * 100).toFixed(1);
                    const color = data.overlap_weight >= 0.3 ? "var(--neg)" : data.overlap_weight >= 0.15 ? "var(--warn)" : "var(--pos)";
                    return (
                      <tr key={pair}>
                        <td style={{ fontFamily: "ui-monospace, monospace" }}>{pair.replace("|", " vs ")}</td>
                        <td className="num">{data.overlap_count}</td>
                        <td className="num">{(data.overlap_weight * 100).toFixed(2)}%</td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 120 }}>
                            <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--surface-2)", overflow: "hidden", border: "1px solid var(--border)" }}>
                              <div style={{ width: `${Math.min(100, data.overlap_weight * 200)}%`, height: "100%", background: color }} />
                            </div>
                            <span style={{ fontSize: 11, color: "var(--text-2)" }}>{pct}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* 共同持仓 */}
              {overlap.common_holdings.length > 0 && (
                <>
                  <h3 style={{ fontSize: 14, color: "var(--text-2)", margin: "16px 0 6px" }}>
                    所有基金共同持仓（{overlap.common_holdings.length} 只）
                  </h3>
                  <table>
                    <thead>
                      <tr>
                        <th>股票代码</th>
                        <th>股票名称</th>
                        {overlap.fund_codes.map((fc) => (
                          <th key={fc} className="num" style={{ fontFamily: "ui-monospace, monospace" }}>{fc}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {overlap.common_holdings.map((h) => (
                        <tr key={h.stock_code}>
                          <td style={{ fontFamily: "ui-monospace, monospace" }}>{h.stock_code}</td>
                          <td>{h.stock_name || "-"}</td>
                          {overlap.fund_codes.map((fc) => (
                            <td key={fc} className="num">
                              {h.weights[fc] !== undefined ? `${(h.weights[fc] * 100).toFixed(2)}%` : "-"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              {overlap.common_holdings.length === 0 && (
                <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>
                  这几只基金没有完全共同持有的股票。
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
