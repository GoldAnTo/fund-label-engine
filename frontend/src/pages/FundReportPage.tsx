import { useState } from "react";
import { useParams } from "react-router-dom";
import { downloadFile, fetchFundReport, postReview } from "../api";
import { useAsync, LabelStatusBadge, ReviewActionBadge } from "../components";

export default function FundReportPage() {
  const { runId = "", fundCode = "" } = useParams();
  const [version, setVersion] = useState(0);
  const { data, error, loading } = useAsync(
    () => fetchFundReport(runId, fundCode),
    [runId, fundCode, version]
  );

  const [activeLabel, setActiveLabel] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState("researcher");
  const [decision, setDecision] = useState("confirm");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const submit = async () => {
    if (!activeLabel) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await postReview(runId, fundCode, activeLabel, decision, reviewer, comment);
      setActiveLabel(null);
      setComment("");
      setVersion((v) => v + 1);
    } catch (e: unknown) {
      setSubmitError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>
            基金报告 <code>{fundCode}</code>{" "}
            {data && <ReviewActionBadge value={data.review_action} />}
          </h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() =>
                downloadFile(
                  `/v1/runs/${runId}/funds/${fundCode}/export?format=xlsx`,
                  `fund_${fundCode}.xlsx`
                )
              }
            >
              导出 XLSX
            </button>
            <button
              onClick={() =>
                downloadFile(
                  `/v1/runs/${runId}/funds/${fundCode}/export?format=csv`,
                  `fund_${fundCode}.zip`
                )
              }
            >
              导出 CSV (zip)
            </button>
          </div>
        </div>
        <p className="muted">Run: <code>{runId}</code></p>
        {loading && <p>加载中...</p>}
        {error && <div className="error">{error}</div>}
        {data && (
          <>
            <h3>汇总</h3>
            <dl className="kv">
              <dt>标签数</dt><dd>{data.summary.label_count}</dd>
              <dt>特征数</dt><dd>{data.summary.feature_count}</dd>
              <dt>因子暴露</dt><dd>{data.summary.factor_exposure_count ?? data.factor_exposures.length}</dd>
              <dt>证据条数</dt><dd>{data.summary.evidence_count}</dd>
              <dt>缺失字段数</dt><dd>{data.summary.missing_field_count}</dd>
              <dt>已有复核</dt><dd>{data.summary.review_count}</dd>
            </dl>
            {data.missing_fields.length > 0 && (
              <>
                <h3>缺失字段</h3>
                <p>{data.missing_fields.join("、")}</p>
              </>
            )}
          </>
        )}
      </div>

      {data && (
        <div className="card">
          <h2>标签与证据</h2>
          <table>
            <thead>
              <tr>
                <th>标签</th><th>分类</th><th>状态</th><th>置信</th><th>证据</th><th>复核</th>
              </tr>
            </thead>
            <tbody>
              {data.labels.map((label) => {
                const ev = data.evidence.filter((e) => e.label_code === label.label_code);
                return (
                  <tr key={label.label_code}>
                    <td>
                      <strong>{label.label_name}</strong>
                      <div className="muted"><code>{label.label_code}</code></div>
                    </td>
                    <td>{label.category}</td>
                    <td><LabelStatusBadge value={label.status} /></td>
                    <td>{(label.confidence * 100).toFixed(0)}%</td>
                    <td>
                      {ev.map((e, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>
                          <div style={{ fontSize: 13 }}>{e.message}</div>
                          <div className="muted">
                            {e.metric} = {e.value} (阈值 {e.threshold}, 来源 {e.source})
                          </div>
                        </div>
                      ))}
                    </td>
                    <td>
                      <button
                        className="secondary"
                        onClick={() => setActiveLabel(label.label_code)}
                      >
                        复核…
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {data && data.factor_exposures.length > 0 && (
        <div className="card">
          <h2>基金级因子暴露</h2>
          <p className="muted">基于持仓和股票因子预聚合，coverage 表示可用因子覆盖的持仓权重。</p>
          <table>
            <thead>
              <tr>
                <th>因子</th><th>暴露值</th><th>覆盖权重</th><th>持仓权重</th><th>股票覆盖</th><th>日期</th>
              </tr>
            </thead>
            <tbody>
              {data.factor_exposures.map((f) => (
                <tr key={`${f.report_date}-${f.factor_code}-${f.as_of_date}`}>
                  <td><code>{f.factor_code}</code></td>
                  <td>{Number(f.exposure_value).toFixed(4)}</td>
                  <td>{(Number(f.coverage_weight) * 100).toFixed(1)}%</td>
                  <td>{(Number(f.holding_total_weight) * 100).toFixed(1)}%</td>
                  <td>{f.covered_stock_count}/{f.stock_count}</td>
                  <td className="muted">{f.report_date} / {f.as_of_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.features.length > 0 && (
        <div className="card">
          <h2>特征值</h2>
          <table>
            <thead>
              <tr><th>特征</th><th>值</th><th>来源</th></tr>
            </thead>
            <tbody>
              {data.features.map((f) => (
                <tr key={f.feature_code}>
                  <td><code>{f.feature_code}</code></td>
                  <td>{f.value}</td>
                  <td className="muted">{f.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.reviews.length > 0 && (
        <div className="card">
          <h2>历史复核</h2>
          <table>
            <thead>
              <tr><th>标签</th><th>决定</th><th>复核人</th><th>备注</th></tr>
            </thead>
            <tbody>
              {data.reviews.map((r) => (
                <tr key={r.review_id}>
                  <td><code>{r.label_code}</code></td>
                  <td>{r.decision}</td>
                  <td>{r.reviewer}</td>
                  <td>{r.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeLabel && (
        <div className="card">
          <h2>提交复核</h2>
          <p className="muted">标签 <code>{activeLabel}</code></p>
          {submitError && <div className="error">{submitError}</div>}
          <div className="toolbar">
            <label>
              决定&nbsp;
              <select value={decision} onChange={(e) => setDecision(e.target.value)}>
                <option value="confirm">confirm</option>
                <option value="reject">reject</option>
                <option value="observe">observe</option>
              </select>
            </label>
            <label>
              复核人&nbsp;
              <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
            </label>
          </div>
          <textarea
            placeholder="备注"
            rows={3}
            style={{ width: "100%", marginBottom: 12 }}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <div className="toolbar">
            <button onClick={submit} disabled={submitting}>
              {submitting ? "提交中…" : "提交"}
            </button>
            <button className="secondary" onClick={() => setActiveLabel(null)}>
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
