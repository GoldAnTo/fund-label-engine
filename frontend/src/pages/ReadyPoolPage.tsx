import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRelativeEligibility, fetchRuns, RelativeEligibilityResponse } from "../api";

const STATUS_LABELS: Record<string, string> = {
  relative_label_ready: "可展示",
  benchmark_source_missing: "缺少基准收益源",
  benchmark_mapping_required: "需要确认基准映射",
  benchmark_unresolved: "基准组件未解析",
  benchmark_missing: "未配置业绩基准",
  nav_window_insufficient: "收益窗口不足",
};

const SOURCE_STATUS_LABELS: Record<string, string> = {
  ready: "基准已就绪",
  missing_source: "缺少收益源",
  mapping_required: "需要映射",
  unresolved: "未解析",
  benchmark_missing: "无业绩基准",
};

function statusLabel(value: string) {
  return STATUS_LABELS[value] ?? value;
}

function sourceStatusLabel(value: string) {
  return SOURCE_STATUS_LABELS[value] ?? value;
}

function displayText(value: string) {
  return value
    .replaceAll("benchmark_source_status=benchmark_missing", "未配置业绩基准")
    .replaceAll("benchmark_source_status=missing_source", "缺少基准收益源")
    .replaceAll("benchmark_source_status=mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_source_status=unresolved", "基准组件未解析")
    .replaceAll("relative_label_ready", "可展示")
    .replaceAll("benchmark_source_missing", "缺少基准收益源")
    .replaceAll("benchmark_mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_unresolved", "基准组件未解析")
    .replaceAll("benchmark_missing", "未配置业绩基准")
    .replaceAll("nav_window_insufficient", "收益窗口不足")
    .replace(/\b[A-Z0-9_]+:/g, "");
}

function statusClass(value: string) {
  return value === "relative_label_ready" ? "badge-observe" : "badge-manual_review";
}

export default function ReadyPoolPage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [status, setStatus] = useState<"all" | "ready" | "blocked">("all");
  const [data, setData] = useState<RelativeEligibilityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
    setLoading(true);
    setError(null);
    fetchRelativeEligibility(runId, status)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId, status]);

  return (
    <div>
      <div className="card">
        <h2>一期 v1 可展示基金池</h2>
        <p className="muted">
          只有通过相对基准门禁的基金，才在前台展示阿尔法、贝塔和超额收益。
        </p>
        <div className="toolbar">
          <label>
            批次&nbsp;
            <select value={runId} onChange={(e) => setRunId(e.target.value)}>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id.slice(0, 8)}… ({run.run_at})
                </option>
              ))}
            </select>
          </label>
          <label>
            状态&nbsp;
            <select value={status} onChange={(e) => setStatus(e.target.value as "all" | "ready" | "blocked")}>
              <option value="all">全部</option>
              <option value="ready">仅看可展示</option>
              <option value="blocked">仅看暂不可展示</option>
            </select>
          </label>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      {data && (
        <div className="metric-grid">
          <div className="metric-tile">
            <span>正式清单</span>
            <strong>{data.total_funds}</strong>
          </div>
          <div className="metric-tile metric-ready">
            <span>可展示</span>
            <strong>{data.ready_count}</strong>
          </div>
          <div className="metric-tile metric-blocked">
            <span>暂不可展示</span>
            <strong>{data.blocked_count}</strong>
          </div>
        </div>
      )}

      {data && (
        <div className="card">
          <h2>Blocked 结构</h2>
          <table>
            <thead>
              <tr><th>状态</th><th>基金数</th></tr>
            </thead>
            <tbody>
              {Object.entries(data.status_counts).map(([key, count]) => (
                <tr key={key}>
                  <td><span className={`badge ${statusClass(key)}`}>{statusLabel(key)}</span></td>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.blocker_groups.length > 0 && (
        <div className="card">
          <h2>主要阻塞项</h2>
          <p className="muted">按门禁原因和基准组件聚合，优先处理影响基金数最多的缺口。</p>
          <table>
            <thead>
              <tr>
                <th>门禁原因</th>
                <th>组件 / 规则</th>
                <th>基金数</th>
                <th>样例基金</th>
              </tr>
            </thead>
            <tbody>
              {data.blocker_groups.slice(0, 12).map((group) => (
                <tr key={group.key}>
                  <td><span className={`badge ${statusClass(group.status)}`}>{statusLabel(group.status)}</span></td>
                  <td className="muted">{displayText(group.component)}</td>
                  <td>{group.count}</td>
                  <td className="muted">{group.sample_fund_codes.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h2>基金列表</h2>
        {loading && <p>加载中...</p>}
        {data && data.results.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>基金</th>
                <th>相对标签状态</th>
                <th>基准源</th>
                <th>净值 / 基准样本</th>
                <th>阻塞组件</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((row) => (
                <tr key={row.fund_code}>
                  <td>
                    <code>{row.fund_code}</code>
                    <div className="muted">{row.fund_name}</div>
                  </td>
                  <td><span className={`badge ${statusClass(row.relative_label_status)}`}>{statusLabel(row.relative_label_status)}</span></td>
                  <td>{sourceStatusLabel(row.benchmark_source_status)}</td>
                  <td>{row.nav_sample_count} / {row.benchmark_sample_count}</td>
                  <td className="muted">{displayText(row.blocking_components || row.blocking_reason || "-")}</td>
                  <td>
                    <Link to={`/runs/${data.run_id}/funds/${row.fund_code}`}>查看报告 →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && data.results.length === 0 && <p className="muted">没有命中的基金。</p>}
      </div>
    </div>
  );
}
