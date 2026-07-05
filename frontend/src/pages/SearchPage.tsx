import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchRuns, searchFunds, fetchPortfolioMatrix, type SearchResponse, type PortfolioMatrixResponse } from "../api";
import { ReviewActionBadge } from "../components";
import { STYLE_GROUPS, ALL_STYLE_CODES, styleTagClass, styleName } from "../styleConfig";

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState(searchParams.get("run_id") || "");
  const [fundCode, setFundCode] = useState(searchParams.get("fund_code") || "");
  const [labelCode, setLabelCode] = useState(searchParams.get("label_code") || "");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [matrix, setMatrix] = useState<PortfolioMatrixResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns()
      .then((rs) => {
        setRuns(rs);
        if (rs.length > 0 && !runId) setRunId(rs[0].run_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (runId) fetchPortfolioMatrix(runId).then(setMatrix).catch(() => {});
  }, [runId]);

  const runSearch = async () => {
    if (!runId) return;
    setError(null);
    try {
      const res = await searchFunds(runId, {
        fund_code: fundCode || undefined,
        label_code: labelCode || undefined,
      });
      setData(res);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    if (runId) runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, labelCode]);

  const fundStyleMap = useMemo(() => {
    const m = new Map<string, string[]>();
    if (matrix) {
      for (const row of matrix.rows) {
        m.set(row.fund_code, (row.style_tags || []).filter((t) => ALL_STYLE_CODES.has(t) && t !== "style_pending_rule_definition"));
      }
    }
    return m;
  }, [matrix]);

  // 当前选中的风格组
  const activeGroup = STYLE_GROUPS.find((g) => g.codes.includes(labelCode));

  return (
    <div>
      <div className="page-head">
        <h1>风格筛选</h1>
        <p>按风格标签筛选基金，横向对比同类基金</p>
      </div>

      {/* 风格快捷筛选 */}
      <div className="card">
        <h2>风格快捷筛选</h2>
        {STYLE_GROUPS.map((group) => (
          <div className="style-group-bar" key={group.title}>
            <span className="style-group-label">{group.title}</span>
            {group.codes.map((code) => (
              <button
                key={code}
                className={`style-filter-btn ${labelCode === code ? "active" : ""}`}
                onClick={() => setLabelCode(labelCode === code ? "" : code)}
              >
                {styleName(code)}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* 搜索栏 */}
      <div className="toolbar">
        <label>
          批次
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id.slice(0, 8)}… ({r.run_at})
              </option>
            ))}
          </select>
        </label>
        <label>
          基金代码
          <input placeholder="模糊匹配" value={fundCode} onChange={(e) => setFundCode(e.target.value)} />
        </label>
        <button onClick={runSearch}>筛选</button>
        {labelCode && (
          <button className="secondary" onClick={() => setLabelCode("")}>清除标签</button>
        )}
      </div>

      {error && <div className="alert alert-warn">{error}</div>}

      {/* 结果 */}
      {data && (
        <div className="card">
          <h2>
            筛选结果
            {labelCode && <span className="muted"> — {styleName(labelCode)}</span>}
            {activeGroup && <span className="muted"> ({activeGroup.title}维度)</span>}
          </h2>
          <p className="muted">{data.results.length} 只基金</p>
          {data.results.length > 0 && (
            <table className="fund-table">
              <thead>
                <tr><th>基金</th><th>风格标签</th><th>复核</th><th></th></tr>
              </thead>
              <tbody>
                {data.results.map((r) => {
                  const tags = fundStyleMap.get(r.fund_code) || [];
                  return (
                    <tr key={r.fund_code}>
                      <td>
                        <div className="fund-code-cell">{r.fund_code}</div>
                      </td>
                      <td>
                        {tags.length > 0 ? (
                          <div className="style-labels-grid">
                            {tags.map((code) => (
                              <span key={code} className={styleTagClass(code)}>{styleName(code)}</span>
                            ))}
                          </div>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td><ReviewActionBadge value={r.review_action} /></td>
                      <td>
                        <Link to={`/runs/${data.run_id}/funds/${r.fund_code}`}>查看报告</Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {data.results.length === 0 && <p className="muted">没有命中的基金。</p>}
        </div>
      )}
    </div>
  );
}
