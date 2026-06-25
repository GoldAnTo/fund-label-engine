import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { downloadFile, fetchReviewQueue, fetchRuns, SearchResponse } from "../api";
import { ReviewActionBadge } from "../components";

export default function ReviewQueuePage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
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
    fetchReviewQueue(runId).then(setData).catch((e) => setError(e.message));
  }, [runId]);

  return (
    <div className="card">
      <h2>复核队列</h2>
      <p className="muted">仅列出最新批次中标记为 manual_review 的基金。</p>
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
              导出 CSV
            </button>
            <button
              onClick={() =>
                downloadFile(
                  `/v1/runs/${runId}/review-queue/export?format=xlsx`,
                  `review_queue_${runId}.xlsx`
                )
              }
            >
              导出 XLSX
            </button>
          </>
        )}
      </div>
      {error && <div className="error">{error}</div>}
      {data && (
        <table>
          <thead>
            <tr>
              <th>基金代码</th>
              <th>标签数</th>
              <th>缺失字段</th>
              <th>状态</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((r) => (
              <tr key={r.fund_code}>
                <td><code>{r.fund_code}</code></td>
                <td>{r.label_count}</td>
                <td>{r.missing_field_count}</td>
                <td><ReviewActionBadge value={r.review_action} /></td>
                <td>
                  <Link to={`/runs/${data.run_id}/funds/${r.fund_code}`}>
                    复核 →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {data && data.results.length === 0 && (
        <p className="muted">当前批次没有 manual_review 基金。</p>
      )}
    </div>
  );
}
