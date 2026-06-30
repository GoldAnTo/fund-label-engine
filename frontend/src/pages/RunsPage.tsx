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
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ margin: 0 }}>批次列表</h2>
            <p className="muted" style={{ margin: "4px 0 0" }}>
              最近的标签计算批次（最多 50 条）。
            </p>
          </div>
          <button onClick={handleRun} disabled={running}>
            {running ? "运行中…" : "运行批次"}
          </button>
        </div>
        {runError && <div className="error" style={{ marginTop: 12 }}>{runError}</div>}
      </div>
      <div className="card">
        {loading && <p>加载中...</p>}
        {error && <div className="error">{error}</div>}
        {data && data.length > 0 && (
          <table>
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
                  <td><code>{run.run_id.slice(0, 12)}…</code></td>
                  <td>{run.run_at}</td>
                  <td>{run.rule_version}</td>
                  <td>{runStatusLabel(run.status)}</td>
                  <td>
                    <Link to={`/runs/${run.run_id}`}>查看 →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && data.length === 0 && <p>暂无批次，点击上方"运行批次"按钮创建一个新批次。</p>}
      </div>
    </div>
  );
}