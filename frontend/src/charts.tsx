import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LabelList,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Legend,
} from "recharts";

/* ============================================================
   可复用图表组件（基于 Recharts）
   借鉴 Wealthfolio / Ghostfolio 的数据可视化风格
   ============================================================ */

const CHART_COLORS = [
  "#3b82f6", // blue-500
  "#8b5cf6", // violet-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#06b6d4", // cyan-500
  "#ec4899", // pink-500
  "#84cc16", // lime-500
  "#f97316", // orange-500
  "#6366f1", // indigo-500
];

/* --- 环形图：组合配置比例 --- */
export interface DonutDatum {
  name: string;
  value: number;
  color?: string;
}

export function DonutChart({
  data,
  size = 200,
  innerRadius = 50,
  outerRadius = 80,
  centerLabel,
  centerValue,
}: {
  data: DonutDatum[];
  size?: number;
  innerRadius?: number;
  outerRadius?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  return (
    <div style={{ position: "relative", width: size, height: size, margin: "0 auto" }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={2}
            dataKey="value"
            stroke="none"
          >
            {data.map((entry, i) => (
              <Cell
                key={`cell-${i}`}
                fill={entry.color || CHART_COLORS[i % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip
            formatter={(v) => `${Number(v ?? 0).toFixed(1)}%`}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid var(--border)",
              background: "var(--surface)",
              fontSize: "12px",
              boxShadow: "var(--shadow)",
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      {centerValue && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            textAlign: "center",
            pointerEvents: "none",
          }}
        >
          <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--text)", lineHeight: 1.2 }}>
            {centerValue}
          </div>
          {centerLabel && (
            <div style={{ fontSize: "11px", color: "var(--text-3)", marginTop: "2px" }}>
              {centerLabel}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* --- 水平条形图：持仓穿透 / 行业暴露 --- */
export interface BarDatum {
  name: string;
  value: number;
  label?: string;
}

export function HorizontalBarChart({
  data,
  unit = "%",
  height = 240,
  color = "#3b82f6",
  formatValue,
}: {
  data: BarDatum[];
  unit?: string;
  height?: number;
  color?: string;
  formatValue?: (v: number) => string;
}) {
  const chartData = data.map((d) => ({
    ...d,
    label: formatValue ? formatValue(d.value) : `${d.value.toFixed(1)}${unit}`,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 40, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke="var(--border)" strokeDasharray="3 3" />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="name"
          width={90}
          tick={{ fontSize: 12, fill: "var(--text-2)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(v) => {
            const n = Number(v ?? 0);
            return formatValue ? formatValue(n) : `${n.toFixed(2)}${unit}`;
          }}
          cursor={{ fill: "var(--surface-2)" }}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
        />
        <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} barSize={18}>
          <LabelList dataKey="label" position="right" style={{ fontSize: 11, fill: "var(--text-2)" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- 迷你柱状图：用于 KPI 卡片中的趋势展示 --- */
export function MiniBars({
  data,
  height = 32,
  color = "var(--accent)",
}: {
  data: number[];
  height?: number;
  color?: string;
}) {
  const max = Math.max(...data, 0.001);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height }}>
      {data.map((v, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: `${(v / max) * 100}%`,
            minHeight: 2,
            background: color,
            opacity: 0.4 + 0.6 * (v / max),
            borderRadius: "2px 2px 0 0",
            transition: "height 0.3s ease",
          }}
        />
      ))}
    </div>
  );
}

/* --- 加载骨架 --- */
export function Skeleton({ width = "100%", height = 20, radius = 4 }: { width?: string | number; height?: string | number; radius?: number }) {
  return (
    <div
      className="skeleton"
      style={{
        width,
        height,
        borderRadius: radius,
      }}
    />
  );
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card skeleton-card">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={i === 0 ? 16 : 12} width={i === 0 ? "60%" : `${90 - i * 10}%`} />
      ))}
    </div>
  );
}

/* --- 空状态 --- */
export function EmptyState({ icon, title, hint }: { icon?: string; title: string; hint?: string }) {
  return (
    <div className="empty-state-v2">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <div className="empty-state-title">{title}</div>
      {hint && <div className="empty-state-hint">{hint}</div>}
    </div>
  );
}

/* --- 雷达图：估值多维度对比 --- */
export interface RadarDatum {
  metric: string;
  value: number;
  benchmark: number;
}

export function ValuationRadar({ data }: { data: RadarDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height={250}>
      <RadarChart data={data}>
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: "var(--text-2)" }} />
        <PolarRadiusAxis tick={{ fontSize: 10, fill: "var(--text-3)" }} />
        <Radar name="当前" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
        <Radar name="基准" dataKey="benchmark" stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.1} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

/* --- 对比柱图：支持/反对证据数量 --- */
export function ComparisonBar({ positive, negative }: { positive: number; negative: number }) {
  const data = [
    { name: "支持证据", count: positive, fill: "#16a34a" },
    { name: "反对证据", count: negative, fill: "#dc2626" },
  ];
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ left: 0, right: 20, top: 10, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--text-2)" }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={60}>
          {data.map((entry, i) => (
            <Cell key={`cell-${i}`} fill={entry.fill} />
          ))}
          <LabelList dataKey="count" position="top" style={{ fontSize: 13, fontWeight: 600, fill: "var(--text)" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- 预期差瀑布图：正向绿色，负向红色 --- */
export interface GapWaterfallDatum {
  name: string;
  value: number;
  positive: boolean;
}

export function GapWaterfall({ data }: { data: GapWaterfallDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: 0, right: 20, top: 10, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--text-2)" }} axisLine={false} tickLine={false} interval={0} angle={-20} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
          formatter={(v) => Number(v ?? 0).toFixed(1)}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={36}>
          {data.map((entry, i) => (
            <Cell key={`cell-${i}`} fill={entry.positive ? "#16a34a" : "#dc2626"} />
          ))}
          <LabelList dataKey="value" position="top" style={{ fontSize: 11, fontWeight: 600, fill: "var(--text-2)" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- 场景收益柱图：bear/base/bull --- */
export interface ScenarioBarDatum {
  name: string;
  return: number;
  probability: number;
}

export function ScenarioBar({ data }: { data: ScenarioBarDatum[] }) {
  const colors = ["#dc2626", "#2563eb", "#16a34a"];
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: 0, right: 20, top: 10, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--text-2)" }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} unit="%" />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
          formatter={(v: any) => `${Number(v ?? 0) > 0 ? "+" : ""}${Number(v ?? 0)}%`}
        />
        <Bar dataKey="return" radius={[4, 4, 0, 0]} barSize={50}>
          {data.map((_, i) => (
            <Cell key={`cell-${i}`} fill={colors[i % colors.length]} />
          ))}
          <LabelList dataKey="return" position="top" style={{ fontSize: 12, fontWeight: 600, fill: "var(--text)" }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- 雷达图：IC Review 三支柱 --- */
export interface RadarVizDatum {
  metric: string;
  value: number;
}

export function RadarChartViz({ data }: { data: RadarVizDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data}>
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: "var(--text-2)" }} />
        <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "var(--text-3)" }} />
        <Radar name="得分" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

/* --- 瀑布图：预期差（正向绿色，负向红色，合计灰色） --- */
export interface WaterfallDatum {
  label: string;
  value: number;
  type: "pos" | "neg" | "total";
}

export function WaterfallChart({ data }: { data: WaterfallDatum[] }) {
  // 计算瀑布图的累积值，生成 base（透明底）和 barHeight（实际柱高）
  let cumulative = 0;
  const chartData = data.map((d) => {
    const prev = cumulative;
    if (d.type === "total") {
      cumulative = d.value;
    } else {
      cumulative += d.value;
    }
    const base = d.type === "total" ? 0 : Math.min(prev, cumulative);
    const barHeight = d.type === "total" ? d.value : Math.abs(d.value);
    return {
      label: d.label,
      base,
      barHeight,
      value: d.value,
      type: d.type,
      fill: d.type === "pos" ? "#16a34a" : d.type === "neg" ? "#dc2626" : "#6b7280",
    };
  });

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={chartData} margin={{ left: 0, right: 20, top: 10, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: "var(--text-2)" }}
          axisLine={false}
          tickLine={false}
          interval={0}
          angle={-20}
          textAnchor="end"
          height={60}
        />
        <YAxis tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
          formatter={(v: any) => Number(v ?? 0).toFixed(1)}
        />
        <Bar dataKey="base" stackId="wf" fill="transparent" />
        <Bar dataKey="barHeight" stackId="wf" radius={[4, 4, 0, 0]} barSize={36}>
          {chartData.map((entry, i) => (
            <Cell key={`cell-${i}`} fill={entry.fill} />
          ))}
          <LabelList
            dataKey="value"
            position="top"
            style={{ fontSize: 11, fontWeight: 600, fill: "var(--text-2)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- 场景分析柱图：bear / base / bull --- */
export interface ScenarioChartDatum {
  scenario: string;
  return: number;
  probability: number;
  color: string;
}

export function ScenarioChart({ data }: { data: ScenarioChartDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: 0, right: 20, top: 10, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="scenario"
          tick={{ fontSize: 12, fill: "var(--text-2)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--text-3)" }}
          axisLine={false}
          tickLine={false}
          unit="%"
        />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "12px",
            boxShadow: "var(--shadow)",
          }}
          formatter={(v: any) => `${Number(v ?? 0) > 0 ? "+" : ""}${Number(v ?? 0)}%`}
        />
        <Bar dataKey="return" radius={[4, 4, 0, 0]} barSize={50}>
          {data.map((entry, i) => (
            <Cell key={`cell-${i}`} fill={entry.color} />
          ))}
          <LabelList
            dataKey="return"
            position="top"
            style={{ fontSize: 12, fontWeight: 600, fill: "var(--text)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --- 估值仪表盘：半圆形 Gauge --- */
export function ValuationGauge({ percentile, label = "估值分位" }: { percentile: number; label?: string }) {
  const pct = Math.min(100, Math.max(0, percentile));
  const angle = 180 - (pct / 100) * 180; // 0% = 180deg, 100% = 0deg
  const radian = (angle * Math.PI) / 180;
  const cx = 100, cy = 90, r = 70;
  const needleX = cx + r * Math.cos(radian);
  const needleY = cy - r * Math.sin(radian);

  const zoneColor = pct < 30 ? "#16a34a" : pct < 70 ? "#ca8a04" : "#dc2626";
  const zoneLabel = pct < 30 ? "偏低" : pct < 70 ? "合理" : pct > 85 ? "极度偏贵" : "偏贵";

  return (
    <div className="flex flex-col items-center">
      <svg width="200" height="110" viewBox="0 0 200 110">
        {/* Background semicircle */}
        <path d={`M 30 90 A 70 70 0 0 1 170 90`} fill="none" stroke="var(--surface-2)" strokeWidth="16" strokeLinecap="round" />
        {/* Green zone */}
        <path d={`M 30 90 A 70 70 0 0 1 70 28`} fill="none" stroke="#16a34a" strokeWidth="16" strokeLinecap="round" opacity="0.3" />
        {/* Yellow zone */}
        <path d={`M 70 28 A 70 70 0 0 1 130 28`} fill="none" stroke="#ca8a04" strokeWidth="16" strokeLinecap="round" opacity="0.3" />
        {/* Red zone */}
        <path d={`M 130 28 A 70 70 0 0 1 170 90`} fill="none" stroke="#dc2626" strokeWidth="16" strokeLinecap="round" opacity="0.3" />
        {/* Needle */}
        <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke={zoneColor} strokeWidth="3" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="5" fill={zoneColor} />
      </svg>
      <div className="text-2xl font-bold font-mono" style={{ color: zoneColor, marginTop: -8 }}>{pct.toFixed(0)}%</div>
      <div className="text-xs text-text-3">{label} · {zoneLabel}</div>
    </div>
  );
}
