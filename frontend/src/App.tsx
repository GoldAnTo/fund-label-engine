import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";
import RunDiffPage from "./pages/RunDiffPage";
import FundReportPage from "./pages/FundReportPage";
import ReadyPoolPage from "./pages/ReadyPoolPage";
import SearchPage from "./pages/SearchPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import PortfolioWorkbenchPage from "./pages/PortfolioWorkbenchPage";
import ComparePage from "./pages/ComparePage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/explorer" className="brand-mark">
          <span>FE</span>
          <strong>基金风格研究台</strong>
        </NavLink>
        <nav className="topnav" aria-label="主导航">
          <NavLink to="/explorer">风格总览</NavLink>
          <NavLink to="/search">风格筛选</NavLink>
          <NavLink to="/compare">竞品横评</NavLink>
          <NavLink to="/ready-pool">展示池</NavLink>
          <NavLink to="/portfolio">组合工作台</NavLink>
          <NavLink to="/review-queue">复核队列</NavLink>
          <NavLink to="/runs">批次</NavLink>
          <NavLink to="/diff">对比</NavLink>
        </nav>
      </header>
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
  );
}
