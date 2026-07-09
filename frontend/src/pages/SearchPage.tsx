import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchRuns, searchFunds, fetchPortfolioMatrix, type SearchResponse, type PortfolioMatrixResponse } from "../api";
import { ReviewActionBadge } from "../components";
import { STYLE_GROUPS, ALL_STYLE_CODES, styleTagClass, styleName } from "../styleConfig";

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [runs, setRuns] = useState<{ run_id: string; run_at: string }[]>([]);
  const [runId, setRunId] = useState(searchParams.get("run_id") || "");
  const [fundCode, setFundCode] = useState(searchParams.get("fund_code") || "");
  const [labelCode, setLabelCode] = useState(searchParams.get("label_code") || "");
  const [groupCode, setGroupCode] = useState(searchParams.get("group_code") || "");
  const [groupType, setGroupType] = useState(searchParams.get("group_type") || "");
  const [classificationCode, setClassificationCode] = useState(searchParams.get("classification_code") || "");
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

  // 把当前筛选条件同步到 URL
  useEffect(() => {
    const next = new URLSearchParams();
    if (runId) next.set("run_id", runId);
    if (fundCode) next.set("fund_code", fundCode);
    if (labelCode) next.set("label_code", labelCode);
    if (groupCode) next.set("group_code", groupCode);
    if (groupType) next.set("group_type", groupType);
    if (classificationCode) next.set("classification_code", classificationCode);
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, fundCode, labelCode, groupCode, groupType, classificationCode]);

  const runSearch = async () => {
    if (!runId) return;
    setError(null);
    try {
      const res = await searchFunds(runId, {
        fund_code: fundCode || undefined,
        label_code: labelCode || undefined,
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
  }, [runId, labelCode, groupCode, groupType, classificationCode]);

  const clearGroup = () => {
    setGroupCode("");
    setGroupType("");
  };
  const clearClassification = () => {
    setClassificationCode("");
  };

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
      <div className="page-head-v2">
        <div>
          <span className="eyebrow">RESEARCH · 风格筛选</span>
          <h1>风格筛选</h1>
          <p>按风格标签筛选基金，横向对比同类基金</p>
        </div>
        <div className="flow-steps" style={{ alignSelf: "flex-start" }}>
          <span className="flow-step is-done">
            <span className="step-num">1</span>总览
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step is-current">
            <span className="step-num">2</span>筛选
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step">诊断</span>
        </div>
      </div>
      <div className="context-bar">
        <div className="chip chip-mono">
          <span className="label">批次</span>
          <span className="value">{runId ? runId.slice(0, 12) + "…" : "—"}</span>
        </div>
        {labelCode && (
          <div className="chip">
            <span className="label">风格</span>
            <span className="value">{styleName(labelCode)}</span>
            <button className="chip-close" onClick={() => setLabelCode("")} title="清除风格筛选">×</button>
          </div>
        )}
        {groupCode && (
          <div className="chip">
            <span className="label">分组</span>
            <span className="value">
              {groupType ? `${groupType} · ` : ""}{groupCode}
            </span>
            <button className="chip-close" onClick={clearGroup} title="清除分组筛选">×</button>
          </div>
        )}
        {classificationCode && (
          <div className="chip">
            <span className="label">分类</span>
            <span className="value">{classificationCode}</span>
            <button className="chip-close" onClick={clearClassification} title="清除分类筛选">×</button>
          </div>
        )}
        {fundCode && (
          <div className="chip">
            <span className="label">基金</span>
            <span className="value">{fundCode}</span>
          </div>
        )}
        <div className="spacer" />
        {data && (
          <span className="meta" style={{ fontSize: 12, color: "var(--text-3)" }}>
            匹配 <strong>{data.results.length}</strong> 只
          </span>
        )}
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
                              <button
                                key={code}
                                type="button"
                                className={`${styleTagClass(code)} style-tag-clickable`}
                                onClick={() => setLabelCode(code)}
                                title={`按「${styleName(code)}」筛选`}
                              >
                                {styleName(code)}
                              </button>
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
