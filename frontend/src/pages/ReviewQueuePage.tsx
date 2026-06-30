import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  downloadFile,
  fetchRelativeEligibility,
  fetchReviewQueue,
  fetchRuns,
  SearchResponse,
} from "../api";
import { ReviewActionBadge } from "../components";

function cleanReason(value: string) {
  return value
    .replaceAll("benchmark_source_status=benchmark_missing", "未配置业绩基准")
    .replaceAll("benchmark_source_status=missing_source", "缺少基准收益源")
    .replaceAll("benchmark_source_status=mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_source_status=unresolved", "基准组件未解析")
    .replaceAll("benchmark_source_missing", "缺少基准收益源")
    .replaceAll("benchmark_mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_unresolved", "基准组件未解析")
    .replaceAll("benchmark_missing", "未配置业绩基准")
    .replaceAll("nav_window_insufficient", "收益窗口不足")
    .replace(/\b[A-Z0-9_]+:/g, "");
}

export default function ReviewQueuePage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [blocked, setBlocked] = useState<Awaited<ReturnType<typeof fetchRelativeEligibility>> | null>(null);
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
      fetchReviewQueue(runId),
      fetchRelativeEligibility(runId, "blocked"),
    ])
      .then(([reviewQueue, blockedPool]) => {
        setData(reviewQueue);
        setBlocked(blockedPool);
      })
      .catch((e) => setError(e.message));
  }, [runId]);

  return (
    <div className="card">
      <h2>待处理队列</h2>
      <p className="muted">汇总人工复核和基准缺口任务，第一版只读，处理入口仍在单基金报告。</p>
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

      {blocked && blocked.results.length > 0 && (
        <>
          <h3>基准缺口任务</h3>
          <table>
            <thead>
              <tr>
                <th>基金</th>
                <th>任务类型</th>
                <th>原因或组件</th>
                <th>建议动作</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {blocked.results.slice(0, 80).map((r) => (
                <tr key={`blocked-${r.fund_code}`}>
                  <td><code>{r.fund_code}</code><div className="muted">{r.fund_name}</div></td>
                  <td>基准缺口</td>
                  <td className="muted">{cleanReason(r.blocking_components || r.blocking_reason || "-")}</td>
                  <td>补数据源、确认映射或补解析规则</td>
                  <td><Link to={`/runs/${blocked.run_id}/funds/${r.fund_code}`}>查看报告 →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {data && (
        <>
          <h3>人工复核任务</h3>
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
        </>
      )}
      {data && data.results.length === 0 && (
        <p className="muted">当前批次没有需要人工复核的基金。</p>
      )}
    </div>
  );
}
