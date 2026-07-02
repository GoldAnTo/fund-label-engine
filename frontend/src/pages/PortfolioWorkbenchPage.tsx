import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchPortfolioDraft,
  fetchPortfolioMatrix,
  fetchPortfolioRoleReviews,
  fetchRuns,
  postPortfolioRoleReview,
  type PortfolioDraftResponse,
  type PortfolioMatrixResponse,
  type PortfolioRoleReview,
} from "../api";

const STATUS_LABELS: Record<string, string> = {
  eligible: "可进入草案",
  observe: "观察池",
  review_required: "需复核",
  excluded: "已排除",
};

const BUCKET_LABELS: Record<string, string> = {
  core: "核心",
  satellite: "卫星",
  index_tool: "指数工具",
};

const REVIEW_DECISIONS = [
  { value: "core", label: "核心" },
  { value: "satellite", label: "卫星" },
  { value: "index_tool", label: "指数工具" },
  { value: "exclude", label: "排除" },
];

function statusLabel(value: string) {
  return STATUS_LABELS[value] ?? value;
}

function bucketLabel(value: string) {
  return BUCKET_LABELS[value] ?? value;
}

function joinTags(values: string[] | undefined) {
  return values && values.length > 0 ? values.join(", ") : "-";
}

function statusClass(status: string) {
  if (status === "eligible") return "badge-observe";
  if (status === "review_required") return "badge-manual_review";
  if (status === "excluded") return "badge-default";
  return "badge-active";
}

function reviewMap(reviews: PortfolioRoleReview[]) {
  return new Map(reviews.map((review) => [review.fund_code, review]));
}

