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
