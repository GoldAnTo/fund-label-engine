import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";
import RunDiffPage from "./pages/RunDiffPage";
import FundReportPage from "./pages/FundReportPage";
import ReadyPoolPage from "./pages/ReadyPoolPage";
import SearchPage from "./pages/SearchPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import PortfolioWorkbenchPage from "./pages/PortfolioWorkbenchPage";

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>基金标签工作台</h1>
        <nav>
          <NavLink to="/ready-pool">可展示池</NavLink>
          <NavLink to="/review-queue">待处理队列</NavLink>
          <NavLink to="/runs">批次列表</NavLink>
          <NavLink to="/diff">批次对比</NavLink>
          <NavLink to="/search">基金检索</NavLink>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/portfolio" replace />} />
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
          <Route path="/review-queue" element={<ReviewQueuePage />} />
        </Routes>
      </main>
    </div>
  );
}
