import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRelativeEligibility, fetchRuns, RelativeEligibilityResponse } from "../api";

const STATUS_LABELS: Record<string, string> = {
  relative_label_ready: "可展示",
  relative_label_ready_approx: "可展示（近似基准）",
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
    .replaceAll("relative_label_ready_approx", "可展示（近似基准）")
    .replaceAll("relative_label_ready", "可展示")
    .replaceAll("benchmark_source_missing", "缺少基准收益源")
    .replaceAll("benchmark_mapping_required", "需要确认基准映射")
    .replaceAll("benchmark_unresolved", "基准组件未解析")
    .replaceAll("benchmark_missing", "未配置业绩基准")
    .replaceAll("nav_window_insufficient", "收益窗口不足")
    .replace(/\b[A-Z0-9_]+:/g, "");
}

function statusClass(value: string) {
  return value === "relative_label_ready" || value === "relative_label_ready_approx"
    ? "badge-observe"
    : "badge-manual_review";
}

function actionText(statusValue: string, component: string) {
  if (statusValue === "benchmark_source_missing") return `补齐 ${displayText(component)} 的基准日收益源`;
  if (statusValue === "benchmark_mapping_required") return `确认 ${displayText(component)} 的精确指数映射`;
  if (statusValue === "benchmark_unresolved") return `补解析规则或明确不支持 ${displayText(component)}`;
  if (statusValue === "benchmark_missing") return "补充基金业绩基准配置";
  if (statusValue === "nav_window_insufficient") return "补齐净值窗口后再展示相对基准标签";
  return "保持观察";
}

function csvEscape(value: string | number) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadCsv(fileName: string, rows: (string | number)[][]) {
  const csv = rows.map((row) => row.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
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

  const currentRun = runs.find((run) => run.run_id === runId);
  const blockedRows = useMemo(
    () => data?.results.filter((row) => row.relative_label_status !== "relative_label_ready") ?? [],
    [data]
  );

  const handleExportBlocked = () => {
    if (!data) return;
    downloadCsv(`ready_pool_blocked_${data.run_id.slice(0, 12)}.csv`, [
      ["基金代码", "基金名称", "暂不可展示原因", "基准源状态", "净值样本", "基准样本", "阻塞组件", "建议动作"],
      ...blockedRows.map((row) => [
        row.fund_code,
        row.fund_name,
        statusLabel(row.relative_label_status),
        sourceStatusLabel(row.benchmark_source_status),
        row.nav_sample_count,
        row.benchmark_sample_count,
        displayText(row.blocking_components || row.blocking_reason || "-"),
        actionText(row.relative_label_status, row.blocking_components || row.blocking_reason || ""),
      ]),
    ]);
  };

  return (
    <div>
      <div className="card workbench-hero">
        <div>
          <h2>Phase1 v1 可展示池工作台</h2>
          <p className="muted">
            默认服务正式清单，先判断哪些基金能展示相对基准标签，再把暂不可展示原因转成数据和映射任务。
          </p>
          {currentRun && <p className="muted">最新批次时间：{currentRun.run_at}</p>}
          <button className="secondary" onClick={handleExportBlocked} disabled={!data || blockedRows.length === 0}>
            导出暂不可展示清单
          </button>
        </div>
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
          {data.ready_approx_count ? (
            <div className="metric-tile metric-ready">
              <span>可展示（近似基准）</span>
              <strong>{data.ready_approx_count}</strong>
            </div>
          ) : null}
          <div className="metric-tile metric-blocked">
            <span>暂不可展示</span>
            <strong>{data.blocked_count}</strong>
          </div>
        </div>
      )}

      {data && (
        <div className="card">
          <h2>暂不可展示结构</h2>
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
                <th>建议动作</th>
              </tr>
            </thead>
            <tbody>
              {data.blocker_groups.slice(0, 12).map((group) => (
                <tr key={group.key}>
                  <td><span className={`badge ${statusClass(group.status)}`}>{statusLabel(group.status)}</span></td>
                  <td className="muted">{displayText(group.component)}</td>
                  <td>{group.count}</td>
                  <td className="muted">{group.sample_fund_codes.join(", ")}</td>
                  <td>{actionText(group.status, group.component)}</td>
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
                <th>建议动作</th>
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
                  <td>
                    {row.relative_label_status === "relative_label_ready"
                      ? "保持展示，查看证据"
                      : actionText(row.relative_label_status, row.blocking_components || row.blocking_reason || "")}
                    {row.relative_label_status !== "relative_label_ready" && (
                      <div className="muted">{displayText(row.blocking_components || row.blocking_reason || "-")}</div>
                    )}
                  </td>
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
