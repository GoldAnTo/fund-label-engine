import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchRuns, triggerRun } from "../api";
import { useAsync, runStatusLabel } from "../components";

export default function RunsPage() {
  const { data, error, loading, refresh } = useAsync(fetchRuns, []);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const handleRun = async () => {
    setRunning(true);
    setRunError(null);
    try {
      const result = await triggerRun("auto");
      // 跑完后刷新列表
      refresh();
      alert(`批次完成：已处理 ${result.processed} 只基金，批次 ${result.run_id.slice(0,12)}…`);
    } catch (e: unknown) {
      setRunError((e as Error).message || String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="page-head-v2">
        <div>
          <span className="eyebrow">OPS · 批次管理</span>
          <h1>批次管理</h1>
          <p>查看历史批次、运行新批次、监控处理状态与失败原因。</p>
        </div>
        <button onClick={handleRun} disabled={running} style={{ alignSelf: "flex-start" }}>
          {running ? "运行中…" : "运行批次"}
        </button>
      </div>
      <div className="context-bar">
        <div className="chip chip-status">
          <span className="dot" />
          <span className="label">服务</span>
          <span className="value">正常</span>
        </div>
        <div className="spacer" />
        {data && (
          <span className="meta" style={{ fontSize: 12, color: "var(--text-3)" }}>
            共 <strong>{data.length}</strong> 个批次
          </span>
        )}
      </div>
      {runError && <div className="alert alert-warn">{runError}</div>}

      <div className="card">
        <div className="section-head">
          <h2>批次列表</h2>
          <div className="meta">最近的标签计算批次（最多 50 条）</div>
        </div>
        {loading && (
          <div className="filter-empty" style={{ marginBottom: 12 }}>
            加载中…
          </div>
        )}
        {error && <div className="alert alert-warn">{error}</div>}
        {data && data.length > 0 && (
          <table className="table-v2">
            <thead>
              <tr>
                <th>批次编号</th>
                <th>开始时间</th>
                <th>规则版本</th>
                <th>状态</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((run) => (
                <tr key={run.run_id}>
                  <td>
                    <code>{run.run_id.slice(0, 12)}…</code>
                  </td>
                  <td>{run.run_at}</td>
                  <td>{run.rule_version}</td>
                  <td>{runStatusLabel(run.status)}</td>
                  <td className="num">
                    <Link to={`/runs/${run.run_id}`}>查看 →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && data.length === 0 && (
          <div className="empty-state">
            <div className="icon">∅</div>
            <div className="title">暂无批次</div>
            <div className="hint">点击上方"运行批次"按钮创建一个新批次。</div>
          </div>
        )}
      </div>
    </div>
  );
}