import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchCompare,
  fetchHoldingsOverlap,
  fetchRuns,
  type CompareResponse,
  type HoldingsOverlapResponse,
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
        const [comp, ov] = await Promise.all([
          fetchCompare(runId, fundCodes),
          fetchHoldingsOverlap(fundCodes, 10),
        ]);
        setCompare(comp);
        setOverlap(ov);
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
      <div className="page-head">
        <h1>竞品横评</h1>
        <p>选 2-6 只基金并排对比风格、指标、持仓重叠度。</p>
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
