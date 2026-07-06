import { NavLink, Route, Routes, Navigate, useLocation } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";
import RunDiffPage from "./pages/RunDiffPage";
import FundReportPage from "./pages/FundReportPage";
import ReadyPoolPage from "./pages/ReadyPoolPage";
import SearchPage from "./pages/SearchPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import PortfolioWorkbenchPage from "./pages/PortfolioWorkbenchPage";
import ComparePage from "./pages/ComparePage";
import { useEffect } from "react";

// 侧边栏导航分组
const RESEARCH_LINKS = [
  { to: "/explorer", label: "风格总览", icon: "◎" },
  { to: "/search", label: "风格筛选", icon: "▤" },
  { to: "/compare", label: "竞品横评", icon: "⊕" },
  { to: "/ready-pool", label: "展示池", icon: "✓" },
];

const PORTFOLIO_LINKS = [
  { to: "/portfolio", label: "组合工作台", icon: "◆" },
  { to: "/review-queue", label: "复核队列", icon: "✎" },
];

const OPS_LINKS = [
  { to: "/runs", label: "批次管理", icon: "▣" },
  { to: "/diff", label: "批次对比", icon: "⇄" },
];

function Sidebar() {
  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-brand">
        <span className="logo">FE</span>
        <div className="name">
          <strong>基金风格研究台</strong>
          <small>Fund Label Engine</small>
        </div>
      </div>

      <nav>
        <div className="nav-section-title">研究</div>
        {RESEARCH_LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.to === "/explorer"}>
            <span className="icon">{l.icon}</span>
            {l.label}
          </NavLink>
        ))}

        <div className="nav-section-title">组合</div>
        {PORTFOLIO_LINKS.map((l) => (
          <NavLink key={l.to} to={l.to}>
            <span className="icon">{l.icon}</span>
            {l.label}
          </NavLink>
        ))}

        <div className="nav-section-title">运维 / 审计</div>
        {OPS_LINKS.map((l) => (
          <NavLink key={l.to} to={l.to}>
            <span className="icon">{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>

      <div className="app-sidebar-footer">
        <div>v1 · 基金标签研究台</div>
        <div className="indicator">
          <span className="dot" />
          数据同步正常
        </div>
      </div>
    </aside>
  );
}

function Topbar() {
  const location = useLocation();
  // 路径 → 面包屑
  const segments = location.pathname.split("/").filter(Boolean);
  const crumbMap: Record<string, string> = {
    explorer: "风格总览",
    search: "风格筛选",
    compare: "竞品横评",
    "ready-pool": "展示池",
    portfolio: "组合工作台",
    "review-queue": "复核队列",
    runs: "批次",
    diff: "对比",
    funds: "基金",
  };
  return (
    <div className="app-topbar">
      <div className="breadcrumb">
        {segments.length === 0 ? (
          <strong>基金风格研究台</strong>
        ) : (
          segments.map((s, i) => (
            <span key={i} style={{ display: "inline-flex", gap: 6 }}>
              {i > 0 && <span className="sep">/</span>}
              <strong>{crumbMap[s] ?? s}</strong>
            </span>
          ))
        )}
      </div>
      <div className="context-actions">
        <a
          href="https://github.com/GoldAnTo/fund-label-engine"
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: 12, color: "var(--text-3)" }}
        >
          文档 ↗
        </a>
      </div>
    </div>
  );
}

export default function App() {
  // 全局：路由切换时滚动到顶部
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <div className="app-shell-grid">
      <Sidebar />
      <div className="app-main">
        <Topbar />
        <main className="main">
          <Routes>
            <Route path="/" element={<Navigate to="/explorer" replace />} />
            <Route path="/explorer" element={<ReadyPoolPage />} />
            <Route path="/portfolio" element={<PortfolioWorkbenchPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/ready-pool" element={<ReadyPoolPage />} />
            <Route path="/runs/:runId" element={<RunDetailPage />} />
            <Route
              path="/runs/:runId/funds/:fundCode"
              element={<FundReportPage />}
            />
            <Route path="/diff" element={<RunDiffPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/review-queue" element={<ReviewQueuePage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
