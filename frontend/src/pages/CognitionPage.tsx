import { useEffect, useState, Component, ReactNode } from "react";
import {
  fetchThemes,
  postCognition,
  searchConcepts,
  postConceptCognition,
  searchStocks,
  postStockCognition,
  exportCognition,
  fetchMonitorOverview,
  runPipeline,
  type ThemeInfo,
  type ChainLink,
  type CognitionResponse,
  type ConceptBoard,
  type StockSearchResult,
  type MonitorOverview,
  type ICReview,
  type FundEvidencePacket,
  type AttentionItem,
  type InboxSnapshot,
  type ScreenSnapshot,
  type PipelineResult,
} from "../api";
import { DonutChart, HorizontalBarChart, SkeletonCard } from "../charts";
import {
  ValuationQuad,
  FundDetailPanel,
  useScrollSpy,
  EvidenceSummary,
  MonitorPanel,
  type EvidenceItem,
} from "../components/CognitionComponents";

// 标签映射
const CERTAINTY_LABEL: Record<string, string> = { high: "高确定性", medium: "中确定性", low: "低确定性" };
const GAP_LABEL: Record<string, string> = { positive: "正预期差", neutral: "中性", negative: "负预期差", unknown: "数据不足" };
const GAP_CLASS: Record<string, string> = { positive: "gap-positive", neutral: "gap-neutral", negative: "gap-negative", unknown: "gap-unknown" };
const TREND_LABEL: Record<string, string> = { increasing: "加仓", decreasing: "减仓", stable: "持平", insufficient_data: "数据不足" };
const CONVICTION_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };
const RISK_LABEL: Record<string, string> = { conservative: "保守", balanced: "适中", aggressive: "进取" };
const HORIZON_LABEL: Record<string, string> = { short: "短期", medium: "中期", long: "长期" };

// Pipeline 阶段标签
const PIPELINE_STAGE_LABELS: Record<string, string> = {
  screener: "筛选",
  cognition: "认知分析",
  ic_review: "投决会审查",
  memo: "投资备忘录",
  portfolio: "组合构建",
  monitoring: "投后监控",
};
const PIPELINE_STAGE_ORDER = ["screener", "cognition", "ic_review", "memo", "portfolio", "monitoring"];

// Pipeline 步骤状态样式
const PIPELINE_STEP_STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  completed: { bg: "rgba(22,163,74,0.1)", color: "#16a34a", label: "完成" },
  failed: { bg: "rgba(220,38,38,0.1)", color: "#dc2626", label: "失败" },
  skipped: { bg: "rgba(156,163,175,0.1)", color: "#6b7280", label: "跳过" },
  running: { bg: "rgba(59,130,246,0.1)", color: "#3b82f6", label: "运行中" },
  pending: { bg: "rgba(209,213,219,0.1)", color: "#9ca3af", label: "等待" },
};

function fmt(v: number | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "-";
  return Number.isInteger(v) ? `${v}${suffix}` : `${v.toFixed(1)}${suffix}`;
}

// Tab 按钮样式
const tabStyle = (active: boolean) => ({
  padding: "6px 14px",
  borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
  fontWeight: active ? 600 : 400,
  color: active ? "var(--text)" : "var(--text-3)",
  cursor: "pointer",
  fontSize: 13,
  background: "none",
  border: "none",
  borderLeft: "none",
  borderRight: "none",
  borderTop: "none",
} as const);

// 选项按钮样式
const optionBtnStyle = (selected: boolean) => ({
  padding: "4px 12px",
  borderRadius: "4px",
  border: selected ? "1px solid var(--accent)" : "1px solid var(--border)",
  background: selected ? "var(--accent-soft, rgba(59,130,246,0.08))" : "transparent",
  color: selected ? "var(--accent)" : "var(--text-2)",
  cursor: "pointer",
  fontSize: 12,
} as const);

