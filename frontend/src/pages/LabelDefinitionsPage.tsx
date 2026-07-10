import { useEffect, useMemo, useState } from "react";
import {
  fetchLabelDefinitions,
  fetchRuleVersions,
  setLabelEnabled,
  bulkSetLabelEnabled,
  fetchLabelEnableChanges,
  type LabelDefinition,
  type RuleVersionInfo,
  type LabelEnableChange,
} from "../api";

export default function LabelDefinitionsPage() {
  const [ruleVersions, setRuleVersions] = useState<RuleVersionInfo[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<string>("");
  const [definitions, setDefinitions] = useState<LabelDefinition[]>([]);
  const [changes, setChanges] = useState<LabelEnableChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [operator, setOperator] = useState("manual-ui");
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());
  const [pendingReason, setPendingReason] = useState("");
  const [filter, setFilter] = useState("");
  const [showOnlyDisabled, setShowOnlyDisabled] = useState(false);

  useEffect(() => {
    fetchRuleVersions()
      .then((v) => {
        const list = v;
        setRuleVersions(list);
        if (list.length > 0) setSelectedVersion(list[0].rule_version);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selectedVersion) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchLabelDefinitions(selectedVersion),
      fetchLabelEnableChanges(selectedVersion, 30),
    ])
      .then(([defs, ch]) => {
        setDefinitions(defs);
        setChanges(ch.changes);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedVersion]);

  const filteredDefs = useMemo(() => {
    let result = definitions;
    if (showOnlyDisabled) {
      result = result.filter((d) => !d.enabled);
    }
    if (filter.trim()) {
      const kw = filter.trim().toLowerCase();
      result = result.filter(
        (d) =>
          d.label_code.toLowerCase().includes(kw) ||
          d.label_name.toLowerCase().includes(kw) ||
          d.category.toLowerCase().includes(kw)
      );
    }
    return result;
  }, [definitions, filter, showOnlyDisabled]);

  const stats = useMemo(() => {
    const total = definitions.length;
    const enabled = definitions.filter((d) => d.enabled).length;
    return { total, enabled, disabled: total - enabled };
  }, [definitions]);

  const toggleSelection = (code: string) => {
    setSelectedCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedCodes.size === filteredDefs.length) {
      setSelectedCodes(new Set());
    } else {
      setSelectedCodes(new Set(filteredDefs.map((d) => d.label_code)));
    }
  };

  const toggleOne = async (def: LabelDefinition) => {
    setError(null);
    try {
      const result = await setLabelEnabled(
        def.label_code,
        selectedVersion,
        !def.enabled,
        operator,
        pendingReason || undefined
      );
      // 乐观更新
      setDefinitions((prev) =>
        prev.map((d) =>
          d.label_code === def.label_code
            ? { ...d, enabled: result.new_enabled ? 1 : 0 }
            : d
        )
      );
      // 重新拉变更日志
      const ch = await fetchLabelEnableChanges(selectedVersion, 30);
      setChanges(ch.changes);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const bulkToggle = async (enabled: boolean) => {
    if (selectedCodes.size === 0) return;
    setError(null);
    try {
      await bulkSetLabelEnabled(
        selectedVersion,
        Array.from(selectedCodes),
        enabled,
        operator,
        pendingReason || undefined
      );
      setDefinitions((prev) =>
        prev.map((d) =>
          selectedCodes.has(d.label_code) ? { ...d, enabled: enabled ? 1 : 0 } : d
        )
      );
      const ch = await fetchLabelEnableChanges(selectedVersion, 30);
      setChanges(ch.changes);
      setSelectedCodes(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>规则定义管理</h1>
          <p className="page-sub">
            启停 label 定义、批量操作、审计回溯。新增版本号或修改阈值后请用下方"规则回放"功能批量验证。
          </p>
        </div>
      </header>

      {/* 顶部控制 + 统计 */}
      <div className="card">
        <div className="rule-toolbar">
          <label className="field">
            <span>规则版本</span>
            <select
              value={selectedVersion}
              onChange={(e) => setSelectedVersion(e.target.value)}
            >
              {ruleVersions.length === 0 && <option value="">加载中…</option>}
              {ruleVersions.map((v) => (
                <option key={v.rule_version} value={v.rule_version}>
                  {v.rule_version}（{v.run_count} 次 run，最近 {v.last_run_at?.slice(0, 10) ?? "—"}）
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>操作人</span>
            <input
              type="text"
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              placeholder="姓名 / 工号"
            />
          </label>
          <label className="field field-grow">
            <span>变更原因（可选）</span>
            <input
              type="text"
              value={pendingReason}
              onChange={(e) => setPendingReason(e.target.value)}
              placeholder="例如：影响 ready pool / 配合回测 / 临时调整"
            />
          </label>
        </div>
        <div className="rule-stats">
          <div className="rule-stat">
            <span className="rule-stat-num">{stats.total}</span>
            <span className="rule-stat-label">规则总数</span>
          </div>
          <div className="rule-stat rule-stat-pos">
            <span className="rule-stat-num">{stats.enabled}</span>
            <span className="rule-stat-label">启用</span>
          </div>
          <div className="rule-stat rule-stat-neg">
            <span className="rule-stat-num">{stats.disabled}</span>
            <span className="rule-stat-label">禁用</span>
          </div>
          <div className="rule-stat">
            <span className="rule-stat-num">{selectedCodes.size}</span>
            <span className="rule-stat-label">已选择</span>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-bad">{error}</div>}

      {/* 批量操作 */}
      {selectedCodes.size > 0 && (
        <div className="card rule-bulk-bar">
          <div>
            已选 <strong>{selectedCodes.size}</strong> 条 —
          </div>
          <button className="btn btn-pos" onClick={() => bulkToggle(true)}>
            批量启用
          </button>
          <button className="btn btn-neg" onClick={() => bulkToggle(false)}>
            批量禁用
          </button>
          <button className="link-btn" onClick={() => setSelectedCodes(new Set())}>
            清空选择
          </button>
        </div>
      )}

      {/* 规则列表 */}
      <div className="card">
        <div className="rule-table-head">
          <h2>规则列表</h2>
          <div className="rule-filters">
            <input
              type="search"
              placeholder="搜索 label_code / 名称 / 类别"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
            <label className="check-inline">
              <input
                type="checkbox"
                checked={showOnlyDisabled}
                onChange={(e) => setShowOnlyDisabled(e.target.checked)}
              />
              只看禁用
            </label>
          </div>
        </div>
        {loading ? (
          <div className="meta">加载中…</div>
        ) : (
          <table className="rule-table">
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <input
                    type="checkbox"
                    checked={
                      selectedCodes.size === filteredDefs.length &&
                      filteredDefs.length > 0
                    }
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>label_code</th>
                <th>名称</th>
                <th>类别</th>
                <th>适用类型</th>
                <th>状态</th>
                <th>描述</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredDefs.map((d) => (
                <tr key={d.label_code + "@" + d.rule_version}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedCodes.has(d.label_code)}
                      onChange={() => toggleSelection(d.label_code)}
                    />
                  </td>
                  <td><code>{d.label_code}</code></td>
                  <td>{d.label_name}</td>
                  <td>{d.category}</td>
                  <td>{d.fund_types}</td>
                  <td>
                    <span
                      className={`status-pill ${d.enabled ? "status-pill-pos" : "status-pill-neg"}`}
                    >
                      {d.enabled ? "启用" : "禁用"}
                    </span>
                  </td>
                  <td className="meta">{d.description}</td>
                  <td>
                    <button
                      className={`btn ${d.enabled ? "btn-warn" : "btn-pos"}`}
                      onClick={() => toggleOne(d)}
                    >
                      {d.enabled ? "禁用" : "启用"}
                    </button>
                  </td>
                </tr>
              ))}
              {filteredDefs.length === 0 && (
                <tr>
                  <td colSpan={8} className="meta center">
                    没有匹配的规则。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* 变更审计日志 */}
      <div className="card">
        <h2>变更审计日志</h2>
        {changes.length === 0 ? (
          <div className="meta">最近 30 条没有变更记录。</div>
        ) : (
          <ul className="rule-audit">
            {changes.map((c) => (
              <li key={c.audit_id} className="rule-audit-row">
                <div>
                  <span
                    className={`status-pill ${c.payload.new_enabled ? "status-pill-pos" : "status-pill-neg"}`}
                  >
                    {c.payload.previous_enabled ? "已启用" : "已禁用"} → {c.payload.new_enabled ? "启用" : "禁用"}
                  </span>
                  <code className="ml-2">{c.payload.label_code}</code>
                  <span className="meta ml-2">@{c.payload.rule_version}</span>
                </div>
                <div className="meta">
                  by {c.operator}
                  {c.source_ip && <> · {c.source_ip}</>}
                  {c.payload.reason && <> · 原因：{c.payload.reason}</>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}