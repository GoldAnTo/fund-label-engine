import { NavLink, Route, Routes, Navigate, useLocation } from "react-router-dom";
import FundReportPage from "./pages/FundReportPage";
import ReadyPoolPage from "./pages/ReadyPoolPage";
import SearchPage from "./pages/SearchPage";
import ComparePage from "./pages/ComparePage";
import CognitionPage from "./pages/CognitionPage";
import MultiCognitionPage from "./pages/MultiCognitionPage";
import LabelDefinitionsPage from "./pages/LabelDefinitionsPage";
import PriorityWorkbenchPage from "./pages/PriorityWorkbenchPage";
import { useEffect } from "react";

const NAV_GROUPS = [
  {
    title: "选基",
    links: [
      { to: "/cognition", label: "认知选基" },
      { to: "/multi-cognition", label: "多认知组合" },
    ],
  },
  {
    title: "研究",
    links: [
      { to: "/compare", label: "竞品横评" },
      { to: "/explorer", label: "风格总览" },
      { to: "/search", label: "风格筛选" },
      { to: "/priority", label: "基金研究优先级" },
    ],
  },
  {
    title: "治理",
    links: [
      { to: "/label-definitions", label: "规则定义" },
    ],
  },
];

const CRUMB_MAP: Record<string, string> = {
  cognition: "认知选基",
  "multi-cognition": "多认知组合",
  compare: "竞品横评",
  explorer: "风格总览",
  search: "风格筛选",
  priority: "基金研究优先级",
  funds: "基金",
  "label-definitions": "规则定义",
};

function Sidebar() {
  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-brand">
        <span className="logo">FE</span>
        <div className="name">
          <strong>基金选基台</strong>
          <small>Fund Insight</small>
        </div>
      </div>
      <nav>
        {NAV_GROUPS.map((group) => (
          <div key={group.title}>
            <div className="nav-section-title">{group.title}</div>
            {group.links.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.to === "/cognition"}>
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
          <strong>基金选基台</strong>
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
            <Route path="/" element={<Navigate to="/cognition" replace />} />
            <Route path="/cognition" element={<CognitionPage />} />
            <Route path="/multi-cognition" element={<MultiCognitionPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/explorer" element={<ReadyPoolPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/runs/:runId/funds/:fundCode" element={<FundReportPage />} />
            <Route path="/label-definitions" element={<LabelDefinitionsPage />} />
            <Route path="/priority" element={<PriorityWorkbenchPage />} />
            <Route path="/ready-pool" element={<Navigate to="/explorer" replace />} />
            <Route path="/portfolio" element={<Navigate to="/cognition" replace />} />
            <Route path="/runs" element={<Navigate to="/cognition" replace />} />
            <Route path="/diff" element={<Navigate to="/cognition" replace />} />
            <Route path="/review-queue" element={<Navigate to="/cognition" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