// 临时 ErrorBoundary：渲染崩溃时把错误显示出来，而不是整页空白
class CognitionErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    console.error("[CognitionPage] render error:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "20px", margin: "20px", background: "#fff3f3", border: "1px solid #e7443c", borderRadius: "6px" }}>
          <div style={{ fontWeight: 600, color: "#c0392b", marginBottom: "8px" }}>渲染出错：</div>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "12px", color: "#333", margin: 0 }}>
            {this.state.error.message}
            {"\n\n"}
            {this.state.error.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function CognitionPage() {
  // 流程控制：1=输入区，2=结果页
  const [step, setStep] = useState<1 | 2>(1);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [direction, setDirection] = useState("");
  const [conviction, setConviction] = useState("medium");
  const [riskTolerance, setRiskTolerance] = useState("balanced");
  const [timeHorizon, setTimeHorizon] = useState("medium");
  const [result, setResult] = useState<CognitionResponse | null>(null);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 统一搜索
  const [searchKeyword, setSearchKeyword] = useState("");
  const [conceptResults, setConceptResults] = useState<ConceptBoard[]>([]);
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  // 高级选项折叠
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 用户观点
  const [beliefNote, setBeliefNote] = useState("");

  // Tab 切换
  const [activeTab, setActiveTab] = useState<"candidates" | "chain" | "validation" | "portfolio" | "memo">("candidates");

  // 基金选中与监控
  const [selectedFundCode, setSelectedFundCode] = useState<string | null>(null);
  const [monitorFundCode, setMonitorFundCode] = useState<string | null>(null);
  const [monitorData, setMonitorData] = useState<MonitorOverview | null>(null);
  const [monitorLoading, setMonitorLoading] = useState(false);
  const [monitorError, setMonitorError] = useState<string | null>(null);

  // 导出
  const [exporting, setExporting] = useState(false);

  // Inbox 展开状态
  const [inboxExpanded, setInboxExpanded] = useState(false);

  // useScrollSpy 必须在所有条件 return 之前调用，避免 Hooks 顺序变化
  const sectionIds = ["tab-candidates", "tab-chain", "tab-validation", "tab-portfolio", "tab-memo"];
  useScrollSpy(sectionIds);

  // 加载预设主题
  useEffect(() => {
    fetchThemes().then((r) => setThemes(r.themes)).catch(() => {});
  }, []);

  // 统一搜索：概念板块 + 个股
  useEffect(() => {
    if (!searchKeyword.trim()) {
      setConceptResults([]);
      setStockResults([]);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    const timer = setTimeout(() => {
      Promise.all([
        searchConcepts(searchKeyword.trim()).catch(() => [] as ConceptBoard[]),
        searchStocks(searchKeyword.trim()).catch(() => [] as StockSearchResult[]),
      ]).then(([concepts, stocks]) => {
        setConceptResults(concepts);
        setStockResults(stocks);
        setSearchLoading(false);
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [searchKeyword]);

  // 监控面板异步加载
  useEffect(() => {
    if (!monitorFundCode) {
      setMonitorData(null);
      setMonitorError(null);
      return;
    }
    let cancelled = false;
    setMonitorLoading(true);
    setMonitorError(null);
    fetchMonitorOverview(monitorFundCode).then(
      (data) => {
        if (cancelled) return;
        setMonitorData(data);
        setMonitorLoading(false);
      },
      (err) => {
        if (cancelled) return;
        setMonitorError(err instanceof Error ? err.message : String(err));
        setMonitorLoading(false);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [monitorFundCode]);

  // 主题方向分析
  const runThemeCognition = () => {
    if (!direction.trim()) return;
    setLoading(true);
    setError(null);
    postCognition(direction.trim(), undefined, conviction, riskTolerance, timeHorizon, beliefNote || undefined)
      .then((r) => {
        setResult(r);
        setStep(2);
        setActiveTab("candidates");
        setSelectedFundCode(null);
        setMonitorFundCode(null);
        // 同时触发 pipeline 运行，获取阶段状态
        setPipelineResult(null);
        runPipeline(direction.trim()).then(setPipelineResult).catch(() => {});
      })
      .catch(() => setError("分析失败，请重试"))
      .finally(() => setLoading(false));
  };

  // 概念板块分析
  const pickConcept = (concept: ConceptBoard) => {
    setLoading(true);
    setError(null);
    setSearchKeyword("");
    setShowDropdown(false);
    postConceptCognition(concept.code, concept.name, conviction, riskTolerance, timeHorizon, beliefNote || undefined)
      .then((r) => {
        setResult(r);
        setDirection(concept.name);
        setStep(2);
        setActiveTab("candidates");
        setSelectedFundCode(null);
        setMonitorFundCode(null);
        // 同时触发 pipeline 运行，获取阶段状态
        setPipelineResult(null);
        runPipeline(concept.name).then(setPipelineResult).catch(() => {});
      })
      .catch(() => setError("概念分析失败"))
      .finally(() => setLoading(false));
  };

  // 个股分析
  const pickStock = (stock: StockSearchResult) => {
    setLoading(true);
    setError(null);
    setSearchKeyword("");
    setShowDropdown(false);
    postStockCognition(stock.stock_code, stock.stock_name, conviction, riskTolerance, timeHorizon, beliefNote || undefined)
      .then((r) => {
        setResult(r as CognitionResponse);
        setDirection(`${stock.stock_name}（个股认知）`);
        setStep(2);
        setActiveTab("candidates");
        setSelectedFundCode(null);
        setMonitorFundCode(null);
        // 同时触发 pipeline 运行，获取阶段状态
        setPipelineResult(null);
        runPipeline(stock.stock_name).then(setPipelineResult).catch(() => {});
      })
      .catch(() => setError("个股分析失败"))
      .finally(() => setLoading(false));
  };

  const reset = () => {
    setStep(1);
    setDirection("");
    setResult(null);
    setPipelineResult(null);
    setSearchKeyword("");
    setSelectedFundCode(null);
    setMonitorFundCode(null);
    setError(null);
  };

  // === Step 1：输入区 ===
  if (step === 1) {
    return (
      <div className="main cognition-form">
        <h2 style={{ marginBottom: "4px" }}>你相信什么？</h2>
        <p style={{ color: "var(--text-3)", marginBottom: "24px" }}>
          输入方向关键词，或选择预设主题，系统帮你从认知推导到基金配置
        </p>

        {/* 搜索框 + 联想下拉 */}
        <div style={{ position: "relative", marginBottom: "16px" }}>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              className="custom-direction-input"
              style={{ flex: 1 }}
              value={searchKeyword}
              onChange={(e) => {
                setSearchKeyword(e.target.value);
                setShowDropdown(true);
              }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && searchKeyword.trim()) {
                  setDirection(searchKeyword.trim());
                  setShowDropdown(false);
                }
              }}
              placeholder="搜索概念板块或个股，如：AI、芯片、贵州茅台..."
              aria-label="搜索方向"
            />
            <button
              type="button"
              className="btn"
              onClick={() => {
                if (searchKeyword.trim()) {
                  setDirection(searchKeyword.trim());
                  setShowDropdown(false);
                }
              }}
            >
              填入
            </button>
          </div>

          {/* 联想下拉列表 */}
          {showDropdown && searchKeyword.trim() && (
            <div
              style={{
                position: "absolute",
                top: "100%",
                left: 0,
                right: 0,
                zIndex: 100,
                background: "var(--surface, #fff)",
                border: "1px solid var(--border)",
                borderRadius: "0 0 6px 6px",
                boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                maxHeight: "400px",
                overflowY: "auto",
              }}
            >
              {searchLoading && (
                <div style={{ padding: "12px", color: "var(--text-3)", fontSize: 13 }}>搜索中...</div>
              )}

              {/* 概念板块结果 */}
              {conceptResults.length > 0 && (
                <div style={{ borderBottom: "1px solid var(--border)" }}>
                  <div style={{ padding: "6px 12px", fontSize: 11, color: "var(--text-3)", background: "var(--surface-2, #f5f5f5)" }}>
                    概念板块
                  </div>
                  {conceptResults.slice(0, 5).map((c) => (
                    <div
                      key={c.code}
                      className="card concept-result-item"
                      style={{ margin: 0, borderRadius: 0, border: "none", borderBottom: "1px solid var(--border)" }}
                      onClick={() => pickConcept(c)}
                    >
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{c.name}</div>
                      <div style={{ fontSize: 12, color: "var(--text-2)" }}>{c.stock_count} 只成分股</div>
                    </div>
                  ))}
                </div>
              )}

              {/* 个股结果 */}
              {stockResults.length > 0 && (
                <div>
                  <div style={{ padding: "6px 12px", fontSize: 11, color: "var(--text-3)", background: "var(--surface-2, #f5f5f5)" }}>
                    个股
                  </div>
                  {stockResults.slice(0, 5).map((s) => (
                    <div
                      key={s.stock_code}
                      className="card concept-result-item"
                      style={{ margin: 0, borderRadius: 0, border: "none", borderBottom: "1px solid var(--border)" }}
                      onClick={() => pickStock(s)}
                    >
                      <div style={{ fontWeight: 600, fontSize: 13 }}>
                        {s.stock_name}
                        <span style={{ fontSize: 12, color: "var(--text-3)", marginLeft: "8px" }}>{s.stock_code}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-2)" }}>
                        {s.fund_count} 只基金持有
                        {s.pe != null && ` · PE ${s.pe}`}
                        {s.val_pct != null && ` · 分位 ${s.val_pct}%`}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!searchLoading && conceptResults.length === 0 && stockResults.length === 0 && (
                <div
                  style={{ padding: "12px", color: "var(--text-3)", fontSize: 13, cursor: "pointer" }}
                  onClick={() => {
                    setDirection(searchKeyword.trim());
                    setShowDropdown(false);
                  }}
                >
                  未找到匹配，将作为自定义方向分析：{searchKeyword.trim()}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 当前方向输入框 */}
        <div style={{ marginBottom: "16px" }}>
          <label htmlFor="cognition-direction" style={{ fontSize: 13, color: "var(--text-3)", marginBottom: "8px", display: "block" }}>
            分析方向：
          </label>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              id="cognition-direction"
              className="custom-direction-input"
              style={{ flex: 1 }}
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && direction.trim() && runThemeCognition()}
              placeholder="例如：AI、消费、创新药、新能源..."
              aria-label="分析方向"
            />
          </div>
        </div>

        {/* 快速选择预设主题 */}
        <div style={{ marginBottom: "16px" }}>
          <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: "8px" }}>快速选择：</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {themes.map((t) => (
              <button
                key={t.key}
                type="button"
                style={optionBtnStyle(direction === t.key)}
                onClick={() => setDirection(t.key)}
              >
                {t.name}
              </button>
            ))}
          </div>
        </div>

        {/* 高级选项折叠区 */}
        <div style={{ marginBottom: "16px" }}>
          <button
            type="button"
            style={{
              background: "none",
              border: "none",
              color: "var(--text-3)",
              fontSize: 13,
              cursor: "pointer",
              padding: "4px 0",
            }}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? "收起高级选项" : "展开高级选项"}
          </button>

          {showAdvanced && (
            <div style={{ marginTop: "12px", padding: "12px 16px", background: "var(--surface-2, #f5f5f5)", borderRadius: "6px" }}>
              {/* 信心强度 */}
              <div style={{ marginBottom: "12px" }}>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: "6px" }}>信心强度：</div>
                <div style={{ display: "flex", gap: "8px" }}>
                  {["low", "medium", "high"].map((c) => (
                    <button
                      key={c}
                      type="button"
                      style={optionBtnStyle(conviction === c)}
                      onClick={() => setConviction(c)}
                    >
                      {CONVICTION_LABEL[c]}
                    </button>
                  ))}
                </div>
              </div>

              {/* 风险偏好 */}
              <div style={{ marginBottom: "12px" }}>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: "6px" }}>风险偏好：</div>
                <div style={{ display: "flex", gap: "8px" }}>
                  {["conservative", "balanced", "aggressive"].map((r) => (
                    <button
                      key={r}
                      type="button"
                      style={optionBtnStyle(riskTolerance === r)}
                      onClick={() => setRiskTolerance(r)}
                    >
                      {RISK_LABEL[r]}
                    </button>
                  ))}
                </div>
              </div>

              {/* 投资周期 */}
              <div style={{ marginBottom: "12px" }}>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: "6px" }}>投资周期：</div>
                <div style={{ display: "flex", gap: "8px" }}>
                  {["short", "medium", "long"].map((h) => (
                    <button
                      key={h}
                      type="button"
                      style={optionBtnStyle(timeHorizon === h)}
                      onClick={() => setTimeHorizon(h)}
                    >
                      {HORIZON_LABEL[h]}
                    </button>
                  ))}
                </div>
              </div>

              {/* 我的观点 */}
              <div>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: "6px" }}>我的观点（可选，1000 字内）：</div>
                <textarea
                  className="custom-direction-input"
                  style={{ width: "100%", minHeight: "50px", fontFamily: "inherit", resize: "vertical" }}
                  value={beliefNote}
                  onChange={(e) => setBeliefNote(e.target.value.slice(0, 1000))}
                  placeholder="例如：受益于国产替代 + 下游需求扩张 + 估值合理..."
                />
              </div>
            </div>
          )}
        </div>

        {/* 错误提示 */}
        {error && (
          <div role="alert" style={{ color: "var(--neg)", padding: "8px 12px", background: "var(--neg-soft, #fff3f3)", borderRadius: "4px", marginBottom: "12px", fontSize: 13 }}>
            {error}
          </div>
        )}

        {/* 开始分析按钮 */}
        <button
          type="button"
          className="btn"
          style={{ width: "100%", opacity: direction.trim() ? 1 : 0.5 }}
          disabled={!direction.trim() || loading}
          onClick={runThemeCognition}
        >
          {loading ? "分析中..." : "开始分析"}
        </button>

        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "12px" }}>
            <SkeletonCard lines={2} />
            <SkeletonCard lines={1} />
            <SkeletonCard lines={3} />
          </div>
        )}
      </div>
    );
  }

  // === Step 2：结果页 ===
  if (step === 2 && result) {
    // 安全访问：个股认知可能缺少 step1/step2/step3/step5 字段
    const chain: ChainLink[] = result.step2_chain ?? [];
    const gap = result.step3_expectation_gap;
    const validation = result.step5_validation ?? null;
    const pf = result.step5_portfolio;
    const fundMatches = result.step4_fund_matches ?? [];
    const gatedOut = result.gated_out_funds ?? [];
    const screenSnapshot: ScreenSnapshot | null = result.screen_snapshot ?? null;
    const inbox: InboxSnapshot | null = result.inbox ?? null;

    // 安全读取 as_of_date（类型中未定义，运行时可能存在）
    const asOfDate = (result as { step1_judgment?: { as_of_date?: string | null } }).step1_judgment?.as_of_date ?? null;

    // 选中基金
    const selectedFund = selectedFundCode
      ? fundMatches.find((f) => f.fund_code === selectedFundCode) ?? null
      : null;

    // 选中基金的证据包（可选字段，安全访问）
    const evidencePacket: FundEvidencePacket | null = selectedFundCode
      ? result.evidence_packets?.find((p) => p.fund_code === selectedFundCode) ?? null
      : null;

    // 顶部关键指标（最多 3 个）
    const kpiMetrics: { label: string; value: string }[] = [];
    if (fundMatches.length > 0) {
      kpiMetrics.push({ label: "匹配基金", value: `${fundMatches.length} 只` });
    }
    if (pf) {
      kpiMetrics.push({ label: "认知仓位", value: fmt(pf.suggested_weight, "%") });
    }
    if (gatedOut.length > 0) {
      kpiMetrics.push({ label: "门禁拦截", value: `${gatedOut.length} 只` });
    }

    // 整理证据用于验证 Tab
    const evidenceItems: EvidenceItem[] = [];
    if (validation) {
      for (const ev of validation.supporting_evidence || []) {
        evidenceItems.push({
          category: "support",
          title: ev.claim || ev.source,
          detail: [ev.context, ev.source].filter(Boolean).join(" - "),
        });
      }
      for (const ev of validation.opposing_evidence || []) {
        evidenceItems.push({
          category: "oppose",
          title: ev.claim || ev.source,
          detail: [ev.context, ev.source].filter(Boolean).join(" - "),
        });
      }
    }
    if (gap) {
      if (gap.positive && gap.positive.length > 0) {
        evidenceItems.push({
          category: "support",
          title: `正向预期差（${gap.positive.length} 条）`,
          detail: gap.positive.map((c) => c.link_name).slice(0, 3).join("、"),
        });
      }
      if (gap.negative && gap.negative.length > 0) {
        evidenceItems.push({
          category: "oppose",
          title: `负向预期差（${gap.negative.length} 条）`,
          detail: gap.negative.map((c) => c.link_name).slice(0, 3).join("、"),
        });
      }
    }

    // 预期差摘要统计
    const gapPositive = gap?.positive?.length ?? 0;
    const gapNeutral = gap?.neutral?.length ?? 0;
    const gapNegative = gap?.negative?.length ?? 0;

    return (
      <CognitionErrorBoundary>
        <div className="main">
          {/* Pipeline 状态条 */}
          {pipelineResult && (
            <section className="card" style={{ marginBottom: "12px", padding: "10px 16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>Pipeline</span>
                <span style={{ fontSize: 11, color: "var(--text-3)", fontFamily: "monospace" }}>
                  {pipelineResult.run.run_id}
                </span>
                {pipelineResult.partial && (
                  <span style={{
                    fontSize: 11,
                    padding: "2px 8px",
                    borderRadius: "3px",
                    background: "rgba(243,156,18,0.1)",
                    color: "#ca8a04",
                    fontWeight: 600,
                  }}>
                    部分完成
                  </span>
                )}
                {/* 整体运行状态 */}
                <span style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: "3px",
                  background: pipelineResult.run.status === "completed" ? "rgba(22,163,74,0.1)" : "rgba(220,38,38,0.1)",
                  color: pipelineResult.run.status === "completed" ? "#16a34a" : "#dc2626",
                  fontWeight: 600,
                }}>
                  {pipelineResult.run.status === "completed" ? "完成" : pipelineResult.run.status === "failed" ? "失败" : pipelineResult.run.status}
                </span>
                {/* 各阶段状态徽章 */}
                <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginLeft: "auto" }}>
                  {PIPELINE_STAGE_ORDER.map((stage) => {
                    const step = pipelineResult.run.steps.find((s) => s.stage === stage);
                    const status = step?.status ?? "pending";
                    const style = PIPELINE_STEP_STATUS_STYLE[status] ?? PIPELINE_STEP_STATUS_STYLE.pending;
                    return (
                      <span
                        key={stage}
                        title={step?.error || style.label}
                        style={{
                          fontSize: 11,
                          padding: "2px 8px",
                          borderRadius: "3px",
                          background: style.bg,
                          color: style.color,
                          fontWeight: 600,
                        }}
                      >
                        {PIPELINE_STAGE_LABELS[stage]}
                      </span>
                    );
                  })}
                </div>
              </div>
            </section>
          )}

          {/* 顶部摘要条 */}
          <div className="cognition-selection-bar">
            <div className="cognition-selection-info">
              <span>方向：<strong>{result.direction}</strong></span>
              <span className="cognition-selection-sep">|</span>
              <span>信心：<strong>{CONVICTION_LABEL[result.conviction] ?? "中"}</strong></span>
              {kpiMetrics.map((m, i) => (
                <span key={i}>
                  <span className="cognition-selection-sep">|</span>
                  <span>{m.label}：<strong>{m.value}</strong></span>
                </span>
              ))}
              {asOfDate && (
                <span>
                  <span className="cognition-selection-sep">|</span>
                  <span style={{ color: "var(--text-3)" }}>数据日期：{asOfDate}</span>
                </span>
              )}
            </div>
            <div className="cognition-selection-actions">
              <button type="button" className="btn btn-sm" onClick={reset}>重新分析</button>
            </div>
          </div>

          {/* 错误提示 */}
          {error && (
            <div role="alert" style={{ color: "var(--neg)", padding: "8px 12px", background: "var(--neg-soft, #fff3f3)", borderRadius: "4px", marginBottom: "12px", fontSize: 13 }}>
              {error}
            </div>
          )}

          {/* Inbox：决策队列 */}
          {inbox && inbox.open_items > 0 && (
            <section className="card" style={{ marginBottom: "12px" }}>
              <div
                style={{ display: "flex", alignItems: "center", gap: "12px", cursor: "pointer" }}
                onClick={() => setInboxExpanded(!inboxExpanded)}
              >
                <span style={{ fontWeight: 600, fontSize: 14 }}>Inbox</span>
                {/* 高优先级红色徽章 */}
                {inbox.high_severity > 0 && (
                  <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "22px",
                    height: "22px",
                    padding: "0 6px",
                    borderRadius: "11px",
                    background: "#dc2626",
                    color: "#fff",
                    fontSize: 12,
                    fontWeight: 600,
                  }}>
                    {inbox.high_severity}
                  </span>
                )}
                {/* 中优先级黄色徽章 */}
                {inbox.medium_severity > 0 && (
                  <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "22px",
                    height: "22px",
                    padding: "0 6px",
                    borderRadius: "11px",
                    background: "#ca8a04",
                    color: "#fff",
                    fontSize: 12,
                    fontWeight: 600,
                  }}>
                    {inbox.medium_severity}
                  </span>
                )}
                {/* 低优先级灰色徽章 */}
                {inbox.low_severity > 0 && (
                  <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "22px",
                    height: "22px",
                    padding: "0 6px",
                    borderRadius: "11px",
                    background: "#6b7280",
                    color: "#fff",
                    fontSize: 12,
                    fontWeight: 600,
                  }}>
                    {inbox.low_severity}
                  </span>
                )}
                <span style={{ fontSize: 12, color: "var(--text-3)", marginLeft: "auto" }}>
                  {inboxExpanded ? "收起" : "展开"}（共 {inbox.open_items} 项）
                </span>
              </div>

              {/* 展开的 attention items 列表 */}
              {inboxExpanded && inbox.items.length > 0 && (
                <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  {inbox.items.map((item: AttentionItem) => {
                    const severityColor = item.severity === "high" ? "#dc2626" : item.severity === "medium" ? "#ca8a04" : "#6b7280";
                    const severityLabel = item.severity === "high" ? "高" : item.severity === "medium" ? "中" : "低";
                    return (
                      <div
                        key={item.item_id}
                        style={{
                          padding: "10px 12px",
                          background: "var(--surface-2, #f5f5f5)",
                          borderRadius: "6px",
                          borderLeft: `3px solid ${severityColor}`,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span style={{ fontSize: 13, fontWeight: 600 }}>{item.title}</span>
                            <span style={{
                              fontSize: 11,
                              padding: "1px 6px",
                              borderRadius: "3px",
                              background: severityColor,
                              color: "#fff",
                              fontWeight: 600,
                            }}>
                              {severityLabel}
                            </span>
                            <span style={{ fontSize: 11, padding: "1px 6px", borderRadius: "3px", background: "var(--surface, #e0e0e0)", color: "var(--text-3)" }}>
                              {item.source_type_display}
                            </span>
                          </div>
                          {item.fund_code && (
                            <span style={{ fontSize: 12, color: "var(--text-3)", fontFamily: "monospace" }}>{item.fund_code}</span>
                          )}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.5 }}>
                          {item.body}
                        </div>
                        {item.response_set.length > 0 && (
                          <div style={{ marginTop: "6px", display: "flex", gap: "6px", flexWrap: "wrap" }}>
                            {item.response_set.map((r) => (
                              <span
                                key={r}
                                style={{
                                  fontSize: 11,
                                  padding: "2px 8px",
                                  borderRadius: "3px",
                                  border: "1px solid var(--border, #e0e0e0)",
                                  color: "var(--text-3)",
                                  background: "transparent",
                                }}
                              >
                                {r}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {/* Tab 导航 */}
          <div id="tab-nav" style={{ display: "flex", gap: "4px", borderBottom: "1px solid var(--border)", marginBottom: "16px" }}>
            <button type="button" style={tabStyle(activeTab === "candidates")} onClick={() => setActiveTab("candidates")}>
              基金候选{fundMatches.length > 0 && ` (${fundMatches.length})`}
            </button>
            <button type="button" style={tabStyle(activeTab === "chain")} onClick={() => setActiveTab("chain")}>
              产业链分析
            </button>
            <button type="button" style={tabStyle(activeTab === "validation")} onClick={() => setActiveTab("validation")}>
              认知验证
            </button>
            <button type="button" style={tabStyle(activeTab === "portfolio")} onClick={() => setActiveTab("portfolio")}>
              组合草案
            </button>
            <button type="button" style={tabStyle(activeTab === "memo")} onClick={() => setActiveTab("memo")}>
              投资备忘录
            </button>
          </div>

          {/* 主区 + 右侧栏 */}
          <div style={{ display: "flex", gap: "16px", alignItems: "flex-start" }}>
            {/* 主内容区 */}
            <div style={{ flex: 1, minWidth: 0 }}>

              {/* Tab 1：基金候选 */}
              {activeTab === "candidates" && (
                <div id="tab-candidates">
                  {fundMatches.length === 0 ? (
                    <div className="cognition-empty-state" role="status">
                      <div className="cognition-empty-state-title">当前没有合格研究候选</div>
                      <div className="cognition-empty-state-detail">
                        所有匹配基金都未通过估值门禁或数据缺失。建议调整方向或估值容忍度。
                      </div>
                    </div>
                  ) : (
                    <section className="card" style={{ marginBottom: "12px" }}>
                      <div style={{ fontWeight: 600, marginBottom: "8px" }}>匹配基金</div>
                      <table className="table-v2">
                        <thead>
                          <tr>
                            <th>代码</th>
                            <th>名称</th>
                            <th>匹配度</th>
                            <th>PE</th>
                            <th>估值分位</th>
                            <th>门禁</th>
                            <th>趋势</th>
                            <th>排名分</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fundMatches.map((f) => {
                            const v = (f.valuation ?? {}) as Record<string, unknown>;
                            const isSelected = selectedFundCode === f.fund_code;
                            // 从筛选快照中查找该基金的排名分
                            const screenResult = screenSnapshot?.results.find((r) => r.fund_code === f.fund_code);
                            return (
                              <tr
                                key={f.fund_code}
                                className={isSelected ? "selected" : ""}
                                onClick={() => setSelectedFundCode(f.fund_code)}
                                style={{ cursor: "pointer" }}
                              >
                                <td>{f.fund_code}</td>
                                <td>{f.fund_name}</td>
                                <td>{fmt(f.match_pct, "%")}</td>
                                <td>{fmt(v.weighted_pe as number | null)}</td>
                                <td>{fmt(v.weighted_val_pct as number | null, "%")}</td>
                                <td>
                                  {f.gate ? (
                                    f.gate.passed ? (
                                      <span style={{ color: "var(--pos)" }}>通过</span>
                                    ) : (
                                      <span style={{ color: "var(--neg)" }} title={f.gate.violations.join("; ")}>拦截</span>
                                    )
                                  ) : "-"}
                                </td>
                                <td style={{ fontSize: 12 }}>{TREND_LABEL[f.trend?.trend] ?? f.trend?.trend ?? "-"}</td>
                                <td style={{ fontWeight: 600, color: "var(--accent)" }}>
                                  {screenResult && screenResult.passed ? fmt(screenResult.rank_score) : "-"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: "6px" }}>
                        点击行查看右侧基金详情
                      </p>
                    </section>
                  )}

                  {/* 被门禁拦截的基金（折叠） */}
                  {gatedOut.length > 0 && (
                    <details className="card" style={{ marginBottom: "12px" }}>
                      <summary style={{ cursor: "pointer", fontWeight: 600, color: "var(--text-2)" }}>
                        被门禁拦截的基金（{gatedOut.length}）
                      </summary>
                      <table className="table-v2" style={{ marginTop: "8px" }}>
                        <thead>
                          <tr>
                            <th>代码</th>
                            <th>名称</th>
                            <th>匹配度</th>
                            <th>拦截原因</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gatedOut.map((f) => (
                            <tr key={f.fund_code}>
                              <td>{f.fund_code}</td>
                              <td>{f.fund_name}</td>
                              <td>{fmt(f.match_pct, "%")}</td>
                              <td style={{ color: "var(--neg)", fontSize: 12 }}>{f.gate.violations.join("; ")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </details>
                  )}

                  {/* 筛选详情（折叠）：展示筛选准则、通过/失败统计、失败原因 */}
                  {screenSnapshot && (
                    <details className="card" style={{ marginBottom: "12px" }}>
                      <summary style={{ cursor: "pointer", fontWeight: 600, color: "var(--text-2)" }}>
                        筛选详情（{screenSnapshot.passed_funds} 通过 / {screenSnapshot.failed_funds} 未通过 / 共 {screenSnapshot.total_funds} 只）
                      </summary>

                      {/* 统计概览 */}
                      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginTop: "12px", marginBottom: "12px", fontSize: 13 }}>
                        <span>
                          <span style={{ color: "var(--text-3)" }}>筛选准则 </span>
                          <span style={{ fontWeight: 600 }}>{screenSnapshot.screen_criteria_count}</span> 条
                        </span>
                        {screenSnapshot.ranking_blend.length > 0 && (
                          <span>
                            <span style={{ color: "var(--text-3)" }}>排名指标 </span>
                            <span style={{ fontWeight: 600 }}>{screenSnapshot.ranking_blend.length}</span> 个
                            <span style={{ color: "var(--text-3)", marginLeft: "4px" }}>
                              （{screenSnapshot.ranking_blend.map((b) => b.metric).join("、")}）
                            </span>
                          </span>
                        )}
                        <span style={{ color: "var(--text-3)" }}>生成于 {screenSnapshot.created_at}</span>
                      </div>

                      {/* 未通过基金及失败原因 */}
                      {screenSnapshot.results.filter((r) => !r.passed).length > 0 && (
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: "8px" }}>未通过基金及失败原因</div>
                          <table className="table-v2">
                            <thead>
                              <tr>
                                <th>代码</th>
                                <th>名称</th>
                                <th>失败准则</th>
                              </tr>
                            </thead>
                            <tbody>
                              {screenSnapshot.results.filter((r) => !r.passed).map((r) => (
                                <tr key={r.fund_code}>
                                  <td>{r.fund_code}</td>
                                  <td>{r.fund_name}</td>
                                  <td style={{ fontSize: 12, color: "var(--neg)" }}>
                                    {r.fail_reasons.map((fr) => {
                                      const valStr = fr.observed !== null ? String(fr.observed) : "数据不足";
                                      return `${fr.metric} ${fr.operator} ${fr.threshold}（观测值 ${valStr}）`;
                                    }).join("；")}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {/* 通过基金排名明细 */}
                      {screenSnapshot.results.filter((r) => r.passed && r.rank_components.length > 0).length > 0 && (
                        <div style={{ marginTop: "12px" }}>
                          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: "8px" }}>通过基金排名明细</div>
                          <table className="table-v2">
                            <thead>
                              <tr>
                                <th>代码</th>
                                <th>名称</th>
                                <th>排名分</th>
                                <th>排名明细</th>
                              </tr>
                            </thead>
                            <tbody>
                              {screenSnapshot.results.filter((r) => r.passed && r.rank_components.length > 0).map((r) => (
                                <tr key={r.fund_code}>
                                  <td>{r.fund_code}</td>
                                  <td>{r.fund_name}</td>
                                  <td style={{ fontWeight: 600, color: "var(--accent)" }}>{fmt(r.rank_score)}</td>
                                  <td style={{ fontSize: 12, color: "var(--text-2)" }}>
                                    {r.rank_components.map((rc) => {
                                      const obsStr = rc.observed !== null ? String(rc.observed) : "-";
                                      return `${rc.metric}: 百分位 ${fmt(rc.percentile)}, 贡献 ${fmt(rc.contribution)}（观测值 ${obsStr}）`;
                                    }).join("；")}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </details>
                  )}
                </div>
              )}

              {/* Tab 2：产业链分析 */}
              {activeTab === "chain" && (
                <div id="tab-chain">
                  {/* 预期差摘要 */}
                  {gap && (
                    <section className="card" style={{ marginBottom: "12px" }}>
                      <div style={{ fontWeight: 600, marginBottom: "8px" }}>预期差摘要</div>
                      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                        <span style={{ color: "var(--pos)" }}>
                          正预期差：{gapPositive} 个环节
                          {gap.positive && gap.positive.length > 0 && (
                            `（${gap.positive.map((c) => c.link_name).slice(0, 3).join("、")}）`
                          )}
                        </span>
                        <span style={{ color: "var(--text-2)" }}>
                          中性：{gapNeutral} 个环节
                          {gap.neutral && gap.neutral.length > 0 && (
                            `（${gap.neutral.map((c) => c.link_name).slice(0, 3).join("、")}）`
                          )}
                        </span>
                        <span style={{ color: "var(--neg)" }}>
                          负预期差：{gapNegative} 个环节
                          {gap.negative && gap.negative.length > 0 && (
                            `（${gap.negative.map((c) => c.link_name).slice(0, 3).join("、")}）`
                          )}
                        </span>
                      </div>
                      {gap.summary && (
                        <p style={{ marginTop: "8px", color: "var(--text-2)", fontSize: 13 }}>{gap.summary}</p>
                      )}
                      {gap.best_link && (
                        <p style={{ marginTop: "6px", fontSize: 13 }}>
                          <span style={{ color: "var(--text-3)" }}>最优环节：</span>
                          <strong>{gap.best_link.link_name}</strong>
                          <span style={{ color: "var(--text-3)", marginLeft: "8px" }}>评分 {fmt(gap.best_link.score)}</span>
                        </p>
                      )}
                    </section>
                  )}

                  {/* 环节表格（精简） */}
                  {chain.length > 0 ? (
                    <section className="card" style={{ marginBottom: "12px" }}>
                      <div style={{ fontWeight: 600, marginBottom: "8px" }}>产业链环节</div>
                      <table className="table-v2">
                        <thead>
                          <tr>
                            <th>环节</th>
                            <th>确定性</th>
                            <th>PE</th>
                            <th>预期差</th>
                            <th>评分</th>
                          </tr>
                        </thead>
                        <tbody>
                          {chain.map((link) => (
                            <tr key={link.link_name}>
                              <td>{link.link_name}</td>
                              <td>{CERTAINTY_LABEL[link.certainty] ?? link.certainty}</td>
                              <td>{fmt(link.pe)}</td>
                              <td>
                                <span className={GAP_CLASS[link.expectation_gap] ?? "gap-unknown"}>
                                  {GAP_LABEL[link.expectation_gap] ?? link.expectation_gap}
                                </span>
                              </td>
                              <td>{fmt(link.score)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </section>
                  ) : (
                    <div className="cognition-empty-state" role="status">
                      <div className="cognition-empty-state-title">暂无产业链数据</div>
                      <div className="cognition-empty-state-detail">
                        个股认知不包含产业链分析，请尝试主题或概念方向。
                      </div>
                    </div>
                  )}

                  {/* 估值四维 */}
                  {chain.length > 0 && fundMatches.length > 0 && gap && (
                    <ValuationQuad
                      expectationGap={gap}
                      chain={chain}
                      fundMatches={fundMatches}
                    />
                  )}
                </div>
              )}

              {/* Tab 3：认知验证 */}
              {activeTab === "validation" && (
                <div id="tab-validation">
                  {validation ? (
                    <>
                      {/* 裁决结论 */}
                      <section className="card" style={{ marginBottom: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                          <span style={{ fontWeight: 600 }}>裁决结论</span>
                          <span style={{
                            padding: "4px 12px",
                            borderRadius: "4px",
                            background: validation.verdict === "认知有效" || validation.verdict === "认知基本有效" ? "var(--pos)" : validation.verdict === "认知有分歧" ? "var(--warn)" : "var(--neg)",
                            color: "#fff",
                            fontSize: 13,
                            fontWeight: 600,
                          }}>
                            {validation.verdict}
                          </span>
                        </div>
                        <p style={{ color: "var(--text-2)", fontSize: 13, marginBottom: "8px" }}>{validation.verdict_detail}</p>
                        <div style={{ display: "flex", gap: "16px", fontSize: 13 }}>
                          <span style={{ color: "var(--pos)" }}>支持证据 {validation.evidence_counts.supporting}</span>
                          <span style={{ color: "var(--neg)" }}>反对证据 {validation.evidence_counts.opposing}</span>
                        </div>
                      </section>

                      {/* 支持证据 + 反对证据（两列） */}
                      <EvidenceSummary items={evidenceItems.slice(0, 10)} />

                      {/* 推理链（折叠） */}
                      {validation.reasoning_chain.length > 0 && (
                        <details className="card" style={{ marginTop: "12px" }}>
                          <summary style={{ cursor: "pointer", fontWeight: 600 }}>推理链（{validation.reasoning_chain.length} 步）</summary>
                          <div style={{ marginTop: "12px" }}>
                            {validation.reasoning_chain.map((node, i) => (
                              <div key={i} style={{ display: "flex", gap: "8px", marginBottom: "6px", fontSize: 13 }}>
                                <span style={{ color: "var(--text-3)", minWidth: "80px" }}>{node.step}</span>
                                <span style={{ flex: 1 }}>{node.description}</span>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}

                      {/* 多空辩论（折叠） */}
                      {validation.debate && validation.debate.length > 0 && (
                        <details className="card" style={{ marginTop: "12px" }}>
                          <summary style={{ cursor: "pointer", fontWeight: 600 }}>多空辩论</summary>
                          <div style={{ marginTop: "12px" }}>
                            {validation.debate.map((round) => (
                              <div key={round.round} style={{ marginBottom: "12px", padding: "8px 12px", background: "var(--surface-2, #f5f5f5)", borderRadius: "6px" }}>
                                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: "6px" }}>Round {round.round}</div>
                                <div style={{ borderLeft: "3px solid var(--pos)", paddingLeft: "8px", marginBottom: "6px" }}>
                                  <span style={{ fontSize: 12, color: "var(--pos)", fontWeight: 600 }}>Bull </span>
                                  <span style={{ fontSize: 13 }}>{round.bull_argument.claim}</span>
                                </div>
                                {round.bear_rebuttal ? (
                                  <div style={{ borderLeft: "3px solid var(--neg)", paddingLeft: "8px", marginBottom: "6px" }}>
                                    <span style={{ fontSize: 12, color: "var(--neg)", fontWeight: 600 }}>Bear </span>
                                    <span style={{ fontSize: 13 }}>{round.bear_rebuttal.claim}</span>
                                  </div>
                                ) : (
                                  <div style={{ borderLeft: "3px solid var(--text-3)", paddingLeft: "8px", marginBottom: "6px" }}>
                                    <span style={{ fontSize: 12, color: "var(--text-3)" }}>Bear 无反驳</span>
                                  </div>
                                )}
                                {round.bull_response && (
                                  <div style={{ borderLeft: "3px solid var(--pos)", paddingLeft: "8px" }}>
                                    <span style={{ fontSize: 12, color: "var(--pos)", fontWeight: 600 }}>Bull 回应 </span>
                                    <span style={{ fontSize: 13 }}>{round.bull_response.claim}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </details>
                      )}

                      {/* 认知反馈（折叠） */}
                      {validation.cognition_feedback &&
                        validation.cognition_feedback.validation_verdict !== "认知有效" &&
                        validation.cognition_feedback.correction_suggestions.length > 0 && (
                        <details className="card" style={{ marginTop: "12px" }}>
                          <summary style={{ cursor: "pointer", fontWeight: 600 }}>认知反馈</summary>
                          <div style={{ marginTop: "12px" }}>
                            <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: "6px" }}>
                              原始认知：{validation.cognition_feedback.original_belief}
                            </div>
                            {validation.cognition_feedback.adjusted_belief !== validation.cognition_feedback.original_belief && (
                              <div style={{ fontSize: 13, color: "var(--warn)", marginBottom: "8px" }}>
                                修正认知：{validation.cognition_feedback.adjusted_belief}
                              </div>
                            )}
                            {validation.cognition_feedback.correction_suggestions.map((s, i) => (
                              <div key={i} style={{ fontSize: 13, color: "var(--text-2)", padding: "4px 8px", marginBottom: "4px", background: "rgba(243,156,18,0.05)", borderRadius: "4px" }}>
                                {s}
                              </div>
                            ))}
                          </div>
                        </details>
                      )}

                      {/* 投决会门槛审查 */}
                      {result.ic_review && (() => {
                        const ic: ICReview = result.ic_review!;
                        const isPass = ic.verdict === "pass";
                        const scorePct = Math.min(100, Math.round(ic.gate_score));
                        const cutoffPct = Math.min(100, Math.round(ic.cutoff));
                        const pillarLabel: Record<string, string> = {
                          conviction: "投资信心",
                          constitution_fit: "策略适配",
                          data_quality: "数据质量",
                        };
                        const pillarWeight: Record<string, string> = {
                          conviction: "45%",
                          constitution_fit: "35%",
                          data_quality: "20%",
                        };
                        return (
                          <section className="card" style={{ marginTop: "12px" }}>
                            <div style={{ fontWeight: 600, marginBottom: "12px" }}>投决会审查</div>

                            {/* 大字 verdict */}
                            <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "12px" }}>
                              <span style={{
                                fontSize: 28,
                                fontWeight: 700,
                                color: isPass ? "var(--pos)" : "var(--neg)",
                              }}>
                                {isPass ? "PASS" : "FAIL"}
                              </span>
                              {ic.is_override && (
                                <span style={{
                                  padding: "2px 8px",
                                  borderRadius: "4px",
                                  background: "var(--warn)",
                                  color: "#fff",
                                  fontSize: 12,
                                  fontWeight: 600,
                                }}>
                                  已覆盖
                                </span>
                              )}
                              {ic.timestamp && (
                                <span style={{ fontSize: 12, color: "var(--text-3)" }}>{ic.timestamp}</span>
                              )}
                            </div>

                            {/* Gate Score vs Cutoff 进度条 */}
                            <div style={{ marginBottom: "12px" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: "6px" }}>
                                <span style={{ color: "var(--text-3)" }}>Gate Score</span>
                                <span style={{ fontWeight: 600, color: isPass ? "var(--pos)" : "var(--neg)" }}>
                                  {ic.gate_score.toFixed(1)} / {ic.cutoff.toFixed(0)}
                                </span>
                              </div>
                              <div style={{ position: "relative", height: "12px", background: "var(--surface-2, #e8e8e8)", borderRadius: "6px", overflow: "hidden" }}>
                                <div style={{
                                  position: "absolute",
                                  left: 0,
                                  top: 0,
                                  height: "100%",
                                  width: `${scorePct}%`,
                                  background: isPass ? "var(--pos)" : "var(--neg)",
                                  transition: "width 0.3s",
                                }} />
                                {/* 通过线标记 */}
                                <div style={{
                                  position: "absolute",
                                  left: `${cutoffPct}%`,
                                  top: -2,
                                  height: "16px",
                                  width: "2px",
                                  background: "var(--text-2)",
                                }} />
                              </div>
                              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: "4px" }}>
                                通过线 {ic.cutoff.toFixed(0)} 分
                              </div>
                            </div>

                            {/* fail_reason */}
                            {ic.fail_reason && (
                              <div style={{
                                padding: "8px 12px",
                                background: "var(--neg-soft, #fff3f3)",
                                border: "1px solid var(--neg)",
                                borderRadius: "4px",
                                marginBottom: "12px",
                                fontSize: 13,
                                color: "var(--neg)",
                              }}>
                                {ic.fail_reason}
                              </div>
                            )}

                            {/* 三支柱评分 */}
                            <div style={{ marginBottom: "12px" }}>
                              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: "8px" }}>评分支柱</div>
                              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                                {ic.pillars.map((p) => {
                                  const weak = p.score < 25;
                                  return (
                                    <div key={p.name} style={{
                                      flex: "1 1 180px",
                                      padding: "10px 12px",
                                      background: "var(--surface-2, #f5f5f5)",
                                      borderRadius: "6px",
                                      border: weak ? "1px solid var(--neg)" : "1px solid transparent",
                                    }}>
                                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                                        <span style={{ fontSize: 13, fontWeight: 600 }}>
                                          {pillarLabel[p.name] ?? p.name}
                                        </span>
                                        <span style={{ fontSize: 11, color: "var(--text-3)" }}>
                                          权重 {pillarWeight[p.name] ?? "-"}
                                        </span>
                                      </div>
                                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                                        <div style={{ flex: 1, height: "8px", background: "#e0e0e0", borderRadius: "4px", overflow: "hidden" }}>
                                          <div style={{
                                            height: "100%",
                                            width: `${Math.min(100, p.score)}%`,
                                            background: weak ? "var(--neg)" : p.score >= 70 ? "var(--pos)" : "var(--warn)",
                                          }} />
                                        </div>
                                        <span style={{
                                          fontSize: 14,
                                          fontWeight: 700,
                                          color: weak ? "var(--neg)" : p.score >= 70 ? "var(--pos)" : "var(--warn)",
                                          minWidth: "36px",
                                          textAlign: "right",
                                        }}>
                                          {p.score.toFixed(1)}
                                        </span>
                                      </div>
                                      {/* 组件明细 */}
                                      <div style={{ fontSize: 11, color: "var(--text-3)" }}>
                                        {p.components.map((c, i) => (
                                          <div key={i} style={{ display: "flex", justifyContent: "space-between", marginTop: "2px" }}>
                                            <span>{c.name}</span>
                                            <span style={{
                                              color: c.state === "contradicted" ? "var(--neg)" : c.state === "unknown" ? "var(--text-3)" : "var(--pos)",
                                            }}>
                                              {c.score.toFixed(0)} ({c.note})
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>

                            {/* 硬性门槛列表 */}
                            {ic.hurdles.length > 0 && (
                              <div>
                                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: "8px" }}>硬性门槛</div>
                                <table className="table-v2">
                                  <thead>
                                    <tr>
                                      <th>门槛</th>
                                      <th>观测值</th>
                                      <th>阈值</th>
                                      <th>结果</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {ic.hurdles.map((h) => (
                                      <tr key={h.hurdle_id}>
                                        <td style={{ fontSize: 13 }}>{h.name}</td>
                                        <td style={{ fontSize: 13 }}>
                                          {h.observed !== null ? h.observed : "-"}
                                        </td>
                                        <td style={{ fontSize: 13 }}>
                                          {h.operator} {h.threshold}
                                        </td>
                                        <td style={{ fontSize: 13 }}>
                                          {h.passed === null ? (
                                            <span style={{ color: "var(--text-3)" }}>无法判断</span>
                                          ) : h.passed ? (
                                            <span style={{ color: "var(--pos)" }}>通过</span>
                                          ) : (
                                            <span style={{ color: "var(--neg)" }}>未通过</span>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}

                            {/* 覆盖说明 */}
                            {ic.is_override && ic.override_rationale && (
                              <div style={{
                                marginTop: "8px",
                                padding: "8px 12px",
                                background: "rgba(243,156,18,0.08)",
                                border: "1px solid rgba(243,156,18,0.3)",
                                borderRadius: "4px",
                                fontSize: 13,
                                color: "var(--warn)",
                              }}>
                                覆盖原因：{ic.override_rationale}
                                {ic.prior_verdict && `（原裁决：${ic.prior_verdict}）`}
                              </div>
                            )}
                          </section>
                        );
                      })()}

                      {/* 假设追踪：Brier Score + 贝叶斯更新 */}
                      {result.thesis_tracker && (() => {
                        const t = result.thesis_tracker;
                        const priorPct = Math.round(t.prior_probability * 100);
                        const postPct = Math.round(t.posterior_probability * 100);
                        const changePct = Math.round(t.probability_change * 100);
                        const accuracyColor = t.prediction_accuracy === "good" ? "var(--pos)" : t.prediction_accuracy === "fair" ? "var(--warn)" : t.prediction_accuracy === "poor" ? "var(--neg)" : "var(--text-3)";
                        const accuracyLabel = t.prediction_accuracy === "good" ? "优秀" : t.prediction_accuracy === "fair" ? "一般" : t.prediction_accuracy === "poor" ? "较差" : "未验证";
                        return (
                          <section className="card" style={{ marginTop: "12px" }}>
                            <div style={{ fontWeight: 600, marginBottom: "12px" }}>假设追踪</div>

                            {/* 先验 -> 后验 概率变化条 */}
                            <div style={{ marginBottom: "12px" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: "6px" }}>
                                <span style={{ color: "var(--text-3)" }}>先验概率 {priorPct}%</span>
                                <span style={{ color: changePct >= 0 ? "var(--pos)" : "var(--neg)", fontWeight: 600 }}>
                                  {changePct >= 0 ? "+" : ""}{changePct}%
                                </span>
                                <span style={{ color: "var(--accent)", fontWeight: 600 }}>后验概率 {postPct}%</span>
                              </div>
                              <div style={{ position: "relative", height: "10px", background: "var(--surface-2, #e8e8e8)", borderRadius: "5px", overflow: "hidden" }}>
                                <div style={{
                                  position: "absolute",
                                  left: 0,
                                  top: 0,
                                  height: "100%",
                                  width: `${priorPct}%`,
                                  background: "var(--text-3)",
                                  opacity: 0.4,
                                }} />
                                <div style={{
                                  position: "absolute",
                                  left: 0,
                                  top: 0,
                                  height: "100%",
                                  width: `${postPct}%`,
                                  background: "var(--accent)",
                                }} />
                              </div>
                            </div>

                            {/* 证据计数 + 预测准确度 */}
                            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", fontSize: 13, marginBottom: t.brier_scores && t.brier_scores.length > 0 ? "12px" : "0" }}>
                              <span>
                                <span style={{ color: "var(--text-3)" }}>证据总计 </span>
                                <span style={{ fontWeight: 600 }}>{t.total_evidence}</span>
                              </span>
                              <span style={{ color: "var(--pos)" }}>支持 {t.supporting_evidence}</span>
                              <span style={{ color: "var(--neg)" }}>反对 {t.opposing_evidence}</span>
                              <span>
                                <span style={{ color: "var(--text-3)" }}>已验证预测 </span>
                                <span style={{ fontWeight: 600 }}>{t.resolved_predictions}/{t.total_predictions}</span>
                              </span>
                              <span>
                                <span style={{ color: "var(--text-3)" }}>准确度 </span>
                                <span style={{ color: accuracyColor, fontWeight: 600 }}>{accuracyLabel}</span>
                              </span>
                              {t.avg_brier_score !== null && (
                                <span>
                                  <span style={{ color: "var(--text-3)" }}>平均 Brier </span>
                                  <span style={{ fontWeight: 600 }}>{t.avg_brier_score.toFixed(4)}</span>
                                </span>
                              )}
                            </div>

                            {/* Brier Score 明细 */}
                            {t.brier_scores && t.brier_scores.length > 0 && (
                              <div style={{ borderTop: "1px solid var(--border, #e0e0e0)", paddingTop: "10px" }}>
                                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: "6px" }}>Brier Score 明细（越低越准）</div>
                                {t.brier_scores.map((b) => (
                                  <div key={b.prediction_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13, padding: "4px 0" }}>
                                    <span style={{ flex: 1, marginRight: "8px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{b.prediction}</span>
                                    <span style={{ color: "var(--text-3)", minWidth: "60px", textAlign: "right" }}>预测 {Math.round(b.probability * 100)}%</span>
                                    <span style={{ color: "var(--text-3)", minWidth: "60px", textAlign: "right" }}>实际 {b.outcome === 1 ? "是" : "否"}</span>
                                    <span style={{ minWidth: "50px", textAlign: "right", fontWeight: 600, color: b.brier_score < 0.15 ? "var(--pos)" : b.brier_score < 0.25 ? "var(--warn)" : "var(--neg)" }}>{b.brier_score.toFixed(4)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </section>
                        );
                      })()}

                      {/* 假设健康监控 */}
                      {result.thesis_tracker?.health && (() => {
                        const h = result.thesis_tracker.health;
                        const healthColor = h.health_label === "Intact" ? "var(--pos)" : h.health_label === "Watching" ? "var(--warn)" : h.health_label === "Broken" ? "var(--neg)" : "var(--text-3)";
                        const statusColor = (s: string) => s === "intact" ? "var(--pos)" : s === "watch" ? "var(--warn)" : s === "broken" ? "var(--neg)" : "var(--text-3)";
                        const statusLabel = (s: string) => s === "intact" ? "正常" : s === "watch" ? "观察" : s === "broken" ? "已破坏" : s === "data_gap" ? "数据缺失" : "未知";
                        const itemTypeLabel: Record<string, string> = { kill_criterion: "退出条件", return_driver: "收益驱动", assumption: "假设", risk: "风险" };
                        return (
                          <section className="card" style={{ marginTop: "12px" }}>
                            <div style={{ fontWeight: 600, marginBottom: "12px" }}>假设健康监控</div>

                            {/* 健康标签大字 */}
                            <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "16px" }}>
                              <span style={{ fontSize: 28, fontWeight: 700, color: healthColor }}>{h.health_label}</span>
                              <span style={{ fontSize: 13, color: "var(--text-3)" }}>
                                {h.intact} 正常 / {h.watch} 观察 / {h.broken} 破坏 / {h.data_gap} 缺失
                              </span>
                            </div>

                            {/* 监控项列表 */}
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {h.items.map((item) => (
                                <div key={item.item_id} style={{ padding: "10px 12px", background: "var(--surface-2, #f5f5f5)", borderRadius: "6px", borderLeft: `3px solid ${statusColor(item.status)}` }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                      <span style={{ fontSize: 13, fontWeight: 600 }}>{item.title}</span>
                                      {itemTypeLabel[item.item_type] && (
                                        <span style={{ fontSize: 11, padding: "1px 6px", borderRadius: "3px", background: "var(--surface, #e0e0e0)", color: "var(--text-3)" }}>
                                          {itemTypeLabel[item.item_type]}
                                        </span>
                                      )}
                                      {item.immediate_kill && (
                                        <span style={{ fontSize: 11, padding: "1px 6px", borderRadius: "3px", background: "rgba(231,68,60,0.1)", color: "var(--neg)" }}>
                                          即时退出
                                        </span>
                                      )}
                                    </div>
                                    <span style={{ fontSize: 12, fontWeight: 600, color: statusColor(item.status) }}>{statusLabel(item.status)}</span>
                                  </div>
                                  <div style={{ display: "flex", gap: "16px", fontSize: 12, color: "var(--text-3)" }}>
                                    <span>
                                      指标 {item.metric ?? "-"}：{item.last_value !== null ? item.last_value : "-"} {item.comparator} {item.threshold !== null ? item.threshold : "-"}
                                    </span>
                                    {item.consecutive_breaches > 0 && (
                                      <span style={{ color: "var(--warn)" }}>连续违规 {item.consecutive_breaches}/{item.confirmation_periods}</span>
                                    )}
                                  </div>
                                  {item.why_matters && (
                                    <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: "4px" }}>{item.why_matters}</div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </section>
                        );
                      })()}
                    </>
                  ) : (
                    <div className="cognition-empty-state" role="status">
                      <div className="cognition-empty-state-title">暂无认知验证数据</div>
                      <div className="cognition-empty-state-detail">
                        个股认知不包含验证步骤，请尝试主题或概念方向。
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4：组合草案 */}
              {activeTab === "portfolio" && (
                <div id="tab-portfolio">
                  {pf && pf.top_funds && pf.top_funds.length > 0 ? (
                    <>
                      {/* 标注 */}
                      <div style={{
                        padding: "8px 12px",
                        background: "rgba(243,156,18,0.08)",
                        border: "1px solid rgba(243,156,18,0.3)",
                        borderRadius: "4px",
                        marginBottom: "12px",
                        fontSize: 12,
                        color: "var(--warn)",
                        fontWeight: 600,
                      }}>
                        研究草案，非交易指令
                      </div>

                      {/* 仓位分配 */}
                      <section className="card" style={{ marginBottom: "12px" }}>
                        <div style={{ fontWeight: 600, marginBottom: "12px" }}>仓位分配</div>
                        <div style={{ display: "flex", gap: "24px", alignItems: "center", flexWrap: "wrap" }}>
                          <DonutChart
                            data={[
                              { name: "认知仓位", value: pf.suggested_weight || 0, color: "#3b82f6" },
                              { name: "防守仓位", value: pf.defense_weight || 0, color: "#10b981" },
                              { name: "现金", value: pf.cash_pct || 0, color: "#e5e7eb" },
                            ]}
                            size={140}
                            innerRadius={35}
                            outerRadius={58}
                            centerLabel="总投资"
                            centerValue={`${(pf.total_invested || 0).toFixed(0)}%`}
                          />
                          <div style={{ flex: 1, minWidth: 200 }}>
                            {/* 仓位权重进度条 */}
                            <div className="portfolio-weight-bar">
                              <div className="portfolio-weight-fill portfolio-weight-cognition" style={{ width: `${pf.suggested_weight}%` }}>
                                认知 {fmt(pf.suggested_weight, "%")}
                              </div>
                              <div className="portfolio-weight-fill portfolio-weight-defense" style={{ width: `${pf.defense_weight}%` }}>
                                防守 {fmt(pf.defense_weight, "%")}
                              </div>
                              <div className="portfolio-weight-fill portfolio-weight-cash" style={{ width: `${pf.cash_pct}%` }}>
                                现金 {fmt(pf.cash_pct, "%")}
                              </div>
                            </div>

                            {/* 配置清单 */}
                            <table className="table-v2" style={{ marginTop: "12px" }}>
                              <thead>
                                <tr>
                                  <th>代码</th>
                                  <th>名称</th>
                                  <th>匹配度</th>
                                </tr>
                              </thead>
                              <tbody>
                                {pf.top_funds.map((f, i) => {
                                  const ff = f as Record<string, unknown>;
                                  return (
                                    <tr key={i} style={{ cursor: "pointer" }} onClick={() => {
                                      const code = String(ff.fund_code ?? "");
                                      if (code) {
                                        setSelectedFundCode(code);
                                        setActiveTab("candidates");
                                      }
                                    }}>
                                      <td>{String(ff.fund_code ?? "")}</td>
                                      <td>{String(ff.fund_name ?? "")}</td>
                                      <td>{fmt(ff.match_pct as number | null, "%")}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* 防守基金 */}
                        {pf.defense_fund && (
                          <div className="defense-fund-box" style={{ marginTop: "12px" }}>
                            <span style={{ color: "var(--text-3)" }}>防守基金：</span>
                            <strong>{(pf.defense_fund as Record<string, unknown>).fund_code as string}</strong>
                            <span> {(pf.defense_fund as Record<string, unknown>).fund_name as string}</span>
                          </div>
                        )}

                        {/* 持仓重叠度 */}
                        {pf.overlap_analysis && pf.overlap_analysis.max_overlap_pct > 0 && (
                          <div style={{ marginTop: "12px", padding: "8px 12px", background: "var(--surface-2, #f5f5f5)", borderRadius: "6px", fontSize: 13 }}>
                            <span style={{ color: "var(--text-3)" }}>持仓重叠度：</span>
                            {pf.overlap_analysis.high_overlap_pairs.length > 0 ? (
                              <span style={{ color: "var(--warn)" }}>
                                最高 {fmt(pf.overlap_analysis.max_overlap_pct, "%")}
                                （{pf.overlap_analysis.high_overlap_pairs.map(p => `${p[0]}<->{p[1]}`).join("、")}高度重叠）
                              </span>
                            ) : (
                              <span style={{ color: "var(--pos)" }}>最高 {fmt(pf.overlap_analysis.max_overlap_pct, "%")}，重叠度低</span>
                            )}
                          </div>
                        )}
                      </section>

                      {/* 风险指标 */}
                      {pf.metrics && (
                        <section className="card" style={{ marginBottom: "12px" }}>
                          <div style={{ fontWeight: 600, marginBottom: "12px" }}>风险指标</div>
                          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                            {pf.metrics.portfolio_pe != null && (
                              <div className="kpi-box" style={{ minWidth: "120px" }}>
                                <div className="kpi-label">组合加权PE</div>
                                <div className="kpi-value">{pf.metrics.portfolio_pe}</div>
                              </div>
                            )}
                            {pf.metrics.portfolio_volatility != null && (
                              <div className="kpi-box" style={{ minWidth: "120px" }}>
                                <div className="kpi-label">年化波动率</div>
                                <div className="kpi-value">{fmt(pf.metrics.portfolio_volatility, "%")}</div>
                              </div>
                            )}
                            {pf.metrics.portfolio_max_drawdown != null && (
                              <div className="kpi-box" style={{ minWidth: "120px" }}>
                                <div className="kpi-label">最大回撤</div>
                                <div className="kpi-value" style={{ color: "var(--neg)" }}>{fmt(pf.metrics.portfolio_max_drawdown, "%")}</div>
                              </div>
                            )}
                          </div>

                          {/* 持仓穿透 */}
                          {pf.metrics.holdings_penetration && pf.metrics.holdings_penetration.length > 0 && (
                            <div style={{ marginTop: "16px" }}>
                              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-2)", marginBottom: "8px" }}>持仓穿透 Top 10</div>
                              <HorizontalBarChart
                                data={pf.metrics.holdings_penetration.slice(0, 10).map(h => ({
                                  name: h.stock_name || h.stock_code,
                                  value: h.weight,
                                }))}
                                height={280}
                                color="#6366f1"
                              />
                            </div>
                          )}

                          {/* 行业暴露 */}
                          {pf.metrics.industry_exposure && pf.metrics.industry_exposure.length > 0 && (
                            <div style={{ marginTop: "16px" }}>
                              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-2)", marginBottom: "8px" }}>行业暴露</div>
                              <HorizontalBarChart
                                data={pf.metrics.industry_exposure.map(ind => ({
                                  name: ind.name,
                                  value: ind.weight,
                                }))}
                                height={200}
                                color="#10b981"
                              />
                            </div>
                          )}
                        </section>
                      )}

                      {/* 导出按钮 */}
                      <button
                        className="btn"
                        disabled={exporting}
                        onClick={() => {
                          setExporting(true);
                          exportCognition(result)
                            .catch(() => {})
                            .finally(() => setExporting(false));
                        }}
                      >
                        {exporting ? "导出中..." : "导出 Excel"}
                      </button>
                    </>
                  ) : (
                    <div className="cognition-empty-state" role="status">
                      <div className="cognition-empty-state-title">没有合格组合</div>
                      <div className="cognition-empty-state-detail">
                        候选为空时不展示可执行组合。请先调整方向或估值容忍度。
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 5：投资备忘录 */}
              {activeTab === "memo" && (
                <div id="tab-memo">
                  {result.investment_memo ? (() => {
                    const memo = result.investment_memo;
                    const decisionConfig: Record<string, { label: string; bg: string; color: string }> = {
                      attractive: { label: "有吸引力", bg: "#dcfce7", color: "#16a34a" },
                      watchlist: { label: "观察名单", bg: "#fef9c3", color: "#ca8a04" },
                      avoid: { label: "暂不参与", bg: "#fee2e2", color: "#dc2626" },
                      needs_more_evidence: { label: "证据不足", bg: "#f3f4f6", color: "#6b7280" },
                    };
                    const dc = decisionConfig[memo.decision] ?? decisionConfig.needs_more_evidence;
                    const scenarioList = [
                      { key: "bear", name: "悲观", data: memo.scenario.bear, color: "#dc2626" },
                      { key: "base", name: "基准", data: memo.scenario.base, color: "#2563eb" },
                      { key: "bull", name: "乐观", data: memo.scenario.bull, color: "#16a34a" },
                    ];
                    const expectedReturn = scenarioList.reduce((acc, s) => acc + (s.data.probability * s.data.return) / 100, 0);
                    const snap = memo.financial_snapshot;

                    return (
                      <>
                        {/* 决策标签 */}
                        <section className="card" style={{ marginBottom: "12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div>
                            <span style={{ fontSize: 13, color: "var(--text-3)" }}>投资决策</span>
                            <span style={{
                              display: "inline-block",
                              marginLeft: "8px",
                              padding: "4px 14px",
                              borderRadius: "4px",
                              background: dc.bg,
                              color: dc.color,
                              fontSize: 14,
                              fontWeight: 600,
                            }}>
                              {dc.label}
                            </span>
                          </div>
                          <span style={{ fontSize: 12, color: "var(--text-3)" }}>
                            生成于 {memo.generated_at}
                          </span>
                        </section>

                        {/* 七段式备忘录 */}
                        {memo.sections.map((section, idx) => (
                          <section key={section.section_id} className="card" style={{ marginBottom: "12px" }}>
                            {/* 段落标题 */}
                            <div style={{ display: "flex", alignItems: "center", marginBottom: "8px" }}>
                              <span style={{
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                width: "22px",
                                height: "22px",
                                borderRadius: "50%",
                                background: "var(--accent, #3b82f6)",
                                color: "#fff",
                                fontSize: 12,
                                fontWeight: 600,
                                marginRight: "8px",
                                flexShrink: 0,
                              }}>
                                {idx + 1}
                              </span>
                              <span style={{ fontWeight: 600, fontSize: 14 }}>{section.title}</span>
                            </div>

                            {/* 核心论点 */}
                            <div style={{
                              padding: "6px 10px",
                              background: "var(--surface-2, #f5f5f5)",
                              borderRadius: "4px",
                              fontSize: 13,
                              color: "var(--text-2)",
                              marginBottom: "8px",
                              borderLeft: "3px solid var(--accent, #3b82f6)",
                            }}>
                              {section.thesis}
                            </div>

                            {/* 关键数字表格 */}
                            {section.key_figures && section.key_figures.length > 0 && (
                              <table className="table-v2" style={{ marginBottom: "8px" }}>
                                <tbody>
                                  {section.key_figures.map((fig, fi) => (
                                    <tr key={fi}>
                                      <td style={{ color: "var(--text-3)", width: "40%" }}>{fig.label}</td>
                                      <td style={{ fontWeight: 600 }}>
                                        {fig.value !== null && fig.value !== "" ? String(fig.value) : "-"}
                                        {fig.unit && <span style={{ color: "var(--text-3)", marginLeft: "2px" }}>{fig.unit}</span>}
                                      </td>
                                      <td style={{ color: "var(--text-3)", fontSize: 11, textAlign: "right" }}>{fig.source}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}

                            {/* 详细内容 */}
                            <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.6, margin: 0 }}>
                              {section.content}
                            </p>
                          </section>
                        ))}

                        {/* 场景分析 */}
                        <section className="card" style={{ marginBottom: "12px" }}>
                          <div style={{ fontWeight: 600, marginBottom: "12px" }}>场景分析</div>
                          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                            {scenarioList.map((s) => (
                              <div key={s.key} style={{
                                flex: "1",
                                minWidth: "140px",
                                padding: "10px 12px",
                                borderRadius: "6px",
                                background: "var(--surface-2, #f5f5f5)",
                                borderLeft: `3px solid ${s.color}`,
                              }}>
                                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: "4px" }}>{s.name}</div>
                                <div style={{ fontSize: 13, fontWeight: 600, color: s.color }}>
                                  {s.data.return > 0 ? "+" : ""}{s.data.return}%
                                </div>
                                <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: "2px" }}>
                                  概率 {s.data.probability}%
                                </div>
                                <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: "4px" }}>
                                  {s.data.thesis}
                                </div>
                              </div>
                            ))}
                          </div>
                          <div style={{ marginTop: "10px", padding: "6px 10px", background: "var(--surface-2, #f5f5f5)", borderRadius: "4px", fontSize: 13 }}>
                            <span style={{ color: "var(--text-3)" }}>期望收益（加权）：</span>
                            <span style={{ fontWeight: 600, color: expectedReturn >= 0 ? "var(--pos)" : "var(--neg)" }}>
                              {expectedReturn >= 0 ? "+" : ""}{expectedReturn.toFixed(1)}%
                            </span>
                          </div>
                        </section>

                        {/* 财务快照 */}
                        <section className="card" style={{ marginBottom: "12px" }}>
                          <div style={{ fontWeight: 600, marginBottom: "12px" }}>财务快照</div>
                          <table className="table-v2">
                            <tbody>
                              <tr>
                                <td style={{ color: "var(--text-3)" }}>顶部基金</td>
                                <td style={{ fontWeight: 600 }}>
                                  {snap.top_fund_code ?? "-"} {snap.top_fund_name ?? ""}
                                </td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--text-3)" }}>匹配度</td>
                                <td style={{ fontWeight: 600 }}>{snap.match_pct != null ? `${snap.match_pct}%` : "-"}</td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--text-3)" }}>加权PE</td>
                                <td style={{ fontWeight: 600 }}>{snap.weighted_pe ?? "-"}</td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--text-3)" }}>加权ROE</td>
                                <td style={{ fontWeight: 600 }}>{snap.weighted_roe != null ? `${snap.weighted_roe}%` : "-"}</td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--text-3)" }}>加权PB</td>
                                <td style={{ fontWeight: 600 }}>{snap.weighted_pb ?? "-"}</td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--text-3)" }}>PEG</td>
                                <td style={{ fontWeight: 600 }}>{snap.peg ?? "-"}</td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--text-3)" }}>估值分位</td>
                                <td style={{ fontWeight: 600 }}>{snap.val_pct != null ? `${snap.val_pct}%` : "-"}</td>
                              </tr>
                            </tbody>
                          </table>
                        </section>
                      </>
                    );
                  })() : (
                    <div className="cognition-empty-state" role="status">
                      <div className="cognition-empty-state-title">暂无投资备忘录</div>
                      <div className="cognition-empty-state-detail">
                        个股认知不生成投资备忘录，请尝试主题或概念方向。
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 右侧详情栏 */}
            <div style={{ width: "320px", flexShrink: 0, position: "sticky", top: "12px" }}>
              <FundDetailPanel fund={selectedFund} />

              {/* 证据溯源：展示冻结的证据源、bundle ID、数据缺口 */}
              {selectedFund && evidencePacket && (
                <section className="card" style={{ marginTop: "12px" }}>
                  <div style={{ fontWeight: 600, marginBottom: "8px" }}>证据溯源</div>

                  {/* 冻结的 bundle ID */}
                  {evidencePacket.evidence_bundle && (
                    <div style={{
                      padding: "6px 10px",
                      background: "var(--surface-2, #f5f5f5)",
                      borderRadius: "4px",
                      fontSize: 12,
                      marginBottom: "8px",
                      wordBreak: "break-all",
                    }}>
                      <span style={{ color: "var(--text-3)" }}>Bundle ID：</span>
                      <span style={{ fontFamily: "monospace", fontWeight: 600 }}>
                        {evidencePacket.evidence_bundle.bundle_id}
                      </span>
                      <span style={{ color: "var(--text-3)", marginLeft: "8px" }}>
                        ({evidencePacket.evidence_bundle.source_ids.length} 个证据源)
                      </span>
                    </div>
                  )}

                  {/* 证据源列表 */}
                  {evidencePacket.evidence_sources.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {evidencePacket.evidence_sources.map((src) => (
                        <div
                          key={src.source_id}
                          style={{
                            padding: "6px 8px",
                            background: "var(--surface-2, #f5f5f5)",
                            borderRadius: "4px",
                            fontSize: 12,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "2px" }}>
                            <span
                              style={{
                                display: "inline-block",
                                padding: "1px 6px",
                                borderRadius: "3px",
                                background: "var(--accent-soft, rgba(59,130,246,0.1))",
                                color: "var(--accent, #3b82f6)",
                                fontSize: 10,
                                fontWeight: 600,
                                whiteSpace: "nowrap",
                              }}
                            >
                              {src.kind}
                            </span>
                            <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {src.title}
                            </span>
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-3)", fontSize: 11 }}>
                            <span>{src.publisher}</span>
                            <span style={{ fontFamily: "monospace" }}>{src.content_hash}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 数据缺口说明 */}
                  {evidencePacket.data_quality_notes.length > 0 && (
                    <div style={{ marginTop: "8px" }}>
                      <div style={{ fontSize: 12, color: "var(--warn)", fontWeight: 600, marginBottom: "4px" }}>
                        数据缺口
                      </div>
                      {evidencePacket.data_quality_notes.map((note, i) => (
                        <div key={i} style={{ fontSize: 12, color: "var(--text-2)", padding: "2px 0" }}>
                          - {note}
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {monitorFundCode && (
                <div style={{ marginTop: "12px" }}>
                  <MonitorPanel
                    fundCode={monitorFundCode}
                    overview={monitorData}
                    loading={monitorLoading}
                    error={monitorError}
                  />
                </div>
              )}
              {/* 监控开关 */}
              {selectedFund && !monitorFundCode && (
                <button
                  type="button"
                  className="btn btn-sm"
                  style={{ marginTop: "12px", width: "100%" }}
                  onClick={() => setMonitorFundCode(selectedFund.fund_code)}
                >
                  查看监控面板
                </button>
              )}
              {monitorFundCode && (
                <button
                  type="button"
                  className="btn btn-sm"
                  style={{ marginTop: "12px", width: "100%" }}
                  onClick={() => setMonitorFundCode(null)}
                >
                  关闭监控
                </button>
              )}
            </div>
          </div>
        </div>
      </CognitionErrorBoundary>
    );
  }

  return null;
}
