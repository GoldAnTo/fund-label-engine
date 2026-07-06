import { useEffect, useState } from "react";
import { fetchRunDiff, fetchRuns, Run, RunDiff } from "../api";

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

type Tab = "by_label" | "by_fund";

export default function RunDiffPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [base, setBase] = useState("");
  const [target, setTarget] = useState("");
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("by_label");

  useEffect(() => {
    fetchRuns()
      .then((rs) => {
        setRuns(rs);
        if (rs.length >= 2) {
          setBase(rs[1].run_id);
          setTarget(rs[0].run_id);
        } else if (rs.length === 1) {
          setBase(rs[0].run_id);
          setTarget(rs[0].run_id);
        }
      })
      .catch((e) => setError(e.message));
  }, []);

  const runDiff = async () => {
    if (!base || !target) return;
    setLoading(true);
    setError(null);
    try {
      setDiff(await fetchRunDiff(base, target));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-head-v2">
        <div>
          <span className="eyebrow">OPS · 批次对比</span>
          <h1>批次对比</h1>
          <p>
            选两个批次，输出标签集合差异。仅以两批共有的基金为统计对象；只在
            某一边出现的基金会进入单边基金名单，避免被误判为"标签变动"。
          </p>
        </div>
        <div className="flow-steps" style={{ alignSelf: "flex-start" }}>
          <span className="flow-step is-done">
            <span className="step-num">✓</span>两批次
          </span>
          <span className="flow-arrow">→</span>
          <span className="flow-step is-current">差异分析</span>
        </div>
      </div>
      <div className="card">
        <div className="section-head">
          <h2>选择对比基准</h2>
          <div className="meta">base 是旧批次，target 是新批次</div>
        </div>
        <div className="toolbar">
          <label>
            base（旧）&nbsp;
            <select value={base} onChange={(e) => setBase(e.target.value)}>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id.slice(0, 8)}… ({r.run_at})
                </option>
              ))}
            </select>
          </label>
          <label>
            target（新）&nbsp;
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id.slice(0, 8)}… ({r.run_at})
                </option>
              ))}
            </select>
          </label>
          <button onClick={runDiff} disabled={!base || !target || loading}>
            {loading ? "对比中…" : "开始对比"}
          </button>
        </div>
        {error && <div className="alert alert-warn">{error}</div>}
      </div>

      {diff && (
        <>
          <div className="card">
            <h2>总览</h2>
            <dl className="kv">
              <dt>基准批次基金数</dt><dd>{diff.totals.base_fund_count}</dd>
              <dt>对比批次基金数</dt><dd>{diff.totals.target_fund_count}</dd>
              <dt>共同基金数</dt><dd>{diff.totals.common_fund_count}</dd>
              <dt>新增标签基金组合</dt><dd>{diff.totals.added_pair_count}</dd>
              <dt>消失标签基金组合</dt><dd>{diff.totals.removed_pair_count}</dd>
              <dt>有变动的基金数</dt><dd>{diff.totals.changed_fund_count}</dd>
              <dt>仅基准批次有</dt><dd>{diff.totals.only_in_base_count}</dd>
              <dt>仅对比批次有</dt><dd>{diff.totals.only_in_target_count}</dd>
            </dl>
          </div>

          <div className="card">
            <div className="toolbar">
              <button
                onClick={() => setTab("by_label")}
                disabled={tab === "by_label"}
              >
                按标签
              </button>
              <button
                onClick={() => setTab("by_fund")}
                disabled={tab === "by_fund"}
              >
                按基金
              </button>
            </div>
            {tab === "by_label" && (
              <table>
                <thead>
                  <tr>
                    <th>标签</th>
                    <th>分类</th>
                    <th>+</th>
                    <th>−</th>
                    <th>净增</th>
                    <th>示例新增基金</th>
                    <th>示例消失基金</th>
                  </tr>
                </thead>
                <tbody>
                  {diff.summary_by_label.map((r) => (
                    <tr key={r.label_code}>
                      <td>
                        <strong>{r.label_name}</strong>
                      </td>
                      <td>{CATEGORY_LABELS[r.category] ?? r.category}</td>
                      <td>{r.added_funds.length}</td>
                      <td>{r.removed_funds.length}</td>
                      <td>{r.delta}</td>
                      <td className="muted">{r.added_funds.slice(0, 3).join(", ")}</td>
                      <td className="muted">{r.removed_funds.slice(0, 3).join(", ")}</td>
                    </tr>
                  ))}
                  {diff.summary_by_label.length === 0 && (
                    <tr><td colSpan={7} className="muted">两个批次没有标签变动。</td></tr>
                  )}
                </tbody>
              </table>
            )}
            {tab === "by_fund" && (
              <table>
                <thead>
                  <tr>
                    <th>基金</th>
                    <th>新增标签</th>
                    <th>消失标签</th>
                  </tr>
                </thead>
                <tbody>
                  {diff.details_by_fund.map((r) => (
                    <tr key={r.fund_code}>
                      <td><code>{r.fund_code}</code></td>
                      <td className="muted">{r.added_labels.join(", ") || "—"}</td>
                      <td className="muted">{r.removed_labels.join(", ") || "—"}</td>
                    </tr>
                  ))}
                  {diff.details_by_fund.length === 0 && (
                    <tr><td colSpan={3} className="muted">两个批次没有基金级变动。</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </div>

          {(diff.only_in_base.length > 0 || diff.only_in_target.length > 0) && (
            <div className="card">
              <h2>仅在单边出现的基金</h2>
              <h3>仅基准批次有（{diff.only_in_base.length}）</h3>
              <p className="muted">{diff.only_in_base.join(", ") || "—"}</p>
              <h3>仅对比批次有（{diff.only_in_target.length}）</h3>
              <p className="muted">{diff.only_in_target.join(", ") || "—"}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
