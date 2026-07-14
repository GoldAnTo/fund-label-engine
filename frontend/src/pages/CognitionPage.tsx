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
import { DonutChart, HorizontalBarChart, ScenarioChart, ComparisonBar } from "../charts";
import {
  ValuationQuad,
  FundDetailPanel,
  useScrollSpy,
  EvidenceSummary,
  MonitorPanel,
  type EvidenceItem,
} from "../components/CognitionComponents";
import {
  Card,
  CardHeader,
  CardBody,
  Badge,
  ProgressBar,
  Stat,
  Table,
  Th,
  Td,
  TabBar,
  SectionTitle,
  Loading,
  ErrorBox,
  EmptyState,
} from "../components/ui";

// === 标签映射 ===
const CERTAINTY_LABEL: Record<string, string> = { high: "高确定性", medium: "中确定性", low: "低确定性" };
const GAP_LABEL: Record<string, string> = { positive: "正预期差", neutral: "中性", negative: "负预期差", unknown: "数据不足" };
const GAP_VARIANT: Record<string, "pos" | "warn" | "neg" | "neutral"> = {
  positive: "pos", neutral: "warn", negative: "neg", unknown: "neutral",
};
const TREND_LABEL: Record<string, string> = { increasing: "加仓", decreasing: "减仓", stable: "持平", insufficient_data: "数据不足" };
const CONVICTION_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };
const RISK_LABEL: Record<string, string> = { conservative: "保守", balanced: "适中", aggressive: "进取" };
const HORIZON_LABEL: Record<string, string> = { short: "短期", medium: "中期", long: "长期" };

// === Pipeline 标签 ===
const PIPELINE_STAGE_LABELS: Record<string, string> = {
  screener: "筛选", cognition: "认知分析", ic_review: "投决会审查",
  memo: "投资备忘录", portfolio: "组合构建", monitoring: "投后监控",
};
const PIPELINE_STAGE_ORDER = ["screener", "cognition", "ic_review", "memo", "portfolio", "monitoring"];
const PIPELINE_STATUS_VARIANT: Record<string, "pos" | "neg" | "warn" | "neutral"> = {
  completed: "pos", failed: "neg", running: "warn", skipped: "neutral", pending: "neutral",
};
const PIPELINE_STATUS_LABEL: Record<string, string> = {
  completed: "完成", failed: "失败", running: "运行中", skipped: "跳过", pending: "等待",
};

// === 投资决策配置 ===
const DECISION_CONFIG: Record<string, { label: string; variant: "pos" | "warn" | "neg" | "neutral" }> = {
  attractive: { label: "有吸引力", variant: "pos" },
  watchlist: { label: "观察名单", variant: "warn" },
  avoid: { label: "暂不参与", variant: "neg" },
  needs_more_evidence: { label: "证据不足", variant: "neutral" },
};

// === 工具函数 ===
function fmt(v: number | string | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "-";
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return String(v);
  return Number.isInteger(n) ? `${n}${suffix}` : `${n.toFixed(1)}${suffix}`;
}

// === Tab 配置 ===
type TabId = "candidates" | "chain" | "validation" | "portfolio" | "memo";
const TAB_LIST: { id: TabId; label: string }[] = [
  { id: "candidates", label: "基金候选" },
  { id: "chain", label: "产业链分析" },
  { id: "validation", label: "认知验证" },
  { id: "portfolio", label: "组合草案" },
  { id: "memo", label: "投资备忘录" },
];

// === 错误边界 ===
class CognitionErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
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
        <Card className="m-5 border-neg">
          <div className="font-semibold text-neg mb-2">渲染出错</div>
          <pre className="text-xs text-text-2 whitespace-pre-wrap m-0">
            {this.state.error.message}{"\n\n"}{this.state.error.stack}
          </pre>
        </Card>
      );
    }
    return this.props.children;
  }
}

