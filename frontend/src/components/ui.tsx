/* ============================================================
   共享 UI 组件 - Tailwind CSS 投研组件库
   ============================================================ */

import React from "react";

// === Card ===
export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-surface border border-border rounded-lg ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between px-4 py-3 border-b border-border">
      <div>
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        {subtitle && <p className="text-xs text-text-3 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`p-4 ${className}`}>{children}</div>;
}

// === Badge ===
type BadgeVariant = "pos" | "neg" | "warn" | "accent" | "neutral";

const badgeStyles: Record<BadgeVariant, string> = {
  pos: "bg-pos-soft text-pos-text border-pos/30",
  neg: "bg-neg-soft text-neg-text border-neg/30",
  warn: "bg-warn-soft text-warn-text border-warn/30",
  accent: "bg-accent-soft text-accent-text border-accent/30",
  neutral: "bg-surface-2 text-text-2 border-border",
};

export function Badge({ children, variant = "neutral", className = "" }: { children: React.ReactNode; variant?: BadgeVariant; className?: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${badgeStyles[variant]} ${className}`}>
      {children}
    </span>
  );
}

// === ProgressBar ===
export function ProgressBar({ value, max = 100, variant = "accent", label, showValue = true }: { value: number; max?: number; variant?: BadgeVariant; label?: string; showValue?: boolean }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const colors: Record<BadgeVariant, string> = {
    pos: "bg-pos",
    neg: "bg-neg",
    warn: "bg-warn",
    accent: "bg-accent",
    neutral: "bg-text-3",
  };
  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between text-xs text-text-2 mb-1">
          <span>{label}</span>
          {showValue && <span className="font-mono text-text">{value.toFixed(1)}</span>}
        </div>
      )}
      <div className="w-full h-2 bg-surface-2 rounded-full overflow-hidden">
        <div className={`h-full ${colors[variant]} rounded-full transition-all duration-300`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// === Stat ===
export function Stat({ label, value, unit, variant }: { label: string; value: string | number | null | undefined; unit?: string; variant?: BadgeVariant }) {
  const valueColor: Record<BadgeVariant, string> = {
    pos: "text-pos",
    neg: "text-neg",
    warn: "text-warn",
    accent: "text-accent",
    neutral: "text-text",
  };
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-text-3">{label}</span>
      <span className={`text-lg font-semibold font-mono ${variant ? valueColor[variant] : "text-text"}`}>
        {value ?? "--"}
        {unit && <span className="text-xs text-text-3 ml-0.5">{unit}</span>}
      </span>
    </div>
  );
}

// === Table ===
export function Table({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <th className={`text-left px-3 py-2 text-xs font-medium text-text-3 border-b border-border whitespace-nowrap ${className}`}>{children}</th>;
}

export function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2 text-text border-b border-border/50 ${className}`}>{children}</td>;
}

// === Tabs ===
export function TabBar({ tabs, active, onChange }: { tabs: { id: string; label: string }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="flex gap-1 border-b border-border px-4">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
            active === tab.id
              ? "border-accent text-accent"
              : "border-transparent text-text-2 hover:text-text"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

// === Section Title ===
export function SectionTitle({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <h4 className={`text-xs font-semibold text-text-2 uppercase tracking-wide mb-2 ${className}`}>{children}</h4>;
}

// === Divider ===
export function Divider({ className = "" }: { className?: string }) {
  return <div className={`border-t border-border my-3 ${className}`} />;
}

// === Loading ===
export function Loading({ text = "分析中..." }: { text?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-text-2">
      <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      <span className="text-sm">{text}</span>
    </div>
  );
}

// === Error ===
export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 py-12">
      <div className="text-neg text-sm">{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="px-4 py-2 text-sm text-accent border border-accent/30 rounded-lg hover:bg-accent-soft transition-colors">
          重试
        </button>
      )}
    </div>
  );
}

// === Empty State ===
export function EmptyState({ message }: { message: string }) {
  return <div className="text-center py-12 text-text-3 text-sm">{message}</div>;
}
