import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchRuns, searchFunds, SearchResponse } from "../api";
import { ReviewActionBadge } from "../components";

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState(searchParams.get("run_id") || "");
  const [fundCode, setFundCode] = useState(searchParams.get("fund_code") || "");
  const [labelCode, setLabelCode] = useState(searchParams.get("label_code") || "");
  const [reviewAction, setReviewAction] = useState(searchParams.get("review_action") || "");
  const [groupCode, setGroupCode] = useState(searchParams.get("group_code") || "");
  const [groupType, setGroupType] = useState(searchParams.get("group_type") || "");
  const [classificationCode, setClassificationCode] = useState(searchParams.get("classification_code") || "");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns()
      .then((rs) => {
        setRuns(rs);
        if (rs.length > 0 && !runId) setRunId(rs[0].run_id);
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
        group_code: groupCode || undefined,
        group_type: groupType || undefined,
        classification_code: classificationCode || undefined,
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
            <option value="observe">观察</option>
            <option value="manual_review">需复核</option>
          </select>
        </label>
        <label>
          业务池&nbsp;
          <select value={groupCode} onChange={(e) => setGroupCode(e.target.value)}>
            <option value="">(全部)</option>
            {data?.available_groups.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </label>
        <label>
          分组类型&nbsp;
          <select value={groupType} onChange={(e) => setGroupType(e.target.value)}>
            <option value="">(全部)</option>
            {data?.available_group_types.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </label>
        <label>
          分类&nbsp;
          <select
            value={classificationCode}
            onChange={(e) => setClassificationCode(e.target.value)}
          >
            <option value="">(全部)</option>
            {data?.available_classifications.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
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
                    查看报告 →
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
