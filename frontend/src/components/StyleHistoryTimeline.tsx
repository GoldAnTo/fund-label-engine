import type { StyleHistory } from "../api";

/* ============================================================
   风格稳定性时间线（style_stable / style_drift / style_recent_shift）
   ============================================================ */

const TREND_META: Record<StyleHistory["trend"], { label: string; color: string; description: string }> = {
  stable: {
    label: "稳定",
    color: "var(--pos)",
    description: "近 N 次 run 持续命中 style_stable，风格一致性高",
  },
  drifting: {
    label: "漂移",
    color: "var(--warn)",
    description: "近期命中 style_drift，风格逐步偏离",
  },
  shifting: {
    label: "近期切换",
    color: "var(--neg)",
    description: "最近一期命中 style_recent_shift，风格出现明显切换",
  },
  insufficient_data: {
    label: "数据不足",
    color: "var(--text-3)",
    description: "历史 run 不足 2 期，暂无法判断趋势",
  },
};

const SUMMARY_META: Record<StyleHistoryEntrySummary, { label: string; color: string }> = {
  stable: { label: "稳定", color: "var(--pos)" },
  drift: { label: "漂移", color: "var(--warn)" },
  recent_shift: { label: "近期切换", color: "var(--neg)" },
  none: { label: "无信号", color: "var(--text-3)" },
};

type StyleHistoryEntrySummary = "stable" | "drift" | "recent_shift" | "none";

function formatDate(s: string): string {
  // 取前 10 位日期部分，避免时区噪音
  return (s || "").slice(0, 10) || "—";
}

export function StyleHistoryTimeline({ history }: { history: StyleHistory }) {
  const trend = TREND_META[history.trend];
  const timeline = history.timeline;

  return (
    <div className="style-history">
      {/* 当前状态 + 趋势 */}
      <div className="style-history-summary" style={{ borderLeft: `3px solid ${trend.color}` }}>
        <div className="style-history-trend">
          <span className="style-history-trend-label" style={{ background: trend.color }}>
            {trend.label}
          </span>
          <span className="style-history-trend-desc">{trend.description}</span>
        </div>
        <div className="style-history-counts">
          <span>
            <span className="count-num" style={{ color: "var(--pos)" }}>{history.stable_run_count}</span>
            <span className="count-label">稳定</span>
          </span>
          <span>
            <span className="count-num" style={{ color: "var(--warn)" }}>{history.drift_run_count}</span>
            <span className="count-label">漂移</span>
          </span>
          <span>
            <span className="count-num" style={{ color: "var(--neg)" }}>{history.shift_run_count}</span>
            <span className="count-label">近期切换</span>
          </span>
          <span className="count-total">共 {timeline.length} 期</span>
        </div>
      </div>

      {/* 时间线 */}
      {timeline.length === 0 ? (
        <div className="style-history-empty">
          该基金暂无风格稳定性历史数据（需要至少一次成功的标签 run）。
        </div>
      ) : (
        <ol className="style-history-timeline">
          {timeline.map((entry, idx) => {
            const meta = SUMMARY_META[entry.summary];
            const isCurrent = idx === timeline.length - 1;
            return (
              <li key={entry.run_id} className={`style-history-item ${isCurrent ? "is-current" : ""}`}>
                <span
                  className="style-history-dot"
                  style={{ background: meta.color }}
                  title={entry.labels.join(", ")}
                />
                <div className="style-history-content">
                  <div className="style-history-row1">
                    <span className="style-history-date" style={{ color: meta.color }}>
                      {formatDate(entry.data_as_of || entry.run_at)}
                    </span>
                    <span
                      className="style-history-pill"
                      style={{ background: meta.color, color: "white" }}
                    >
                      {meta.label}
                    </span>
                    {isCurrent && <span className="style-history-current-tag">当前</span>}
                    <span className="style-history-rule">v{entry.rule_version}</span>
                  </div>
                  <div className="style-history-row2">
                    <code className="style-history-runid">{entry.run_id}</code>
                    {entry.labels.length > 0 && (
                      <span className="style-history-labels">
                        命中：{entry.labels.join(" · ")}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
