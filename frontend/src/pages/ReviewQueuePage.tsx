import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  downloadFile,
  fetchRuns,
  fetchWorkbenchSummary,
  fetchWorkbenchTasks,
  type WorkbenchSummary,
  type WorkbenchTasksResponse,
} from "../api";
import { styleName } from "../styleConfig";

function taskTypeLabel(value: string) {
  const labels: Record<string, string> = {
    benchmark_gap: "基准缺口",
    manual_review: "人工复核",
    observe_signal: "观察信号",
    calibration_signal: "待校准信号",
  };
  return labels[value] ?? value;
}

function priorityLabel(value: string) {
  const labels: Record<string, string> = {
    high: "高",
    medium: "中",
    low: "低",
  };
  return labels[value] ?? value;
}

function taskTarget(task: WorkbenchTasksResponse["results"][number]) {
  if (task.fund_code) {
    return <><code>{task.fund_code}</code><div className="muted">{task.fund_name || "单基金任务"}</div></>;
  }
  if (task.label_code) {
    return <><strong>{styleName(task.label_code)}</strong><div className="muted">{task.label_name || "标签任务"}</div></>;
  }
  return <span className="muted">-</span>;
}

export default function ReviewQueuePage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [summary, setSummary] = useState<WorkbenchSummary | null>(null);
  const [tasks, setTasks] = useState<WorkbenchTasksResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns()
      .then((rs) => {
        setRuns(rs);
        if (rs.length > 0) setRunId(rs[0].run_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!runId) return;
    setError(null);
    Promise.all([
      fetchWorkbenchSummary(runId),
      fetchWorkbenchTasks(runId),
    ])
      .then(([summaryPayload, taskPayload]) => {
        setSummary(summaryPayload);
        setTasks(taskPayload);
      })
      .catch((e) => setError(e.message));
  }, [runId]);

  return (
    <div className="card">
      <h2>待处理队列</h2>
      <p className="muted">汇总基准缺口、人工复核、观察信号和待校准信号，处理入口仍在单基金报告或标签检索。</p>
      <div className="toolbar">
        <label>
          批次&nbsp;
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id.slice(0, 8)}… ({r.run_at})
              </option>
            ))}
          </select>
        </label>
        {runId && (
          <>
            <button
              onClick={() =>
                downloadFile(
                  `/v1/runs/${runId}/review-queue/export?format=csv`,
                  `review_queue_${runId}.csv`
                )
              }
            >
              导出人工复核 CSV
            </button>
            <button
              onClick={() =>
                downloadFile(
                  `/v1/runs/${runId}/review-queue/export?format=xlsx`,
                  `review_queue_${runId}.xlsx`
                )
              }
            >
              导出人工复核 XLSX
            </button>
          </>
        )}
      </div>
      {error && <div className="error">{error}</div>}

      {summary && (
        <div className="metrics-grid">
          <div className="metric-tile"><span>全部任务</span><strong>{tasks?.total_count ?? 0}</strong></div>
          <div className="metric-tile"><span>基准缺口</span><strong>{summary.task_type_counts.benchmark_gap ?? 0}</strong></div>
          <div className="metric-tile"><span>人工复核</span><strong>{summary.task_type_counts.manual_review ?? 0}</strong></div>
          <div className="metric-tile"><span>观察 / 校准</span><strong>{(summary.task_type_counts.observe_signal ?? 0) + (summary.task_type_counts.calibration_signal ?? 0)}</strong></div>
        </div>
      )}

      {tasks && tasks.results.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>优先级</th>
              <th>任务类型</th>
              <th>对象</th>
              <th>原因</th>
              <th>建议动作</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tasks.results.map((task) => (
              <tr key={task.task_id}>
                <td><span className="badge badge-manual_review">{priorityLabel(task.priority)}</span></td>
                <td>{taskTypeLabel(task.task_type)}</td>
                <td>{taskTarget(task)}</td>
                <td className="muted">{task.reason_text || task.reason_code}</td>
                <td>{task.suggested_action}</td>
                <td>
                  {task.fund_code ? (
                    <Link to={`/runs/${tasks.run_id}/funds/${task.fund_code}`}>查看报告 →</Link>
                  ) : task.label_code ? (
                    <Link to={`/search?run_id=${tasks.run_id}&label_code=${task.label_code}`}>查看基金 →</Link>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {tasks && tasks.results.length === 0 && (
        <p className="muted">当前批次没有待处理任务。</p>
      )}
    </div>
  );
}
