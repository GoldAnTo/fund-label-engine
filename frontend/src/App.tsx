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

const NAV_GROUPS = [
  {
    title: "研究",
    links: [
      { to: "/explorer", label: "风格总览" },
      { to: "/search", label: "风格筛选" },
      { to: "/compare", label: "竞品横评" },
    ],
  },
  {
    title: "组合",
    links: [
      { to: "/portfolio", label: "组合工作台" },
      { to: "/review-queue", label: "复核队列" },
    ],
  },
  {
    title: "运维",
    links: [
      { to: "/runs", label: "批次管理" },
      { to: "/diff", label: "批次对比" },
    ],
  },
];

const CRUMB_MAP: Record<string, string> = {
  explorer: "风格总览",
  search: "风格筛选",
  compare: "竞品横评",
  portfolio: "组合工作台",
  "review-queue": "复核队列",
  runs: "批次",
  diff: "对比",
  funds: "基金",
};

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
        {NAV_GROUPS.map((group) => (
          <div key={group.title}>
            <div className="nav-section-title">{group.title}</div>
            {group.links.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.to === "/explorer"}>
                {l.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="app-sidebar-footer">
        <div>v1 · 数据同步正常</div>
      </div>
    </aside>
  );
}

function Topbar() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  return (
    <div className="app-topbar">
      <div className="breadcrumb">
        {segments.length === 0 ? (
          <strong>基金风格研究台</strong>
        ) : (
          segments.map((s, i) => (
            <span key={i} style={{ display: "inline-flex", gap: 5 }}>
              {i > 0 && <span className="sep">/</span>}
              <strong>{CRUMB_MAP[s] ?? s}</strong>
            </span>
          ))
        )}
      </div>
    </div>
  );
}

export default function App() {
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
            <Route path="/ready-pool" element={<Navigate to="/explorer" replace />} />
            <Route path="/runs/:runId" element={<RunDetailPage />} />
            <Route path="/runs/:runId/funds/:fundCode" element={<FundReportPage />} />
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