export default function PortfolioWorkbenchPage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [matrix, setMatrix] = useState<PortfolioMatrixResponse | null>(null);
  const [draft, setDraft] = useState<PortfolioDraftResponse | null>(null);
  const [reviews, setReviews] = useState<PortfolioRoleReview[]>([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [bucketFilter, setBucketFilter] = useState("all");
  const [reviewer, setReviewer] = useState("researcher-a");
  const [savingFund, setSavingFund] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchRuns()
      .then((payload) => {
        setRuns(payload);
        if (payload.length > 0) setRunId(payload[0].run_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchPortfolioMatrix(runId),
      fetchPortfolioDraft(runId),
      fetchPortfolioRoleReviews(runId),
    ])
      .then(([matrixPayload, draftPayload, reviewPayload]) => {
        setMatrix(matrixPayload);
        setDraft(draftPayload);
        setReviews(reviewPayload);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  const draftByFund = useMemo(() => {
    const map = new Map<string, PortfolioDraftResponse["rows"][number]>();
    draft?.rows.forEach((row) => map.set(row.fund_code, row));
    return map;
  }, [draft]);

  const reviewsByFund = useMemo(() => reviewMap(reviews), [reviews]);

  const statusCounts = useMemo(() => {
    const counts = new Map<string, number>();
    matrix?.rows.forEach((row) => counts.set(row.allocation_status, (counts.get(row.allocation_status) ?? 0) + 1));
    return counts;
  }, [matrix]);

  const bucketCounts = useMemo(() => {
    const counts = new Map<string, number>();
    draft?.rows.forEach((row) => counts.set(row.bucket, (counts.get(row.bucket) ?? 0) + 1));
    return counts;
  }, [draft]);

  const filteredRows = useMemo(() => {
    const rows = matrix?.rows ?? [];
    return rows.filter((row) => {
      if (statusFilter !== "all" && row.allocation_status !== statusFilter) return false;
      const draftRow = draftByFund.get(row.fund_code);
      if (bucketFilter !== "all" && draftRow?.bucket !== bucketFilter) return false;
      return true;
    });
  }, [bucketFilter, draftByFund, matrix, statusFilter]);

  const saveReview = async (fundCode: string, decision: string) => {
    if (!runId) return;
    setSavingFund(fundCode);
    setError(null);
    try {
      const saved = await postPortfolioRoleReview(runId, {
        fund_code: fundCode,
        decision,
        reviewer,
        comment: "portfolio workbench calibration",
      });
      setReviews((current) => {
        const rest = current.filter((item) => item.fund_code !== fundCode);
        return [saved, ...rest];
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingFund(null);
    }
  };

  const totalDraftWeight = draft?.rows.reduce((sum, row) => sum + row.draft_weight_pct, 0) ?? 0;

  return (
    <div className="portfolio-workbench">
      <section className="card workbench-hero portfolio-hero">
        <div>
          <p className="eyebrow">Core Satellite Portfolio</p>
          <h2>组合工作台</h2>
          <p className="muted">
            把 eligible、观察池、人工角色复核和 dry-run 权重放在同一页，先校准判断，再进入组合草案。
          </p>
          {draft && (
            <p className="muted">
              目标：{draft.objective}，配置版本：{draft.config_version}
            </p>
          )}
        </div>
        <div className="toolbar portfolio-toolbar">
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
            复核人&nbsp;
            <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          </label>
        </div>
      </section>

      {error && <div className="error">{error}</div>}
      {loading && <p>加载中...</p>}

      {matrix && draft && (
        <div className="metric-grid portfolio-metrics">
          <div className="metric-tile"><span>基金总数</span><strong>{matrix.total_count}</strong></div>
          <div className="metric-tile metric-ready"><span>进入草案</span><strong>{draft.rows.length}</strong></div>
          <div className="metric-tile"><span>dry-run 权重</span><strong>{totalDraftWeight.toFixed(1)}%</strong></div>
          <div className="metric-tile metric-blocked"><span>排除</span><strong>{draft.excluded.length}</strong></div>
        </div>
      )}

      {matrix && draft && (
        <section className="portfolio-grid">
          <div className="card portfolio-panel">
            <h2>校准队列</h2>
            <p className="muted">按组合可用性分层，优先看 eligible 和 observe 中高价值基金。</p>
            <div className="portfolio-filter-row">
              <label>
                状态&nbsp;
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="all">全部</option>
                  {[...statusCounts.keys()].map((status) => (
                    <option key={status} value={status}>{statusLabel(status)}</option>
                  ))}
                </select>
              </label>
              <label>
                角色桶&nbsp;
                <select value={bucketFilter} onChange={(e) => setBucketFilter(e.target.value)}>
                  <option value="all">全部</option>
                  {[...bucketCounts.keys()].map((bucket) => (
                    <option key={bucket} value={bucket}>{bucketLabel(bucket)}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="portfolio-status-strip">
              {[...statusCounts.entries()].map(([status, count]) => (
                <span key={status} className={`badge ${statusClass(status)}`}>
                  {statusLabel(status)} {count}
                </span>
              ))}
            </div>
          </div>

          <div className="card portfolio-panel">
            <h2>草案权重</h2>
            <p className="muted">权重是 dry-run 输出，用于检查约束和角色分布，不代表最终投资建议。</p>
            <div className="draft-buckets">
              {[...bucketCounts.entries()].map(([bucket, count]) => {
                const weight = draft.rows
                  .filter((row) => row.bucket === bucket)
                  .reduce((sum, row) => sum + row.draft_weight_pct, 0);
                return (
                  <div key={bucket} className="draft-bucket">
                    <span>{bucketLabel(bucket)}</span>
                    <strong>{weight.toFixed(1)}%</strong>
                    <small>{count} 只</small>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {matrix && (
        <section className="card portfolio-table-card">
          <h2>基金角色复核</h2>
          <table className="portfolio-table">
            <thead>
              <tr>
                <th>基金</th>
                <th>状态</th>
                <th>草案</th>
                <th>角色 / 标签</th>
                <th>风险和阻塞</th>
                <th>人工判断</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => {
                const draftRow = draftByFund.get(row.fund_code);
                const review = reviewsByFund.get(row.fund_code);
                return (
                  <tr key={row.fund_code}>
                    <td>
                      <code>{row.fund_code}</code>
                      <div><Link to={`/runs/${runId}/funds/${row.fund_code}`}>查看报告 →</Link></div>
                    </td>
                    <td><span className={`badge ${statusClass(row.allocation_status)}`}>{statusLabel(row.allocation_status)}</span></td>
                    <td>
                      {draftRow ? (
                        <>
                          <strong>{draftRow.draft_weight_pct.toFixed(2)}%</strong>
                          <div className="muted">{bucketLabel(draftRow.bucket)}，上限 {draftRow.max_weight_pct.toFixed(1)}%</div>
                        </>
                      ) : (
                        <span className="muted">未进入草案</span>
                      )}
                    </td>
                    <td>
                      <div>{joinTags(row.portfolio_roles)}</div>
                      <div className="muted">风格：{joinTags(row.style_tags)}</div>
                      <div className="muted">收益：{joinTags(row.return_tags)}</div>
                    </td>
                    <td>
                      <div>{joinTags(row.risk_tags)}</div>
                      {(row.blocking_reasons.length > 0 || row.watch_reasons.length > 0) && (
                        <div className="muted">{joinTags([...row.blocking_reasons, ...row.watch_reasons])}</div>
                      )}
                    </td>
                    <td>
                      <div className="review-controls">
                        <select
                          value={review?.decision ?? ""}
                          onChange={(e) => saveReview(row.fund_code, e.target.value)}
                          disabled={savingFund === row.fund_code || !reviewer.trim()}
                        >
                          <option value="">待确认</option>
                          {REVIEW_DECISIONS.map((decision) => (
                            <option key={decision.value} value={decision.value}>{decision.label}</option>
                          ))}
                        </select>
                        {review && <span className="muted">{review.reviewer}</span>}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filteredRows.length === 0 && <p className="muted">没有命中的基金。</p>}
        </section>
      )}
    </div>
  );
}
