import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRuns, searchFunds, SearchResponse } from "../api";
import { ReviewActionBadge } from "../components";

export default function SearchPage() {
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState("");
  const [fundCode, setFundCode] = useState("");
  const [labelCode, setLabelCode] = useState("");
  const [reviewAction, setReviewAction] = useState("");
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

  const runSearch = async () => {
    if (!runId) return;
    setError(null);
    try {
      const res = await searchFunds(runId, {
        fund_code: fundCode || undefined,
        label_code: labelCode || undefined,
        review_action: reviewAction || undefined,
      });
      setData(res);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    if (runId) runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  return (
    <div className="card">
      <h2>基金检索</h2>
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
        <label>
          基金代码&nbsp;
          <input
            placeholder="模糊匹配"
            value={fundCode}
            onChange={(e) => setFundCode(e.target.value)}
          />
        </label>
        <label>
          标签&nbsp;
          <select value={labelCode} onChange={(e) => setLabelCode(e.target.value)}>
            <option value="">(全部)</option>
            {data?.available_labels.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </label>
        <label>
          复核动作&nbsp;
          <select
            value={reviewAction}
            onChange={(e) => setReviewAction(e.target.value)}
          >
            <option value="">(全部)</option>
            <option value="observe">observe</option>
            <option value="manual_review">manual_review</option>
          </select>
        </label>
        <button onClick={runSearch}>检索</button>
      </div>
      {error && <div className="error">{error}</div>}
      {data && (
        <table>
          <thead>
            <tr>
              <th>基金代码</th>
              <th>标签数</th>
              <th>复核动作</th>
              <th>缺失字段</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((r) => (
              <tr key={r.fund_code}>
                <td><code>{r.fund_code}</code></td>
                <td>{r.label_count}</td>
                <td><ReviewActionBadge value={r.review_action} /></td>
                <td>{r.missing_field_count}</td>
                <td>
                  <Link to={`/runs/${data.run_id}/funds/${r.fund_code}`}>
                    报告 →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {data && data.results.length === 0 && <p className="muted">没有命中的基金。</p>}
    </div>
  );
}