export default function CognitionPage() {
  // === 状态 ===
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

  const [searchKeyword, setSearchKeyword] = useState("");
  const [conceptResults, setConceptResults] = useState<ConceptBoard[]>([]);
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [beliefNote, setBeliefNote] = useState("");

  const [activeTab, setActiveTab] = useState<TabId>("candidates");
  const [selectedFundCode, setSelectedFundCode] = useState<string | null>(null);
  const [monitorFundCode, setMonitorFundCode] = useState<string | null>(null);
  const [monitorData, setMonitorData] = useState<MonitorOverview | null>(null);
  const [monitorLoading, setMonitorLoading] = useState(false);
  const [monitorError, setMonitorError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [inboxExpanded, setInboxExpanded] = useState(false);

  // ScrollSpy hooks 必须在条件 return 之前
  useScrollSpy(TAB_LIST.map((t) => `tab-${t.id}`));

  // === Effects ===
  useEffect(() => {
    fetchThemes().then((r) => setThemes(r.themes)).catch(() => {});
  }, []);

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
      (data) => { if (!cancelled) { setMonitorData(data); setMonitorLoading(false); } },
      (err) => { if (!cancelled) { setMonitorError(err instanceof Error ? err.message : String(err)); setMonitorLoading(false); } }
    );
    return () => { cancelled = true; };
  }, [monitorFundCode]);

  // === 动作 ===
  const triggerAnalysis = (dirText: string, run: () => Promise<CognitionResponse>) => {
    setLoading(true);
    setError(null);
    run().then((r) => {
      setResult(r);
      setStep(2);
      setDirection(dirText);
      setActiveTab("candidates");
      setSelectedFundCode(null);
      setMonitorFundCode(null);
      setPipelineResult(null);
      runPipeline(dirText).then(setPipelineResult).catch(() => {});
    }).catch(() => setError("分析失败，请重试"))
      .finally(() => setLoading(false));
  };

  const runThemeCognition = () => {
    if (!direction.trim()) return;
    triggerAnalysis(direction.trim(), () =>
      postCognition(direction.trim(), undefined, conviction, riskTolerance, timeHorizon, beliefNote || undefined)
    );
  };

  const pickConcept = (concept: ConceptBoard) => {
    setSearchKeyword("");
    setShowDropdown(false);
    triggerAnalysis(concept.name, () =>
      postConceptCognition(concept.code, concept.name, conviction, riskTolerance, timeHorizon, beliefNote || undefined)
    );
  };

  const pickStock = (stock: StockSearchResult) => {
    setSearchKeyword("");
    setShowDropdown(false);
    triggerAnalysis(`${stock.stock_name}（个股认知）`, () =>
      postStockCognition(stock.stock_code, stock.stock_name, conviction, riskTolerance, timeHorizon, beliefNote || undefined).then((r) => r as CognitionResponse)
    );
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
        <h2 className="text-xl font-bold mb-1">你相信什么？</h2>
        <p className="text-text-3 mb-6 text-sm">
          输入方向关键词，或选择预设主题，系统帮你从认知推导到基金配置。
        </p>

        {/* 搜索框 */}
        <div className="relative mb-4">
          <div className="flex gap-2">
            <input
              type="search"
              className="flex-1 px-3 py-2 text-sm bg-surface border border-border rounded-lg focus:outline-none focus:border-accent"
              value={searchKeyword}
              onChange={(e) => { setSearchKeyword(e.target.value); setShowDropdown(true); }}
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
              className="px-4 py-2 text-sm bg-accent text-white border border-accent rounded-lg hover:opacity-90"
              onClick={() => { if (searchKeyword.trim()) { setDirection(searchKeyword.trim()); setShowDropdown(false); } }}
            >
              填入
            </button>
          </div>

          {showDropdown && searchKeyword.trim() && (
            <div className="absolute top-full left-0 right-0 z-50 bg-surface border border-border border-t-0 rounded-b-lg shadow-lg max-h-96 overflow-y-auto">
              {searchLoading && <div className="p-3 text-text-3 text-xs">搜索中…</div>}

              {conceptResults.length > 0 && (
                <div className="border-b border-border">
                  <div className="px-3 py-1.5 text-[11px] text-text-3 bg-surface-2">概念板块</div>
                  {conceptResults.slice(0, 5).map((c) => (
                    <button
                      key={c.code}
                      type="button"
                      onClick={() => pickConcept(c)}
                      className="block w-full text-left px-3 py-2 hover:bg-accent-soft border-b border-border last:border-b-0"
                    >
                      <div className="font-semibold text-sm">{c.name}</div>
                      <div className="text-xs text-text-2">{c.stock_count} 只成分股</div>
                    </button>
                  ))}
                </div>
              )}

              {stockResults.length > 0 && (
                <div>
                  <div className="px-3 py-1.5 text-[11px] text-text-3 bg-surface-2">个股</div>
                  {stockResults.slice(0, 5).map((s) => (
                    <button
                      key={s.stock_code}
                      type="button"
                      onClick={() => pickStock(s)}
                      className="block w-full text-left px-3 py-2 hover:bg-accent-soft border-b border-border last:border-b-0"
                    >
                      <div className="font-semibold text-sm">
                        {s.stock_name}
                        <span className="text-xs text-text-3 ml-2">{s.stock_code}</span>
                      </div>
                      <div className="text-xs text-text-2">
                        {s.fund_count} 只基金持有
                        {s.pe != null && ` · PE ${s.pe}`}
                        {s.val_pct != null && ` · 分位 ${s.val_pct}%`}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {!searchLoading && conceptResults.length === 0 && stockResults.length === 0 && (
                <button
                  type="button"
                  className="block w-full text-left p-3 text-text-3 text-xs hover:bg-accent-soft"
                  onClick={() => { setDirection(searchKeyword.trim()); setShowDropdown(false); }}
                >
                  未找到匹配，将作为自定义方向分析：{searchKeyword.trim()}
                </button>
              )}
            </div>
          )}
        </div>

        {/* 当前方向输入 */}
        <div className="mb-4">
          <label htmlFor="cognition-direction" className="block text-xs text-text-3 mb-2">分析方向</label>
          <input
            id="cognition-direction"
            type="text"
            className="w-full px-3 py-2 text-sm bg-surface border border-border rounded-lg focus:outline-none focus:border-accent"
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && direction.trim() && runThemeCognition()}
            placeholder="例如：AI、消费、创新药、新能源..."
            aria-label="分析方向"
          />
        </div>

        {/* 预设主题 */}
        <div className="mb-4">
          <div className="text-xs text-text-3 mb-2">快速选择</div>
          <div className="flex flex-wrap gap-2">
            {themes.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setDirection(t.key)}
                className={`px-3 py-1 rounded text-xs border ${
                  direction === t.key
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-border bg-transparent text-text-2 hover:border-accent"
                }`}
              >
                {t.name}
              </button>
            ))}
          </div>
        </div>

        {/* 高级选项 */}
        <div className="mb-4">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-xs text-text-3 hover:text-accent"
          >
            {showAdvanced ? "收起高级选项" : "展开高级选项"}
          </button>

          {showAdvanced && (
            <div className="mt-3 p-4 bg-surface-2 rounded-lg space-y-3">
              <div>
                <div className="text-xs text-text-3 mb-2">信心强度</div>
                <div className="flex gap-2">
                  {["low", "medium", "high"].map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setConviction(c)}
                      className={`px-3 py-1 rounded text-xs border ${
                        conviction === c
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-border bg-surface text-text-2 hover:border-accent"
                      }`}
                    >
                      {CONVICTION_LABEL[c]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-xs text-text-3 mb-2">风险偏好</div>
                <div className="flex gap-2">
                  {["conservative", "balanced", "aggressive"].map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setRiskTolerance(r)}
                      className={`px-3 py-1 rounded text-xs border ${
                        riskTolerance === r
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-border bg-surface text-text-2 hover:border-accent"
                      }`}
                    >
                      {RISK_LABEL[r]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-xs text-text-3 mb-2">投资周期</div>
                <div className="flex gap-2">
                  {["short", "medium", "long"].map((h) => (
                    <button
                      key={h}
                      type="button"
                      onClick={() => setTimeHorizon(h)}
                      className={`px-3 py-1 rounded text-xs border ${
                        timeHorizon === h
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-border bg-surface text-text-2 hover:border-accent"
                      }`}
                    >
                      {HORIZON_LABEL[h]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-xs text-text-3 mb-2">我的观点（可选，1000 字内）</div>
                <textarea
                  className="w-full min-h-[60px] px-3 py-2 text-sm bg-surface border border-border rounded-lg font-sans resize-y focus:outline-none focus:border-accent"
                  value={beliefNote}
                  onChange={(e) => setBeliefNote(e.target.value.slice(0, 1000))}
                  placeholder="例如：受益于国产替代 + 下游需求扩张 + 估值合理..."
                />
              </div>
            </div>
          )}
        </div>

        {error && <ErrorBox message={error} />}

        <button
          type="button"
          disabled={!direction.trim() || loading}
          onClick={runThemeCognition}
          className="w-full px-4 py-3 text-sm font-semibold bg-accent text-white border border-accent rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "分析中…" : "开始分析"}
        </button>

        {loading && <Loading text="正在分析方向并推导配置…" />}
      </div>
    );
  }

  // === Step 2：结果页 ===
  if (step === 2 && result) {
    const chain: ChainLink[] = result.step2_chain ?? [];
    const gap = result.step3_expectation_gap;
    const validation = result.step5_validation ?? null;
    const pf = result.step5_portfolio;
    const fundMatches = result.step4_fund_matches ?? [];
    const gatedOut = result.gated_out_funds ?? [];
    const screenSnapshot: ScreenSnapshot | null = result.screen_snapshot ?? null;
    const inbox: InboxSnapshot | null = result.inbox ?? null;
    const asOfDate = (result as { step1_judgment?: { as_of_date?: string | null } }).step1_judgment?.as_of_date ?? null;

    const selectedFund = selectedFundCode
      ? fundMatches.find((f) => f.fund_code === selectedFundCode) ?? null
      : null;
    const evidencePacket: FundEvidencePacket | null = selectedFundCode
      ? result.evidence_packets?.find((p) => p.fund_code === selectedFundCode) ?? null
      : null;

    // 顶部摘要
    const gapPositive = gap?.positive?.length ?? 0;
    const gapNegative = gap?.negative?.length ?? 0;
    const gapNeutral = gap?.neutral?.length ?? 0;

    // 证据汇总
    const evidenceItems: EvidenceItem[] = [];
    if (validation) {
      for (const ev of validation.supporting_evidence || []) {
        evidenceItems.push({ category: "support", title: ev.claim || ev.source, detail: [ev.context, ev.source].filter(Boolean).join(" - ") });
      }
      for (const ev of validation.opposing_evidence || []) {
        evidenceItems.push({ category: "oppose", title: ev.claim || ev.source, detail: [ev.context, ev.source].filter(Boolean).join(" - ") });
      }
    }
    if (gap) {
      if (gap.positive && gap.positive.length > 0) {
        evidenceItems.push({ category: "support", title: `正向预期差（${gap.positive.length} 条）`, detail: gap.positive.map((c) => c.link_name).slice(0, 3).join("、") });
      }
      if (gap.negative && gap.negative.length > 0) {
        evidenceItems.push({ category: "oppose", title: `负向预期差（${gap.negative.length} 条）`, detail: gap.negative.map((c) => c.link_name).slice(0, 3).join("、") });
      }
    }

    // === KPI 顶部指标 ===
    const kpiMetrics = {
      match: fundMatches.length,
      passed: screenSnapshot?.passed_funds ?? fundMatches.length,
      gated: gatedOut.length,
      gap: 0,
    };



    return (
      <CognitionErrorBoundary>
        <div className="main space-y-4">
          {/* === 第 1 层：决策摘要 === */}
          <Card className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* IC Review */}
              {result.ic_review ? (() => {
                const ic = result.ic_review!;
                const isPass = ic.verdict === "pass";
                const scorePct = Math.min(100, ic.gate_score);
                return (
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-3 uppercase tracking-wide">投决会</span>
                      {ic.is_override && <Badge variant="warn">已覆盖</Badge>}
                    </div>
                    <span className={`text-2xl font-bold ${isPass ? "text-pos" : "text-neg"}`}>
                      {isPass ? "PASS" : "FAIL"}
                    </span>
                    <ProgressBar value={scorePct} variant={isPass ? "pos" : "neg"} label="Gate Score" />
                    <span className="text-[11px] text-text-3">通过线 {ic.cutoff.toFixed(0)} 分</span>
                  </div>
                );
              })() : (
                <Stat label="投决会" value="未触发" />
              )}

              {/* 假设健康 */}
              {result.thesis_tracker?.health ? (() => {
                const h = result.thesis_tracker.health!;
                const variant = h.health_label === "Intact" ? "pos" : h.health_label === "Watching" ? "warn" : h.health_label === "Broken" ? "neg" : "neutral";
                return (
                  <div className="flex flex-col gap-2">
                    <span className="text-xs text-text-3 uppercase tracking-wide">假设健康</span>
                    <Badge variant={variant}>{h.health_label}</Badge>
                    <span className="text-[11px] text-text-3">
                      正常 {h.intact} · 观察 {h.watch} · 破坏 {h.broken}
                    </span>
                  </div>
                );
              })() : (
                <Stat label="假设健康" value="—" />
              )}

              {/* Inbox */}
              <div className="flex flex-col gap-2">
                <span className="text-xs text-text-3 uppercase tracking-wide">Inbox 决策队列</span>
                {inbox ? (
                  <div className="flex gap-2 items-center">
                    {inbox.high_severity > 0 && <Badge variant="neg">高 {inbox.high_severity}</Badge>}
                    {inbox.medium_severity > 0 && <Badge variant="warn">中 {inbox.medium_severity}</Badge>}
                    {inbox.low_severity > 0 && <Badge variant="neutral">低 {inbox.low_severity}</Badge>}
                    {inbox.open_items === 0 && <span className="text-sm text-text-3">无待办</span>}
                  </div>
                ) : (
                  <span className="text-sm text-text-3">无</span>
                )}
                {inbox && <span className="text-[11px] text-text-3">共 {inbox.open_items} 项</span>}
              </div>

              {/* Pipeline */}
              {pipelineResult ? (
                <div className="flex flex-col gap-2">
                  <span className="text-xs text-text-3 uppercase tracking-wide">Pipeline</span>
                  <div className="flex gap-1 flex-wrap">
                    {PIPELINE_STAGE_ORDER.map((stage) => {
                      const s = pipelineResult.run.steps.find((x) => x.stage === stage);
                      const status = s?.status ?? "pending";
                      return (
                        <Badge key={stage} variant={PIPELINE_STATUS_VARIANT[status] ?? "neutral"}>
                          {PIPELINE_STAGE_LABELS[stage]}
                        </Badge>
                      );
                    })}
                  </div>
                  {pipelineResult.partial && <Badge variant="warn">部分完成</Badge>}
                </div>
              ) : (
                <Stat label="Pipeline" value="—" />
              )}
            </div>
          </Card>

          {/* 摘要条 */}
          <Card className="px-4 py-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-text-3">方向</span>
              <strong className="font-semibold">{result.direction}</strong>
              <span className="text-text-3">·</span>
              <span className="text-text-3">信心</span>
              <Badge variant="accent">{CONVICTION_LABEL[result.conviction] ?? "中"}</Badge>
              <span className="text-text-3">·</span>
              <span className="text-text-3">匹配</span>
              <strong>{fundMatches.length}</strong>
              <span className="text-text-3">只</span>
              {gatedOut.length > 0 && (
                <>
                  <span className="text-text-3">·</span>
                  <span className="text-text-3">拦截</span>
                  <strong className="text-neg">{gatedOut.length}</strong>
                </>
              )}
              {asOfDate && (
                <>
                  <span className="text-text-3">·</span>
                  <span className="text-text-3">数据日期 {asOfDate}</span>
                </>
              )}
            </div>
            <button
              type="button"
              onClick={reset}
              className="px-4 py-2 text-sm text-accent border border-accent/30 rounded-lg hover:bg-accent-soft"
            >
              重新分析
            </button>
          </Card>

          {error && <ErrorBox message={error} />}

          {/* Inbox 展开区域 */}
          {inbox && inbox.open_items > 0 && (
            <Card>
              <button
                type="button"
                onClick={() => setInboxExpanded(!inboxExpanded)}
                className="w-full flex items-center gap-3 text-left"
              >
                <SectionTitle>Inbox 决策队列</SectionTitle>
                <div className="flex gap-2">
                  {inbox.high_severity > 0 && <Badge variant="neg">高 {inbox.high_severity}</Badge>}
                  {inbox.medium_severity > 0 && <Badge variant="warn">中 {inbox.medium_severity}</Badge>}
                  {inbox.low_severity > 0 && <Badge variant="neutral">低 {inbox.low_severity}</Badge>}
                </div>
                <span className="text-xs text-text-3 ml-auto">共 {inbox.open_items} 项 · {inboxExpanded ? "收起" : "展开"}</span>
              </button>
              {inboxExpanded && (
                <div className="mt-3 space-y-2">
                  {inbox.items.map((item: AttentionItem) => (
                    <div key={item.item_id} className="p-3 bg-surface-2 rounded border-l-4 border-border">
                      <div className="flex justify-between items-start gap-2 mb-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-semibold">{item.title}</span>
                          <Badge variant={item.severity === "high" ? "neg" : item.severity === "medium" ? "warn" : "neutral"}>
                            {item.severity === "high" ? "高" : item.severity === "medium" ? "中" : "低"}
                          </Badge>
                          <span className="text-xs text-text-3 bg-surface px-2 py-0.5 rounded">{item.source_type_display}</span>
                        </div>
                        {item.fund_code && <span className="text-xs text-text-3 font-mono">{item.fund_code}</span>}
                      </div>
                      <p className="text-xs text-text-2 leading-relaxed">{item.body}</p>
                      {item.response_set.length > 0 && (
                        <div className="flex gap-1 flex-wrap mt-2">
                          {item.response_set.map((r) => (
                            <span key={r} className="text-[11px] px-2 py-0.5 border border-border rounded text-text-3">{r}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* === 第 2 层：Tab 切换 === */}
          <TabBar
            tabs={TAB_LIST.map((t) => ({
              id: t.id,
              label: t.id === "candidates" && fundMatches.length > 0 ? `${t.label} (${fundMatches.length})` : t.label,
            }))}
            active={activeTab}
            onChange={(id) => setActiveTab(id as TabId)}
          />

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
            {/* === 主内容区 === */}
            <div className="lg:col-span-8 space-y-4">
              {/* Tab 1：基金候选 */}
              {activeTab === "candidates" && (
                <div id="tab-candidates" className="space-y-4">
                  {/* KPI 顶卡 */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Stat label="匹配基金" value={kpiMetrics.match} unit="只" variant="accent" />
                    <Stat label="通过筛选" value={kpiMetrics.passed} unit="只" variant="pos" />
                    <Stat label="门禁拦截" value={kpiMetrics.gated} unit="只" variant="neg" />
                    <Stat label="证据缺口" value={kpiMetrics.gap} unit="条" />
                  </div>

                  {/* 匹配度横向条形图 */}
                  {fundMatches.length > 0 && (
                    <Card>
                      <CardHeader title="匹配度分布" subtitle={`共 ${fundMatches.length} 只基金`} />
                      <CardBody>
                        <HorizontalBarChart
                          data={fundMatches.slice(0, 12).map((f) => ({
                            name: f.fund_name?.length > 16 ? `${f.fund_name.slice(0, 16)}…` : (f.fund_name ?? f.fund_code),
                            value: Number(f.match_pct ?? 0),
                          }))}
                          unit="%"
                          height={Math.max(160, fundMatches.length * 28)}
                          color="#3b82f6"
                        />
                      </CardBody>
                    </Card>
                  )}

                  {/* 基金表格 */}
                  {fundMatches.length === 0 ? (
                    <EmptyState message="当前没有合格研究候选。所有匹配基金都未通过估值门禁或数据缺失，建议调整方向或估值容忍度。" />
                  ) : (
                    <Card>
                      <CardHeader title="匹配基金" />
                      <CardBody className="p-0">
                        <Table>
                          <thead>
                            <tr>
                              <Th>代码</Th>
                              <Th>名称</Th>
                              <Th>匹配度</Th>
                              <Th>PE</Th>
                              <Th>估值分位</Th>
                              <Th>门禁</Th>
                              <Th>趋势</Th>
                              <Th>排名分</Th>
                            </tr>
                          </thead>
                          <tbody>
                            {fundMatches.map((f) => {
                              const v = (f.valuation ?? {}) as Record<string, unknown>;
                              const isSelected = selectedFundCode === f.fund_code;
                              const screenResult = screenSnapshot?.results.find((r) => r.fund_code === f.fund_code);
                              return (
                                <tr
                                  key={f.fund_code}
                                  onClick={() => setSelectedFundCode(f.fund_code)}
                                  className={`cursor-pointer hover:bg-surface-2 ${isSelected ? "bg-accent-soft" : ""}`}
                                >
                                  <Td className="font-mono text-xs">{f.fund_code}</Td>
                                  <Td>{f.fund_name}</Td>
                                  <Td className="font-semibold text-accent">{fmt(f.match_pct, "%")}</Td>
                                  <Td>{fmt(v.weighted_pe as number | null)}</Td>
                                  <Td>{fmt(v.weighted_val_pct as number | null, "%")}</Td>
                                  <Td>
                                    {f.gate ? (
                                      f.gate.passed ? (
                                        <Badge variant="pos">通过</Badge>
                                      ) : (
                                        <span title={f.gate.violations.join("; ")}>
                                          <Badge variant="neg">拦截</Badge>
                                        </span>
                                      )
                                    ) : (
                                      <span className="text-text-3">-</span>
                                    )}
                                  </Td>
                                  <Td className="text-xs">{TREND_LABEL[f.trend?.trend] ?? f.trend?.trend ?? "-"}</Td>
                                  <Td className="font-semibold text-accent">
                                    {screenResult?.passed ? fmt(screenResult.rank_score) : "-"}
                                  </Td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </Table>
                      </CardBody>
                    </Card>
                  )}

                  {/* 估值四维 */}
                  {chain.length > 0 && fundMatches.length > 0 && gap && (
                    <Card>
                      <CardHeader title="估值四维" subtitle="成长空间 / 护城河 / 竞争格局 / 经营绩效" />
                      <CardBody>
                        <ValuationQuad expectationGap={gap} chain={chain} fundMatches={fundMatches} />
                      </CardBody>
                    </Card>
                  )}

                  {/* 门禁拦截 */}
                  {gatedOut.length > 0 && (
                    <details className="bg-surface border border-border rounded-lg p-4">
                      <summary className="cursor-pointer font-semibold text-text-2">
                        被门禁拦截的基金（{gatedOut.length}）
                      </summary>
                      <Table className="mt-3">
                        <thead>
                          <tr>
                            <Th>代码</Th><Th>名称</Th><Th>匹配度</Th><Th>拦截原因</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {gatedOut.map((f) => (
                            <tr key={f.fund_code}>
                              <Td className="font-mono text-xs">{f.fund_code}</Td>
                              <Td>{f.fund_name}</Td>
                              <Td>{fmt(f.match_pct, "%")}</Td>
                              <Td className="text-neg text-xs">{f.gate.violations.join("; ")}</Td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </details>
                  )}

                  {/* 筛选快照 */}
                  {screenSnapshot && (
                    <details className="bg-surface border border-border rounded-lg p-4">
                      <summary className="cursor-pointer font-semibold text-text-2">
                        筛选详情（{screenSnapshot.passed_funds} 通过 / {screenSnapshot.failed_funds} 未通过 / 共 {screenSnapshot.total_funds}）
                      </summary>
                      <div className="flex flex-wrap gap-4 mt-3 mb-3 text-xs text-text-3">
                        <span>筛选准则 <strong className="text-text">{screenSnapshot.screen_criteria_count}</strong> 条</span>
                        {screenSnapshot.ranking_blend.length > 0 && (
                          <span>排名指标 <strong className="text-text">{screenSnapshot.ranking_blend.length}</strong> 个</span>
                        )}
                        <span>生成于 {screenSnapshot.created_at}</span>
                      </div>
                      {screenSnapshot.results.filter((r) => !r.passed).length > 0 && (
                        <div className="mt-3">
                          <div className="text-sm font-semibold mb-2">未通过基金及失败原因</div>
                          <Table>
                            <thead>
                              <tr><Th>代码</Th><Th>名称</Th><Th>失败准则</Th></tr>
                            </thead>
                            <tbody>
                              {screenSnapshot.results.filter((r) => !r.passed).map((r) => (
                                <tr key={r.fund_code}>
                                  <Td className="font-mono text-xs">{r.fund_code}</Td>
                                  <Td>{r.fund_name}</Td>
                                  <Td className="text-xs text-neg">
                                    {r.fail_reasons.map((fr) => `${fr.metric} ${fr.operator} ${fr.threshold}（观测值 ${fr.observed ?? "数据不足"}）`).join("；")}
                                  </Td>
                                </tr>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      )}
                    </details>
                  )}
                </div>
              )}

              {/* Tab 2：产业链分析 */}
              {activeTab === "chain" && (
                <div id="tab-chain" className="space-y-4">
                  {/* 预期差饼图 */}
                  {gap && (
                    <Card>
                      <CardHeader title="预期差分布" subtitle="基于产业链环节" />
                      <CardBody>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                          <DonutChart
                            data={[
                              { name: "正预期差", value: gapPositive, color: "#16a34a" },
                              { name: "中性", value: gapNeutral, color: "#ca8a04" },
                              { name: "负预期差", value: gapNegative, color: "#dc2626" },
                            ].filter((d) => d.value > 0)}
                            size={180}
                            innerRadius={45}
                            outerRadius={70}
                            centerLabel="环节数"
                            centerValue={`${gapPositive + gapNeutral + gapNegative}`}
                          />
                          <div className="space-y-2 text-sm">
                            <div className="flex items-center gap-2">
                              <span className="w-3 h-3 bg-pos rounded" />
                              <span className="flex-1 text-text-2">正预期差</span>
                              <strong>{gapPositive}</strong>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="w-3 h-3 bg-warn rounded" />
                              <span className="flex-1 text-text-2">中性</span>
                              <strong>{gapNeutral}</strong>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="w-3 h-3 bg-neg rounded" />
                              <span className="flex-1 text-text-2">负预期差</span>
                              <strong>{gapNegative}</strong>
                            </div>
                            {gap.summary && <p className="text-xs text-text-2 leading-relaxed mt-3">{gap.summary}</p>}
                            {gap.best_link && (
                              <div className="text-xs mt-2 pt-2 border-t border-border">
                                <span className="text-text-3">最优环节：</span>
                                <strong>{gap.best_link.link_name}</strong>
                                <span className="text-text-3 ml-2">评分 {fmt(gap.best_link.score)}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </CardBody>
                    </Card>
                  )}

                  {/* 产业链环节表 */}
                  {chain.length === 0 ? (
                    <EmptyState message="暂无产业链数据。个股认知不包含产业链分析，请尝试主题或概念方向。" />
                  ) : (
                    <Card>
                      <CardHeader title="产业链环节" />
                      <CardBody className="p-0">
                        <Table>
                          <thead>
                            <tr>
                              <Th>环节</Th><Th>确定性</Th><Th>PE</Th><Th>预期差</Th><Th>评分</Th>
                            </tr>
                          </thead>
                          <tbody>
                            {chain.map((link) => (
                              <tr key={link.link_name}>
                                <Td className="font-semibold">{link.link_name}</Td>
                                <Td>{CERTAINTY_LABEL[link.certainty] ?? link.certainty}</Td>
                                <Td>{fmt(link.pe)}</Td>
                                <Td>
                                  <Badge variant={GAP_VARIANT[link.expectation_gap] ?? "neutral"}>
                                    {GAP_LABEL[link.expectation_gap] ?? link.expectation_gap}
                                  </Badge>
                                </Td>
                                <Td className="font-semibold">{fmt(link.score)}</Td>
                              </tr>
                            ))}
                          </tbody>
                        </Table>
                      </CardBody>
                    </Card>
                  )}
                </div>
              )}

              {/* Tab 3：认知验证 */}
              {activeTab === "validation" && (
                <div id="tab-validation" className="space-y-4">
                  {!validation ? (
                    <EmptyState message="暂无认知验证数据。个股认知不包含验证步骤，请尝试主题或概念方向。" />
                  ) : (
                    <>
                      {/* 裁决结论 */}
                      <Card>
                        <div className="flex justify-between items-center flex-wrap gap-2">
                          <SectionTitle>裁决结论</SectionTitle>
                          <Badge variant={validation.verdict.includes("有效") ? "pos" : validation.verdict.includes("分歧") ? "warn" : "neg"}>
                            {validation.verdict}
                          </Badge>
                        </div>
                        <CardBody className="pt-3">
                          <p className="text-sm text-text-2 mb-3 leading-relaxed">{validation.verdict_detail}</p>
                          <ComparisonBar
                            positive={validation.evidence_counts.supporting}
                            negative={validation.evidence_counts.opposing}
                          />
                        </CardBody>
                      </Card>

                      {/* 证据汇总 */}
                      <EvidenceSummary items={evidenceItems.slice(0, 10)} />

                      {/* 投决会审查 */}
                      {result.ic_review && <ICReviewCard ic={result.ic_review} />}

                      {/* 假设追踪 */}
                      {result.thesis_tracker && <ThesisTrackerCard tracker={result.thesis_tracker} />}

                      {/* 假设健康监控 */}
                      {result.thesis_tracker?.health && <ThesisHealthCard health={result.thesis_tracker.health} />}

                      {/* 推理链 */}
                      {validation.reasoning_chain.length > 0 && (
                        <details className="bg-surface border border-border rounded-lg p-4">
                          <summary className="cursor-pointer font-semibold">推理链（{validation.reasoning_chain.length} 步）</summary>
                          <div className="mt-3 space-y-1">
                            {validation.reasoning_chain.map((node, i) => (
                              <div key={i} className="flex gap-3 text-sm">
                                <span className="text-text-3 min-w-[80px]">{node.step}</span>
                                <span className="flex-1">{node.description}</span>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}

                      {/* 多空辩论 */}
                      {validation.debate && validation.debate.length > 0 && (
                        <details className="bg-surface border border-border rounded-lg p-4">
                          <summary className="cursor-pointer font-semibold">多空辩论</summary>
                          <div className="mt-3 space-y-3">
                            {validation.debate.map((round) => (
                              <div key={round.round} className="p-3 bg-surface-2 rounded-lg">
                                <div className="text-xs text-text-3 mb-2">Round {round.round}</div>
                                <div className="border-l-2 border-pos pl-2 mb-2">
                                  <span className="text-xs text-pos font-semibold">Bull </span>
                                  <span className="text-sm">{round.bull_argument.claim}</span>
                                </div>
                                {round.bear_rebuttal ? (
                                  <div className="border-l-2 border-neg pl-2 mb-2">
                                    <span className="text-xs text-neg font-semibold">Bear </span>
                                    <span className="text-sm">{round.bear_rebuttal.claim}</span>
                                  </div>
                                ) : (
                                  <div className="border-l-2 border-text-3 pl-2 mb-2 text-xs text-text-3">Bear 无反驳</div>
                                )}
                                {round.bull_response && (
                                  <div className="border-l-2 border-pos pl-2">
                                    <span className="text-xs text-pos font-semibold">Bull 回应 </span>
                                    <span className="text-sm">{round.bull_response.claim}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* Tab 4：组合草案 */}
              {activeTab === "portfolio" && (
                <div id="tab-portfolio" className="space-y-4">
                  {!pf || !pf.top_funds || pf.top_funds.length === 0 ? (
                    <EmptyState message="没有合格组合。候选为空时不展示可执行组合。请先调整方向或估值容忍度。" />
                  ) : (
                    <>
                      <div className="p-3 bg-warn-soft border border-warn/30 rounded-lg text-xs text-warn-text font-semibold">
                        研究草案，非交易指令
                      </div>

                      <Card>
                        <CardHeader title="仓位分配" />
                        <CardBody>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                            <DonutChart
                              data={[
                                { name: "认知仓位", value: pf.suggested_weight || 0, color: "#3b82f6" },
                                { name: "防守仓位", value: pf.defense_weight || 0, color: "#10b981" },
                                { name: "现金", value: pf.cash_pct || 0, color: "#e5e7eb" },
                              ]}
                              size={180}
                              innerRadius={45}
                              outerRadius={70}
                              centerLabel="总投资"
                              centerValue={`${(pf.total_invested || 0).toFixed(0)}%`}
                            />
                            <div className="space-y-3">
                              <ProgressBar value={pf.suggested_weight} variant="accent" label="认知仓位" />
                              <ProgressBar value={pf.defense_weight} variant="pos" label="防守仓位" />
                              <ProgressBar value={pf.cash_pct} variant="neutral" label="现金" />
                            </div>
                          </div>

                          {/* 配置清单 */}
                          <div className="mt-4">
                            <Table>
                              <thead><tr><Th>代码</Th><Th>名称</Th><Th>匹配度</Th></tr></thead>
                              <tbody>
                                {pf.top_funds.map((f, i) => {
                                  const ff = f as Record<string, unknown>;
                                  const code = String(ff.fund_code ?? "");
                                  return (
                                    <tr
                                      key={i}
                                      onClick={() => { if (code) { setSelectedFundCode(code); setActiveTab("candidates"); } }}
                                      className="cursor-pointer hover:bg-surface-2"
                                    >
                                      <Td className="font-mono text-xs">{code}</Td>
                                      <Td>{String(ff.fund_name ?? "")}</Td>
                                      <Td className="font-semibold text-accent">{fmt(ff.match_pct as number | null, "%")}</Td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </Table>
                          </div>

                          {pf.defense_fund && (
                            <div className="mt-3 p-3 bg-warn-soft border border-warn/30 rounded-lg text-sm">
                              <span className="text-text-3">防守基金：</span>
                              <strong className="font-mono">{String((pf.defense_fund as Record<string, unknown>).fund_code)}</strong>
                              <span className="ml-1">{String((pf.defense_fund as Record<string, unknown>).fund_name)}</span>
                            </div>
                          )}
                        </CardBody>
                      </Card>

                      {/* 风险指标 */}
                      {pf.metrics && (
                        <Card>
                          <CardHeader title="风险指标" />
                          <CardBody>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                              {pf.metrics.portfolio_pe != null && <Stat label="组合加权 PE" value={pf.metrics.portfolio_pe} />}
                              {pf.metrics.portfolio_volatility != null && (
                                <Stat label="年化波动率" value={fmt(pf.metrics.portfolio_volatility, "%")} variant="warn" />
                              )}
                              {pf.metrics.portfolio_max_drawdown != null && (
                                <Stat label="最大回撤" value={fmt(pf.metrics.portfolio_max_drawdown, "%")} variant="neg" />
                              )}
                            </div>

                            {pf.metrics.holdings_penetration && pf.metrics.holdings_penetration.length > 0 && (
                              <div className="mt-4">
                                <SectionTitle>持仓穿透 Top 10</SectionTitle>
                                <HorizontalBarChart
                                  data={pf.metrics.holdings_penetration.slice(0, 10).map((h) => ({
                                    name: h.stock_name || h.stock_code,
                                    value: h.weight,
                                  }))}
                                  height={280}
                                  color="#6366f1"
                                />
                              </div>
                            )}

                            {pf.metrics.industry_exposure && pf.metrics.industry_exposure.length > 0 && (
                              <div className="mt-4">
                                <SectionTitle>行业暴露</SectionTitle>
                                <HorizontalBarChart
                                  data={pf.metrics.industry_exposure.map((ind) => ({ name: ind.name, value: ind.weight }))}
                                  height={200}
                                  color="#10b981"
                                />
                              </div>
                            )}
                          </CardBody>
                        </Card>
                      )}

                      <button
                        type="button"
                        disabled={exporting}
                        onClick={() => {
                          setExporting(true);
                          exportCognition(result).catch(() => {}).finally(() => setExporting(false));
                        }}
                        className="px-4 py-2 text-sm bg-accent text-white border border-accent rounded-lg hover:opacity-90 disabled:opacity-50"
                      >
                        {exporting ? "导出中…" : "导出 Excel"}
                      </button>
                    </>
                  )}
                </div>
              )}

              {/* Tab 5：投资备忘录 */}
              {activeTab === "memo" && (
                <div id="tab-memo" className="space-y-4">
                  {!result.investment_memo ? (
                    <EmptyState message="暂无投资备忘录。个股认知不生成投资备忘录，请尝试主题或概念方向。" />
                  ) : (
                    <MemoView memo={result.investment_memo} />
                  )}
                </div>
              )}
            </div>

            {/* === 右侧详情栏 === */}
            <aside className="lg:col-span-4 space-y-4 lg:sticky lg:top-4">
              <FundDetailPanel fund={selectedFund} />

              {selectedFund && evidencePacket && (
                <Card>
                  <CardHeader title="证据溯源" />
                  <CardBody>
                    {evidencePacket.evidence_bundle && (
                      <div className="p-2 bg-surface-2 rounded text-xs mb-3 break-all">
                        <span className="text-text-3">Bundle ID：</span>
                        <span className="font-mono font-semibold">{evidencePacket.evidence_bundle.bundle_id}</span>
                        <span className="text-text-3 ml-2">({evidencePacket.evidence_bundle.source_ids.length} 个证据源)</span>
                      </div>
                    )}
                    {evidencePacket.evidence_sources.length > 0 && (
                      <div className="space-y-1.5">
                        {evidencePacket.evidence_sources.map((src) => (
                          <div key={src.source_id} className="p-2 bg-surface-2 rounded text-xs">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <Badge variant="accent">{src.kind}</Badge>
                              <span className="font-semibold flex-1 truncate">{src.title}</span>
                            </div>
                            <div className="flex justify-between text-text-3 text-[11px]">
                              <span>{src.publisher}</span>
                              <span className="font-mono">{src.content_hash}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {evidencePacket.data_quality_notes.length > 0 && (
                      <div className="mt-3">
                        <div className="text-xs text-warn-text font-semibold mb-1">数据缺口</div>
                        {evidencePacket.data_quality_notes.map((note, i) => (
                          <div key={i} className="text-xs text-text-2 py-0.5">- {note}</div>
                        ))}
                      </div>
                    )}
                  </CardBody>
                </Card>
              )}

              {monitorFundCode && (
                <MonitorPanel
                  fundCode={monitorFundCode}
                  overview={monitorData}
                  loading={monitorLoading}
                  error={monitorError}
                />
              )}

              {selectedFund && !monitorFundCode && (
                <button
                  type="button"
                  onClick={() => setMonitorFundCode(selectedFund.fund_code)}
                  className="w-full px-4 py-2 text-sm text-accent border border-accent/30 rounded-lg hover:bg-accent-soft"
                >
                  查看监控面板
                </button>
              )}
              {monitorFundCode && (
                <button
                  type="button"
                  onClick={() => setMonitorFundCode(null)}
                  className="w-full px-4 py-2 text-sm text-text-2 border border-border rounded-lg hover:bg-surface-2"
                >
                  关闭监控
                </button>
              )}
            </aside>
          </div>

          {/* === 第 3 层：完整材料（折叠） === */}
          {pipelineResult && (
            <details className="bg-surface border border-border rounded-lg p-4">
              <summary className="cursor-pointer font-semibold">Pipeline 阶段详情（{pipelineResult.run.run_id}）</summary>
              <div className="mt-3 space-y-2 text-xs">
                {pipelineResult.run.steps.map((step) => (
                  <div key={step.stage} className="flex justify-between items-center p-2 bg-surface-2 rounded">
                    <span className="font-semibold">{PIPELINE_STAGE_LABELS[step.stage] ?? step.stage}</span>
                    <Badge variant={PIPELINE_STATUS_VARIANT[step.status] ?? "neutral"}>
                      {PIPELINE_STATUS_LABEL[step.status] ?? step.status}
                    </Badge>
                    {step.error && <span className="text-neg ml-2 truncate max-w-[40%]">{step.error}</span>}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </CognitionErrorBoundary>
    );
  }

  return null;
}

// === 子组件：投决会审查卡 ===
function ICReviewCard({ ic }: { ic: ICReview }) {
  const isPass = ic.verdict === "pass";
  const pillarLabel: Record<string, string> = { conviction: "投资信心", constitution_fit: "策略适配", data_quality: "数据质量" };
  return (
    <Card>
      <CardHeader title="投决会审查" subtitle={ic.timestamp || undefined} />
      <CardBody className="space-y-4">
        <div className="flex items-center gap-4">
          <span className={`text-3xl font-bold ${isPass ? "text-pos" : "text-neg"}`}>
            {isPass ? "PASS" : "FAIL"}
          </span>
          {ic.is_override && <Badge variant="warn">已覆盖</Badge>}
        </div>

        <ProgressBar
          value={ic.gate_score}
          variant={isPass ? "pos" : "neg"}
          label={`Gate Score vs Cutoff ${ic.cutoff.toFixed(0)}`}
        />

        {ic.fail_reason && (
          <div className="p-3 bg-neg-soft border border-neg/30 rounded text-sm text-neg-text">
            {ic.fail_reason}
          </div>
        )}

        {/* 三支柱 */}
        <div>
          <SectionTitle>评分支柱</SectionTitle>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {ic.pillars.map((p) => {
              const weak = p.score < 25;
              const variant = weak ? "neg" : p.score >= 70 ? "pos" : "warn";
              return (
                <div key={p.name} className={`p-3 bg-surface-2 rounded-lg border ${weak ? "border-neg/40" : "border-transparent"}`}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-semibold">{pillarLabel[p.name] ?? p.name}</span>
                    <Badge variant="neutral">权重 {p.name === "conviction" ? "45%" : p.name === "constitution_fit" ? "35%" : "20%"}</Badge>
                  </div>
                  <ProgressBar value={p.score} variant={variant} showValue={true} />
                  <div className="mt-2 space-y-0.5 text-[11px] text-text-3">
                    {p.components.map((c, i) => (
                      <div key={i} className="flex justify-between">
                        <span>{c.name}</span>
                        <span className={`font-mono ${c.state === "contradicted" ? "text-neg" : c.state === "unknown" ? "text-text-3" : "text-pos"}`}>
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

        {/* 硬性门槛 */}
        {ic.hurdles.length > 0 && (
          <div>
            <SectionTitle>硬性门槛</SectionTitle>
            <Table>
              <thead><tr><Th>门槛</Th><Th>观测值</Th><Th>阈值</Th><Th>结果</Th></tr></thead>
              <tbody>
                {ic.hurdles.map((h) => (
                  <tr key={h.hurdle_id}>
                    <Td>{h.name}</Td>
                    <Td>{h.observed !== null ? h.observed : "-"}</Td>
                    <Td>{h.operator} {h.threshold}</Td>
                    <Td>
                      {h.passed === null ? <Badge variant="neutral">无法判断</Badge>
                        : h.passed ? <Badge variant="pos">通过</Badge>
                          : <Badge variant="neg">未通过</Badge>}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}

        {ic.is_override && ic.override_rationale && (
          <div className="p-3 bg-warn-soft border border-warn/30 rounded text-sm text-warn-text">
            覆盖原因：{ic.override_rationale}
            {ic.prior_verdict && `（原裁决：${ic.prior_verdict}）`}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// === 子组件：假设追踪卡 ===
function ThesisTrackerCard({ tracker }: { tracker: NonNullable<CognitionResponse["thesis_tracker"]> }) {
  const priorPct = Math.round(tracker.prior_probability * 100);
  const postPct = Math.round(tracker.posterior_probability * 100);
  const changePct = Math.round(tracker.probability_change * 100);
  const accuracyVariant: Record<string, "pos" | "warn" | "neg" | "neutral"> = {
    good: "pos", fair: "warn", poor: "neg",
  };
  const accuracyLabel = tracker.prediction_accuracy === "good" ? "优秀"
    : tracker.prediction_accuracy === "fair" ? "一般"
      : tracker.prediction_accuracy === "poor" ? "较差" : "未验证";

  return (
    <Card>
      <CardHeader title="假设追踪" subtitle={`Thesis ID ${tracker.thesis_id}`} />
      <CardBody className="space-y-3">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-text-3">先验概率 {priorPct}%</span>
            <span className={`font-semibold ${changePct >= 0 ? "text-pos" : "text-neg"}`}>
              {changePct >= 0 ? "+" : ""}{changePct}%
            </span>
            <span className="text-accent font-semibold">后验概率 {postPct}%</span>
          </div>
          <div className="relative h-2.5 bg-surface-2 rounded-full overflow-hidden">
            <div className="absolute top-0 left-0 h-full bg-text-3 opacity-40" style={{ width: `${priorPct}%` }} />
            <div className="absolute top-0 left-0 h-full bg-accent" style={{ width: `${postPct}%` }} />
          </div>
        </div>

        <div className="flex flex-wrap gap-4 text-xs">
          <Stat label="证据总计" value={tracker.total_evidence} />
          <Stat label="支持" value={tracker.supporting_evidence} variant="pos" />
          <Stat label="反对" value={tracker.opposing_evidence} variant="neg" />
          <Stat label="已验证预测" value={`${tracker.resolved_predictions}/${tracker.total_predictions}`} />
          <Badge variant={accuracyVariant[tracker.prediction_accuracy] ?? "neutral"}>
            准确度：{accuracyLabel}
          </Badge>
          {tracker.avg_brier_score !== null && (
            <Stat label="平均 Brier" value={tracker.avg_brier_score.toFixed(4)} />
          )}
        </div>

        {tracker.brier_scores && tracker.brier_scores.length > 0 && (
          <div className="border-t border-border pt-3">
            <div className="text-xs text-text-3 mb-2">Brier Score 明细（越低越准）</div>
            <div className="space-y-1">
              {tracker.brier_scores.map((b) => (
                <div key={b.prediction_id} className="flex justify-between text-xs py-1">
                  <span className="flex-1 truncate mr-2">{b.prediction}</span>
                  <span className="text-text-3 min-w-[60px] text-right">预测 {Math.round(b.probability * 100)}%</span>
                  <span className="text-text-3 min-w-[60px] text-right">实际 {b.outcome === 1 ? "是" : "否"}</span>
                  <span className={`min-w-[60px] text-right font-semibold font-mono ${b.brier_score < 0.15 ? "text-pos" : b.brier_score < 0.25 ? "text-warn" : "text-neg"}`}>
                    {b.brier_score.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// === 子组件：假设健康监控 ===
function ThesisHealthCard({ health }: { health: NonNullable<NonNullable<CognitionResponse["thesis_tracker"]>["health"]> }) {
  const variant = health.health_label === "Intact" ? "pos" : health.health_label === "Watching" ? "warn" : health.health_label === "Broken" ? "neg" : "neutral";
  const statusVariant = (s: string): "pos" | "warn" | "neg" | "neutral" =>
    s === "intact" ? "pos" : s === "watch" ? "warn" : s === "broken" ? "neg" : "neutral";
  const statusLabel = (s: string) =>
    s === "intact" ? "正常" : s === "watch" ? "观察" : s === "broken" ? "已破坏" : s === "data_gap" ? "数据缺失" : "未知";
  const itemTypeLabel: Record<string, string> = { kill_criterion: "退出条件", return_driver: "收益驱动", assumption: "假设", risk: "风险" };

  return (
    <Card>
      <CardHeader title="假设健康监控" />
      <CardBody>
        <div className="flex items-center gap-4 mb-4">
          <Badge variant={variant} className="text-base px-3 py-1">{health.health_label}</Badge>
          <span className="text-xs text-text-3">
            正常 {health.intact} · 观察 {health.watch} · 破坏 {health.broken} · 数据缺失 {health.data_gap}
          </span>
        </div>

        <div className="space-y-2">
          {health.items.map((item) => {
            const sv = statusVariant(item.status);
            const borderClass = sv === "pos" ? "border-l-pos" : sv === "warn" ? "border-l-warn" : sv === "neg" ? "border-l-neg" : "border-l-border-2";
            return (
            <div key={item.item_id} className={`p-3 bg-surface-2 rounded border-l-4 ${borderClass}`}>
              <div className="flex justify-between items-start gap-2 mb-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold">{item.title}</span>
                  {itemTypeLabel[item.item_type] && (
                    <span className="text-[11px] px-1.5 py-0.5 bg-surface text-text-3 rounded">{itemTypeLabel[item.item_type]}</span>
                  )}
                  {item.immediate_kill && <Badge variant="neg">即时退出</Badge>}
                </div>
                <Badge variant={statusVariant(item.status)}>{statusLabel(item.status)}</Badge>
              </div>
              <div className="flex gap-4 text-xs text-text-3 flex-wrap">
                <span>指标 {item.metric ?? "-"}：{item.last_value !== null ? item.last_value : "-"} {item.comparator} {item.threshold !== null ? item.threshold : "-"}</span>
                {item.consecutive_breaches > 0 && (
                  <span className="text-warn">连续违规 {item.consecutive_breaches}/{item.confirmation_periods}</span>
                )}
              </div>
              {item.why_matters && <div className="text-xs text-text-2 mt-1">{item.why_matters}</div>}
            </div>
            );
          })}
        </div>
      </CardBody>
    </Card>
  );
}

// === 子组件：备忘录视图 ===
function MemoView({ memo }: { memo: NonNullable<CognitionResponse["investment_memo"]> }) {
  const dc = DECISION_CONFIG[memo.decision] ?? DECISION_CONFIG.needs_more_evidence;
  const scenarioData = [
    { scenario: "悲观", return: memo.scenario.bear.return, probability: memo.scenario.bear.probability, color: "#dc2626" },
    { scenario: "基准", return: memo.scenario.base.return, probability: memo.scenario.base.probability, color: "#2563eb" },
    { scenario: "乐观", return: memo.scenario.bull.return, probability: memo.scenario.bull.probability, color: "#16a34a" },
  ];
  const expectedReturn = scenarioData.reduce((acc, s) => acc + (s.probability * s.return) / 100, 0);
  const snap = memo.financial_snapshot;

  return (
    <>
      {/* 决策标签 */}
      <Card>
        <CardBody className="flex justify-between items-center flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-3 uppercase tracking-wide">投资决策</span>
            <Badge variant={dc.variant} className="text-sm px-3 py-1">{dc.label}</Badge>
          </div>
          <span className="text-xs text-text-3">生成于 {memo.generated_at}</span>
        </CardBody>
      </Card>

      {/* 七段式备忘录 */}
      {memo.sections.map((section, idx) => (
        <Card key={section.section_id}>
          <CardHeader
            title={`${idx + 1}. ${section.title}`}
            subtitle={section.thesis}
          />
          <CardBody>
            {section.key_figures && section.key_figures.length > 0 && (
              <Table className="mb-3">
                <tbody>
                  {section.key_figures.map((fig, fi) => (
                    <tr key={fi}>
                      <Td className="text-text-3 w-2/5">{fig.label}</Td>
                      <Td className="font-semibold">
                        {fig.value !== null && fig.value !== "" ? String(fig.value) : "-"}
                        {fig.unit && <span className="text-text-3 ml-1">{fig.unit}</span>}
                      </Td>
                      <Td className="text-text-3 text-[11px] text-right">{fig.source}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            <p className="text-sm text-text-2 leading-relaxed m-0">{section.content}</p>
          </CardBody>
        </Card>
      ))}

      {/* 场景分析 */}
      <Card>
        <CardHeader title="场景分析" subtitle="Bear / Base / Bull 概率加权" />
        <CardBody>
          <ScenarioChart data={scenarioData} />
          <div className="mt-3 p-2 bg-surface-2 rounded text-sm flex items-center gap-2">
            <span className="text-text-3">期望收益（加权）：</span>
            <span className={`font-semibold font-mono ${expectedReturn >= 0 ? "text-pos" : "text-neg"}`}>
              {expectedReturn >= 0 ? "+" : ""}{expectedReturn.toFixed(1)}%
            </span>
          </div>
        </CardBody>
      </Card>

      {/* 财务快照 */}
      <Card>
        <CardHeader title="财务快照" />
        <CardBody className="p-0">
          <Table>
            <tbody>
              <tr><Td className="text-text-3">顶部基金</Td><Td className="font-semibold">{snap.top_fund_code ?? "-"} {snap.top_fund_name ?? ""}</Td></tr>
              <tr><Td className="text-text-3">匹配度</Td><Td className="font-semibold">{snap.match_pct != null ? `${snap.match_pct}%` : "-"}</Td></tr>
              <tr><Td className="text-text-3">加权 PE</Td><Td className="font-semibold">{snap.weighted_pe ?? "-"}</Td></tr>
              <tr><Td className="text-text-3">加权 ROE</Td><Td className="font-semibold">{snap.weighted_roe != null ? `${snap.weighted_roe}%` : "-"}</Td></tr>
              <tr><Td className="text-text-3">加权 PB</Td><Td className="font-semibold">{snap.weighted_pb ?? "-"}</Td></tr>
              <tr><Td className="text-text-3">PEG</Td><Td className="font-semibold">{snap.peg ?? "-"}</Td></tr>
              <tr><Td className="text-text-3">估值分位</Td><Td className="font-semibold">{snap.val_pct != null ? `${snap.val_pct}%` : "-"}</Td></tr>
            </tbody>
          </Table>
        </CardBody>
      </Card>
    </>
  );
}