import { Link, useParams } from "react-router-dom";
import {
  downloadFile,
  fetchLabelChanges,
  fetchRun,
  fetchRunStyle,
  fetchRunSummary,
} from "../api";
import { useAsync, runStatusLabel } from "../components";

const CATEGORY_LABELS: Record<string, string> = {
  data_quality: "数据质量",
  return_risk: "收益风险",
  holding: "持仓结构",
  holding_style: "持仓风格",
  relative_benchmark: "相对基准",
  manager: "基金经理",
  fee: "费率",
  fund_size: "规模",
  review: "复核",
  description: "描述性",
};

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const { data, error, loading } = useAsync(() => fetchRun(runId), [runId]);
  const { data: summary } = useAsync(() => fetchRunSummary(runId), [runId]);
  const { data: style } = useAsync(() => fetchRunStyle(runId), [runId]);
  const { data: labelChanges } = useAsync(
    () => fetchLabelChanges(runId),
    [runId]
  );

  return (
    <div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>批次详情</h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() =>
                downloadFile(`/v1/runs/${runId}/export?format=xlsx`, `run_${runId}.xlsx`)
              }
            >
              导出 XLSX
            </button>
            <button
              onClick={() =>
                downloadFile(`/v1/runs/${runId}/export?format=csv`, `run_${runId}.zip`)
              }
            >
              导出 CSV 压缩包
            </button>
          </div>
        </div>
        <p className="muted">批次编号：<code>{runId}</code></p>
        {loading && <p>加载中...</p>}
        {error && <div className="error">{error}</div>}
        {data && (
          <dl className="kv">
            <dt>开始时间</dt><dd>{data.run_at}</dd>
            <dt>规则版本</dt><dd>{data.rule_version}</dd>
            <dt>状态</dt><dd>{runStatusLabel(data.status)}</dd>
            <dt>处理基金数</dt><dd>{data.fund_codes.length}</dd>
            <dt>失败基金数</dt><dd>{data.failure_count ?? 0}</dd>
          </dl>
        )}
      </div>

      {summary && (
        <div className="card">
          <h2>批次摘要</h2>
          <dl className="kv">
            <dt>已处理</dt><dd>{summary.counts.processed}</dd>
            <dt>失败</dt><dd>{summary.counts.failed}</dd>
            <dt>数据不足</dt><dd>{summary.counts.data_insufficient}</dd>
            <dt>需人工复核</dt><dd>{summary.counts.manual_review}</dd>
            <dt>收益窗口不足</dt><dd>{summary.counts.return_window_insufficient}</dd>
          </dl>
          <h3>标签命中分布（前 10）</h3>
          <table>
            <thead>
              <tr><th>标签</th><th>分类</th><th>命中基金数</th></tr>
            </thead>
            <tbody>
              {summary.label_distribution.slice(0, 10).map((row) => (
                <tr key={row.label_code}>
                  <td>
                    <strong>{row.label_name}</strong>
                  </td>
                  <td>{CATEGORY_LABELS[row.category] ?? row.category}</td>
                  <td>{row.fund_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {style && (
        <div className="card">
          <h2>风格分布</h2>
          <p className="muted">
            基于股票因子聚合的高级风格标签命中情况；规则版本 =
            <code> {style.rule_version}</code>
          </p>
          <table>
            <thead>
              <tr><th>风格</th><th>命中基金数</th><th>示例基金</th></tr>
            </thead>
            <tbody>
              {Object.entries(style.styles).map(([code, info]) => (
                <tr key={code}>
                  <td><code>{code}</code></td>
                  <td>{info.count}</td>
                  <td className="muted">
                    {info.funds.slice(0, 5).join(", ")}
                    {info.funds.length > 5 ? ` … (+${info.funds.length - 5})` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            未出风格：缺少股票因子 <strong>{style.boundary_counts.stock_factors_missing}</strong>；
            因子存在但未达任何阈值 <strong>{style.boundary_counts.style_pending_rule_definition}</strong>。
          </p>
        </div>
      )}

      {labelChanges && labelChanges.summary.total > 0 && (
        <div className="card">
          <h2>
            标签变化
            {labelChanges.summary.risk_warnings > 0 && (
              <span
                className="badge badge-manual_review"
                style={{ marginLeft: 8 }}
                title="风险标签从非 active 变为 active"
              >
                ⚠ {labelChanges.summary.risk_warnings} 项风险预警
              </span>
            )}
          </h2>
          <p className="muted">
            相对上一次成功批次，本次共 <strong>{labelChanges.summary.total}</strong> 个标签发生变化：
            新增 <strong>{labelChanges.summary.by_type.added || 0}</strong>，
            消失 <strong>{labelChanges.summary.by_type.removed || 0}</strong>，
            状态变更 <strong>{labelChanges.summary.by_type.status_changed || 0}</strong>。
          </p>
          {labelChanges.changes.filter((c) => c.is_risk_warning).length > 0 && (
            <details open style={{ marginTop: 12 }}>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                风险预警详情（{labelChanges.changes.filter((c) => c.is_risk_warning).length}）
              </summary>
              <table>
                <thead>
                  <tr>
                    <th>基金代码</th>
                    <th>风险标签</th>
                    <th>状态变化</th>
                  </tr>
                </thead>
                <tbody>
                  {labelChanges.changes
                    .filter((c) => c.is_risk_warning)
                    .slice(0, 50)
                    .map((c, i) => (
                      <tr key={`${c.fund_code}-${c.label_code}-${i}`}>
                        <td>
                          <Link to={`/runs/${runId}/funds/${c.fund_code}`}>
                            <code>{c.fund_code}</code>
                          </Link>
                        </td>
                        <td><code>{c.label_code}</code></td>
                        <td>
                          <span className="muted">{c.previous_status || "无"}</span>
                          {" → "}
                          <strong>{c.current_status || "无"}</strong>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </details>
          )}
        </div>
      )}

      {data && data.failures && data.failures.length > 0 && (
        <div className="card">
          <h2>失败记录</h2>
          <p className="muted">下列基金在本次批次中计算失败，已被隔离，不影响其它基金的结果。</p>
          <table>
            <thead>
              <tr>
                <th>基金代码</th>
                <th>阶段</th>
                <th>错误类型</th>
                <th>消息</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {data.failures.map((f, i) => (
                <tr key={`${f.fund_code}-${i}`}>
                  <td><code>{f.fund_code}</code></td>
                  <td>{f.stage}</td>
                  <td>{f.error_type}</td>
                  <td className="muted">{f.message}</td>
                  <td>{f.recorded_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.rule_snapshot && (
        <div className="card">
          <h2>规则快照</h2>
          <p className="muted">本次批次使用的全部阈值参数（规则版本：{data.rule_version}）。</p>
          <table>
            <thead>
              <tr><th>参数</th><th>值</th></tr>
            </thead>
            <tbody>
              {Object.entries(data.rule_snapshot).map(([k, v]) => (
                <tr key={k}>
                  <td><code>{k}</code></td>
                  <td>{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <div className="card">
          <h2>基金列表</h2>
          <table>
            <thead>
              <tr><th>基金代码</th><th></th></tr>
            </thead>
            <tbody>
              {data.fund_codes.map((code) => (
                <tr key={code}>
                  <td><code>{code}</code></td>
                  <td>
                    <Link to={`/runs/${runId}/funds/${code}`}>查看报告 →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
