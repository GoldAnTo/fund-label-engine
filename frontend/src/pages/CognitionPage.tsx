import { useEffect, useState, Component, ReactNode } from "react";
import {
  fetchThemes, postCognition, searchConcepts, postConceptCognition,
  searchStocks, postStockCognition, exportCognition, fetchMonitorOverview,
  runPipeline,
  type ThemeInfo, type CognitionResponse, type ConceptBoard,
  type StockSearchResult, type MonitorOverview, type ICReview,
  type FundEvidencePacket, type AttentionItem, type InboxSnapshot,
  type ScreenSnapshot, type PipelineResult, type DebateRound,
} from "../api";
import { DonutChart, HorizontalBarChart, ScenarioChart, ValuationGauge, RadarChartViz } from "../charts";
import {
  Card, CardHeader, CardBody, Badge, ProgressBar, Stat, Table, Th, Td,
  Loading, ErrorBox, EmptyState, TabBar,
} from "../components/ui";

// === 标签映射 ===
const CONVICTION_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };
const RISK_LABEL: Record<string, string> = { conservative: "保守", balanced: "适中", aggressive: "进取" };
const HORIZON_LABEL: Record<string, string> = { short: "短期", medium: "中期", long: "长期" };
const PIPELINE_STAGE_LABELS: Record<string, string> = {
  screener: "筛选", cognition: "认知", ic_review: "投决", memo: "备忘", portfolio: "组合", monitoring: "监控",
};
const PIPELINE_STAGE_ORDER = ["screener", "cognition", "ic_review", "memo", "portfolio", "monitoring"];
const PIPELINE_STATUS_VARIANT: Record<string, "pos" | "neg" | "warn" | "neutral"> = {
  completed: "pos", failed: "neg", running: "warn", skipped: "neutral", pending: "neutral",
};
const PIPELINE_STATUS_LABEL: Record<string, string> = {
  completed: "完成", failed: "失败", running: "运行中", skipped: "跳过", pending: "等待",
};
const DECISION_CONFIG: Record<string, { label: string; variant: "pos" | "warn" | "neg" | "neutral" }> = {
  attractive: { label: "有吸引力", variant: "pos" },
  watchlist: { label: "观察名单", variant: "warn" },
  avoid: { label: "暂不参与", variant: "neg" },
  needs_more_evidence: { label: "证据不足", variant: "neutral" },
};

const COGNITION_TABS = [
  { id: "summary", label: "概览" },
  { id: "evidence", label: "证据链" },
  { id: "candidates", label: "候选基金" },
  { id: "risk", label: "风险护栏" },
  { id: "portfolio", label: "组合与备忘录" },
];

function fmt(v: number | string | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "-";
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return String(v);
  return Number.isInteger(n) ? `${n}${suffix}` : `${n.toFixed(1)}${suffix}`;
}

// === 错误边界 ===
class CognitionErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
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

// === 主组件：双栏工作台 ===
export default function CognitionPage() {
  // 状态：步骤 / 输入 / 主题
  const [step, setStep] = useState<1 | 2>(1);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [direction, setDirection] = useState("");
  const [conviction, setConviction] = useState("medium");
  const [riskTolerance, setRiskTolerance] = useState("balanced");
  const [timeHorizon, setTimeHorizon] = useState("medium");
  const [result, setResult] = useState<CognitionResponse | null>(null);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null);
  const [pipelineProgress, setPipelineProgress] = useState<{ stage: string; label: string; progress: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 状态：联想搜索 / 高级选项
  const [searchKeyword, setSearchKeyword] = useState("");
  const [conceptResults, setConceptResults] = useState<ConceptBoard[]>([]);
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [beliefNote, setBeliefNote] = useState("");
  const [reasoningSteps, setReasoningSteps] = useState<string[]>([""]);

  // 状态：详情栏 / 监控 / 导出
  const [selectedFundCode, setSelectedFundCode] = useState<string | null>(null);
  const [monitorFundCode, setMonitorFundCode] = useState<string | null>(null);
  const [monitorData, setMonitorData] = useState<MonitorOverview | null>(null);
  const [monitorLoading, setMonitorLoading] = useState(false);
  const [monitorError, setMonitorError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState<"summary" | "evidence" | "candidates" | "risk" | "portfolio">("summary");

  // === Effects ===
  useEffect(() => {
    fetchThemes().then((r) => setThemes(r.themes)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!searchKeyword.trim()) {
      setConceptResults([]); setStockResults([]); setSearchLoading(false); return;
    }
    setSearchLoading(true);
    const timer = setTimeout(() => {
      Promise.all([
        searchConcepts(searchKeyword.trim()).catch(() => [] as ConceptBoard[]),
        searchStocks(searchKeyword.trim()).catch(() => [] as StockSearchResult[]),
      ]).then(([concepts, stocks]) => {
        setConceptResults(concepts); setStockResults(stocks); setSearchLoading(false);
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [searchKeyword]);

  useEffect(() => {
    if (!monitorFundCode) { setMonitorData(null); setMonitorError(null); return; }
    let cancelled = false;
    setMonitorLoading(true); setMonitorError(null);
    fetchMonitorOverview(monitorFundCode).then(
      (data) => { if (!cancelled) { setMonitorData(data); setMonitorLoading(false); } },
      (err) => { if (!cancelled) { setMonitorError(err instanceof Error ? err.message : String(err)); setMonitorLoading(false); } }
    );
    return () => { cancelled = true; };
  }, [monitorFundCode]);

  // === 动作 ===
  const startProgressStream = (dirText: string) => {
    const BASE = import.meta.env.VITE_API_BASE ?? "";
    const url = `${BASE}/v1/cognition/stream?direction=${encodeURIComponent(dirText)}&conviction=${conviction}&risk_tolerance=${riskTolerance}&time_horizon=${timeHorizon}`;

    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "complete") {
          setPipelineProgress(null);
          eventSource.close();
        } else {
          setPipelineProgress({ stage: data.stage, label: data.label, progress: data.progress });
        }
      } catch {
        // ignore parse errors
      }
    };

    eventSource.onerror = () => {
      setPipelineProgress(null);
      eventSource.close();
    };
  };

  const triggerAnalysis = (dirText: string, run: () => Promise<CognitionResponse>) => {
    setLoading(true); setError(null);
    startProgressStream(dirText);
    run().then((r) => {
      setResult(r); setStep(2); setDirection(dirText);
      setSelectedFundCode(null); setMonitorFundCode(null); setPipelineResult(null);
      runPipeline(dirText).then(setPipelineResult).catch(() => {});
    }).catch(() => setError("分析失败，请重试")).finally(() => setLoading(false));
  };

  const runThemeCognition = () => {
    if (!direction.trim()) return;
    const chain = reasoningSteps.filter(s => s.trim());
    triggerAnalysis(direction.trim(), () =>
      postCognition(direction.trim(), undefined, conviction, riskTolerance, timeHorizon, beliefNote || undefined, chain.length ? chain : undefined)
    );
  };
  const pickConcept = (concept: ConceptBoard) => {
    setSearchKeyword(""); setShowDropdown(false);
    const chain = reasoningSteps.filter(s => s.trim());
    triggerAnalysis(concept.name, () =>
      postConceptCognition(concept.code, concept.name, conviction, riskTolerance, timeHorizon, beliefNote || undefined, chain.length ? chain : undefined)
    );
  };
  const pickStock = (stock: StockSearchResult) => {
    setSearchKeyword(""); setShowDropdown(false);
    const chain = reasoningSteps.filter(s => s.trim());
    triggerAnalysis(`${stock.stock_name}（个股认知）`, () =>
      postStockCognition(stock.stock_code, stock.stock_name, conviction, riskTolerance, timeHorizon, beliefNote || undefined, chain.length ? chain : undefined).then((r) => r as CognitionResponse)
    );
  };
  const reset = () => {
    setStep(1); setDirection(""); setResult(null); setPipelineResult(null);
    setPipelineProgress(null);
    setSearchKeyword(""); setSelectedFundCode(null); setMonitorFundCode(null); setError(null);
  };

  // === Step 1：输入页 ===
  if (step === 1) {
    return (
      <div className="main cognition-form">
        <div className="mb-8">
          <h2 className="text-2xl font-bold tracking-tight mb-2">你相信什么？</h2>
          <p className="text-text-3 text-sm leading-relaxed">
            输入方向关键词，或选择预设主题。系统会从认知推导到基金配置，并给出可执行的投资结论。
          </p>
        </div>

        {/* 搜索框：联想概念/个股 */}
        <div className="relative mb-6">
          <label htmlFor="cognition-search" className="block text-xs uppercase tracking-wide text-text-3 mb-2">搜索方向</label>
          <div className="flex gap-2">
            <input
              id="cognition-search"
              type="search"
              className="flex-1 px-4 py-3 text-sm bg-surface border border-border rounded-lg focus:outline-none focus:border-accent"
              value={searchKeyword}
              onChange={(e) => { setSearchKeyword(e.target.value); setShowDropdown(true); }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              onKeyDown={(e) => { if (e.key === "Enter" && searchKeyword.trim()) { setDirection(searchKeyword.trim()); setShowDropdown(false); } }}
              placeholder="搜索概念板块或个股，如：AI、芯片、贵州茅台..."
              aria-label="搜索方向"
            />
            <button type="button" className="px-5 py-3 text-sm bg-accent text-white border border-accent rounded-lg hover:opacity-90"
              onClick={() => { if (searchKeyword.trim()) { setDirection(searchKeyword.trim()); setShowDropdown(false); } }}>填入</button>
          </div>
          {showDropdown && searchKeyword.trim() && (
            <div className="absolute top-full left-0 right-0 z-50 bg-surface border border-border border-t-0 rounded-b-lg shadow-lg max-h-96 overflow-y-auto">
              {searchLoading && <div className="p-3 text-text-3 text-xs">搜索中…</div>}
              {conceptResults.length > 0 && (
                <div className="border-b border-border">
                  <div className="px-3 py-1.5 text-[11px] text-text-3 bg-surface-2">概念板块</div>
                  {conceptResults.slice(0, 5).map((c) => (
                    <button key={c.code} type="button" onClick={() => pickConcept(c)}
                      className="block w-full text-left px-3 py-2 hover:bg-accent-soft border-b border-border last:border-b-0">
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
                    <button key={s.stock_code} type="button" onClick={() => pickStock(s)}
                      className="block w-full text-left px-3 py-2 hover:bg-accent-soft border-b border-border last:border-b-0">
                      <div className="font-semibold text-sm">{s.stock_name}<span className="text-xs text-text-3 ml-2">{s.stock_code}</span></div>
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
                <button type="button" className="block w-full text-left p-3 text-text-3 text-xs hover:bg-accent-soft"
                  onClick={() => { setDirection(searchKeyword.trim()); setShowDropdown(false); }}>
                  未找到匹配，将作为自定义方向分析：{searchKeyword.trim()}
                </button>
              )}
            </div>
          )}
        </div>

        {/* 当前方向输入 */}
        <div className="mb-6">
          <label htmlFor="cognition-direction" className="block text-xs uppercase tracking-wide text-text-3 mb-2">分析方向</label>
          <input id="cognition-direction" type="text"
            className="w-full px-4 py-3 text-sm bg-surface border border-border rounded-lg focus:outline-none focus:border-accent"
            value={direction} onChange={(e) => setDirection(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && direction.trim() && runThemeCognition()}
            placeholder="例如：AI、消费、创新药、新能源..." aria-label="分析方向" />
        </div>

        {/* 预设主题 chip */}
        <div className="mb-6">
          <div className="text-xs uppercase tracking-wide text-text-3 mb-3">预设主题</div>
          <div className="flex flex-wrap gap-2">
            {themes.map((t) => (
              <button key={t.key} type="button" onClick={() => setDirection(t.key)}
                className={`px-3 py-1.5 rounded text-xs border transition-colors ${
                  direction === t.key ? "border-accent bg-accent-soft text-accent"
                    : "border-border bg-transparent text-text-2 hover:border-accent"}`}>
                {t.name}
              </button>
            ))}
          </div>
        </div>

        {/* 高级选项 */}
        <div className="mb-6">
          <button type="button" onClick={() => setShowAdvanced(!showAdvanced)} className="text-xs text-text-3 hover:text-accent">
            {showAdvanced ? "收起高级选项" : "展开高级选项"}
          </button>
          {showAdvanced && (
            <div className="mt-3 p-4 bg-surface-2 rounded-lg space-y-4">
              <div>
                <div className="text-xs text-text-3 mb-2">信心强度</div>
                <div className="flex gap-2">
                  {["low", "medium", "high"].map((c) => (
                    <button key={c} type="button" onClick={() => setConviction(c)}
                      className={`px-3 py-1 rounded text-xs border ${
                        conviction === c ? "border-accent bg-accent-soft text-accent"
                          : "border-border bg-surface text-text-2 hover:border-accent"}`}>{CONVICTION_LABEL[c]}</button>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-3 mb-2">风险偏好</div>
                <div className="flex gap-2">
                  {["conservative", "balanced", "aggressive"].map((r) => (
                    <button key={r} type="button" onClick={() => setRiskTolerance(r)}
                      className={`px-3 py-1 rounded text-xs border ${
                        riskTolerance === r ? "border-accent bg-accent-soft text-accent"
                          : "border-border bg-surface text-text-2 hover:border-accent"}`}>{RISK_LABEL[r]}</button>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-3 mb-2">投资周期</div>
                <div className="flex gap-2">
                  {["short", "medium", "long"].map((h) => (
                    <button key={h} type="button" onClick={() => setTimeHorizon(h)}
                      className={`px-3 py-1 rounded text-xs border ${
                        timeHorizon === h ? "border-accent bg-accent-soft text-accent"
                          : "border-border bg-surface text-text-2 hover:border-accent"}`}>{HORIZON_LABEL[h]}</button>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-3 mb-2">我的观点（可选，1000 字内）</div>
                <textarea className="w-full min-h-[80px] px-3 py-2 text-sm bg-surface border border-border rounded-lg font-sans resize-y focus:outline-none focus:border-accent"
                  value={beliefNote} onChange={(e) => setBeliefNote(e.target.value.slice(0, 1000))}
                  placeholder="例如：受益于国产替代 + 下游需求扩张 + 估值合理..." />
              </div>
              <div>
                <div className="text-xs text-text-3 mb-2">因果链（为什么相信？按顺序填写推理步骤）</div>
                <div className="space-y-1.5">
                  {reasoningSteps.map((step, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-xs text-text-3 w-5 text-right shrink-0">{i + 1}.</span>
                      <input className="flex-1 px-2.5 py-1.5 text-sm bg-surface border border-border rounded-lg font-sans focus:outline-none focus:border-accent"
                        value={step} onChange={(e) => setReasoningSteps(prev => prev.map((s, j) => j === i ? e.target.value : s))}
                        placeholder={i === 0 ? "例如：AI是生产力变革" : i === 1 ? "例如：生产资产最值钱" : "继续推理..."} />
                      {reasoningSteps.length > 1 && (
                        <button type="button" onClick={() => setReasoningSteps(prev => prev.filter((_, j) => j !== i))}
                          className="text-text-3 hover:text-neg text-sm shrink-0">✕</button>
                      )}
                    </div>
                  ))}
                  {reasoningSteps.length < 6 && (
                    <button type="button" onClick={() => setReasoningSteps(prev => [...prev, ""])}
                      className="text-xs text-accent hover:underline">+ 添加步骤</button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {error && <ErrorBox message={error} />}
        <button type="button" disabled={!direction.trim() || loading} onClick={runThemeCognition}
          className="w-full px-4 py-3.5 text-sm font-semibold bg-accent text-white border border-accent rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed">
          {loading ? "分析中…" : "开始分析"}
        </button>
        {loading && pipelineProgress && (
          <div className="mt-4 p-4 bg-surface border border-border rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-accent">{pipelineProgress.label}</span>
              <span className="text-xs text-text-3 font-mono">{pipelineProgress.progress.toFixed(0)}%</span>
            </div>
            <div className="w-full h-2 bg-surface-2 rounded-full overflow-hidden">
              <div className="h-full bg-accent rounded-full transition-all duration-300" style={{ width: `${pipelineProgress.progress}%` }} />
            </div>
            <div className="mt-2 flex gap-1 flex-wrap">
              {["cognition_input", "chain_analysis", "expectation_gap", "asset_penetration", "validation", "portfolio", "output"].map((s, i) => {
                const stageLabels: Record<string, string> = {
                  cognition_input: "认知采集", chain_analysis: "产业链拆解", expectation_gap: "预期差分析",
                  asset_penetration: "资产穿透", validation: "认知验证", portfolio: "组合构建", output: "结果输出",
                };
                const currentIdx = ["cognition_input", "chain_analysis", "expectation_gap", "asset_penetration", "validation", "portfolio", "output"].indexOf(pipelineProgress.stage);
                const isDone = i < currentIdx;
                const isActive = i === currentIdx;
                return (
                  <span key={s} className={`text-[10px] px-1.5 py-0.5 rounded ${
                    isDone ? "bg-pos-soft text-pos" : isActive ? "bg-accent-soft text-accent" : "bg-surface-2 text-text-3"
                  }`}>
                    {stageLabels[s]}
                  </span>
                );
              })}
            </div>
          </div>
        )}
        {loading && !pipelineProgress && <Loading text="正在分析方向并推导配置…" />}
      </div>
    );
  }

  // === Step 2：结果页（双栏布局） ===
  if (step === 2 && result) {
    const gap = result.step3_expectation_gap;
    const validation = result.step5_validation ?? null;
    const pf = result.step5_portfolio;
    const fundMatches = result.step4_fund_matches ?? [];
    const gatedOut = result.gated_out_funds ?? [];
    const screenSnapshot: ScreenSnapshot | null = result.screen_snapshot ?? null;
    const inbox: InboxSnapshot | null = result.inbox ?? null;
    const asOfDate = (result as { step1_judgment?: { as_of_date?: string | null } }).step1_judgment?.as_of_date ?? null;
    const selectedFund = selectedFundCode ? fundMatches.find((f) => f.fund_code === selectedFundCode) ?? null : null;
    const evidencePacket: FundEvidencePacket | null = selectedFundCode
      ? result.evidence_packets?.find((p) => p.fund_code === selectedFundCode) ?? null : null;
    const gapPositive = gap?.positive?.length ?? 0;
    const gapNegative = gap?.negative?.length ?? 0;
    const gapNeutral = gap?.neutral?.length ?? 0;

    // 一句话结论
    const headline = (() => {
      if (result.ic_review) {
        const isPass = result.ic_review.verdict === "pass";
        const w = pf?.suggested_weight ?? 0;
        const d = result.direction;
        if (isPass && w > 0) return { verdict: "PASS" as const, text: `${d}方向投决会通过，建议 ${w.toFixed(0)}% 仓位。` };
        if (isPass) return { verdict: "WATCH" as const, text: `${d}方向通过审查，但当前无可执行组合。` };
        return { verdict: "FAIL" as const, text: `${d}方向未通过投决会审查，暂不参与。` };
      }
      if (result.investment_memo) {
        const dec = result.investment_memo.decision;
        if (dec === "attractive") return { verdict: "PASS" as const, text: `${result.direction}方向有吸引力。` };
        if (dec === "watchlist") return { verdict: "WATCH" as const, text: `${result.direction}方向列入观察。` };
        if (dec === "avoid") return { verdict: "FAIL" as const, text: `${result.direction}方向暂不参与。` };
      }
      return { verdict: "PENDING" as const, text: `${result.direction}方向：证据不足，建议补充更多数据后再判断。` };
    })();

    const supportingTop5 = (validation?.supporting_evidence || []).slice(0, 5);
    const opposingTop5 = (validation?.opposing_evidence || []).slice(0, 5);
    const supportingExtra = (validation?.supporting_evidence || []).length - supportingTop5.length;
    const opposingExtra = (validation?.opposing_evidence || []).length - opposingTop5.length;

    // IC 裁决摘要
    const icPass = result.ic_review?.verdict === "pass";

    return (
      <CognitionErrorBoundary>
        <div className="main space-y-6">
          {/* 头部：方向 + Pipeline 状态 + 返回 */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3 flex-wrap min-w-0">
              <span className="text-xs uppercase tracking-wide text-text-3">方向</span>
              <h1 className="text-xl font-bold m-0 truncate">{result.direction}</h1>
              <Badge variant="accent">{CONVICTION_LABEL[result.conviction] ?? "中"}</Badge>
              <span className="text-xs text-text-3">
                匹配 {fundMatches.length} 只
                {gatedOut.length > 0 && ` · 拦截 ${gatedOut.length} 只`}
                {asOfDate && ` · 数据日期 ${asOfDate}`}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {pipelineResult && (
                <div className="flex gap-1 flex-wrap">
                  {PIPELINE_STAGE_ORDER.map((stage) => {
                    const s = pipelineResult.run.steps.find((x) => x.stage === stage);
                    const status = s?.status ?? "pending";
                    return <Badge key={stage} variant={PIPELINE_STATUS_VARIANT[status] ?? "neutral"}>{PIPELINE_STAGE_LABELS[stage]}</Badge>;
                  })}
                </div>
              )}
              <button type="button" onClick={reset}
                className="px-3 py-1.5 text-xs text-accent border border-accent/30 rounded hover:bg-accent-soft">返回</button>
            </div>
          </div>

          {error && <ErrorBox message={error} />}

          {/* 双栏：主区 + 详情栏 */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* 主区 */}
            <div className="lg:col-span-8 space-y-8">
              <TabBar
                tabs={COGNITION_TABS}
                active={activeTab}
                onChange={(id) => setActiveTab(id as typeof activeTab)}
              />
              {activeTab === "summary" && (
              <>
              {/* 1. 决策摘要条（4 列） */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <KpiTile label="IC 投决">
                  {result.ic_review ? (
                    <>
                      <div className={`text-3xl font-bold font-mono ${icPass ? "text-pos" : "text-neg"}`}>{icPass ? "PASS" : "FAIL"}</div>
                      <div className="text-[11px] text-text-3 mt-1">Score {result.ic_review.gate_score.toFixed(0)} / Cutoff {result.ic_review.cutoff.toFixed(0)}</div>
                    </>
                  ) : <div className="text-3xl font-bold text-text-3 font-mono">—</div>}
                </KpiTile>
                <KpiTile label="假设健康">
                  {result.thesis_tracker?.health ? (
                    <>
                      <Badge variant={healthVariant(result.thesis_tracker.health.health_label)} className="text-base px-3 py-1">
                        {result.thesis_tracker.health.health_label}
                      </Badge>
                      <div className="text-[11px] text-text-3 mt-2">
                        正常 {result.thesis_tracker.health.intact} · 观察 {result.thesis_tracker.health.watch} · 破坏 {result.thesis_tracker.health.broken}
                      </div>
                    </>
                  ) : <div className="text-3xl font-bold text-text-3 font-mono">—</div>}
                </KpiTile>
                <KpiTile label="Inbox">
                  {inbox ? (
                    <>
                      <div className="text-3xl font-bold font-mono">{inbox.open_items}</div>
                      <div className="flex gap-1 flex-wrap mt-2">
                        {inbox.high_severity > 0 && <Badge variant="neg">高 {inbox.high_severity}</Badge>}
                        {inbox.medium_severity > 0 && <Badge variant="warn">中 {inbox.medium_severity}</Badge>}
                        {inbox.low_severity > 0 && <Badge variant="neutral">低 {inbox.low_severity}</Badge>}
                      </div>
                    </>
                  ) : <div className="text-3xl font-bold text-text-3 font-mono">0</div>}
                </KpiTile>
                <KpiTile label="Pipeline">
                  {pipelineResult ? (
                    <>
                      <div className="text-3xl font-bold font-mono">
                        {pipelineResult.run.steps.filter((s) => s.status === "completed").length}/{PIPELINE_STAGE_ORDER.length}
                      </div>
                      {pipelineResult.partial && <Badge variant="warn" className="mt-2">部分完成</Badge>}
                    </>
                  ) : <div className="text-3xl font-bold text-text-3 font-mono">—</div>}
                </KpiTile>
              </div>

              {/* 2. 一句话结论 */}
              <div className={`p-6 rounded-lg border-l-4 ${
                headline.verdict === "PASS" ? "bg-pos-soft border-pos" :
                headline.verdict === "FAIL" ? "bg-neg-soft border-neg" :
                headline.verdict === "WATCH" ? "bg-warn-soft border-warn" : "bg-surface border-border"}`}>
                <div className="flex items-start gap-3">
                  <span className={`text-2xl font-bold font-mono shrink-0 ${
                    headline.verdict === "PASS" ? "text-pos" :
                    headline.verdict === "FAIL" ? "text-neg" :
                    headline.verdict === "WATCH" ? "text-warn" : "text-text-3"}`}>{headline.verdict}</span>
                  <p className="text-base font-medium leading-relaxed m-0 flex-1">{headline.text}</p>
                </div>
              </div>
              </>
              )}
              {activeTab === "evidence" && (
              <section>
                {(result as { step0_thesis?: { belief?: string; reasoning_chain?: string[]; falsification_conditions?: string[]; source?: string } }).step0_thesis && (
                  <div className="p-6 bg-surface border border-border rounded-lg mb-4">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs uppercase tracking-wide text-text-3">投资假设（Thesis）</span>
                      {(result as { step0_thesis?: { source?: string } }).step0_thesis?.source === "user" && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-accent-soft text-accent rounded">用户输入</span>
                      )}
                    </div>
                    <p className="text-sm leading-relaxed m-0 font-medium">{(result as { step0_thesis?: { belief?: string } }).step0_thesis?.belief}</p>
                    {(result as { step0_thesis?: { reasoning_chain?: string[] } }).step0_thesis?.reasoning_chain && (result as { step0_thesis?: { reasoning_chain?: string[] } }).step0_thesis!.reasoning_chain!.length > 0 && (
                      <div className="mt-3 space-y-1">
                        <div className="text-xs text-text-3">因果链：</div>
                        <ol className="text-sm text-text-1 m-0 pl-5 list-decimal space-y-0.5">
                          {(result as { step0_thesis?: { reasoning_chain?: string[] } }).step0_thesis!.reasoning_chain!.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                    {(result as { step0_thesis?: { falsification_conditions?: string[] } }).step0_thesis?.falsification_conditions && (result as { step0_thesis?: { falsification_conditions?: string[] } }).step0_thesis!.falsification_conditions!.length > 0 && (
                      <div className="mt-3">
                        <div className="text-xs text-text-3 mb-1">证伪条件（出现则假设不成立）：</div>
                        <ul className="text-sm text-neg m-0 pl-5 list-disc space-y-0.5">
                          {(result as { step0_thesis?: { falsification_conditions?: string[] } }).step0_thesis!.falsification_conditions!.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
                {result.step1_judgment?.belief && (
                  <div className="p-4 bg-surface border border-border rounded-lg mb-4">
                    <div className="text-xs uppercase tracking-wide text-text-3 mb-1">系统判断模板</div>
                    <p className="text-sm text-text-2 m-0">{result.step1_judgment.belief}</p>
                    {result.step1_judgment.key_metric && (
                      <div className="text-xs text-text-3 mt-2">核心指标：{result.step1_judgment.key_metric}</div>
                    )}
                  </div>
                )}
                {gap && (gapPositive + gapNegative + gapNeutral) > 0 && (
                  <Card className="mb-4">
                    <CardHeader title="产业链预期差"
                      subtitle={gap.best_link ? `最优环节：${gap.best_link.link_name}（评分 ${fmt(gap.best_link.score)}）` : undefined} />
                    <CardBody>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                        <DonutChart
                          data={[
                            { name: "正预期差", value: gapPositive, color: "#16a34a" },
                            { name: "中性", value: gapNeutral, color: "#ca8a04" },
                            { name: "负预期差", value: gapNegative, color: "#dc2626" },
                          ].filter((d) => d.value > 0)}
                          size={170} innerRadius={45} outerRadius={70}
                          centerLabel="环节数" centerValue={`${gapPositive + gapNeutral + gapNegative}`} />
                        <div className="space-y-2">
                          <p className="text-sm text-text-2 leading-relaxed m-0">
                            {gapPositive > gapNegative ? `整体偏正向：${gapPositive} 个环节存在正预期差，市场尚未充分定价。` :
                              gapNegative > gapPositive ? `整体偏负向：${gapNegative} 个环节存在负预期差，建议谨慎。` :
                                `正负预期差相近，方向选择不明确。`}
                          </p>
                          {gap.summary && <p className="text-xs text-text-3 leading-relaxed">{gap.summary}</p>}
                        </div>
                      </div>
                    </CardBody>
                  </Card>
                )}
                <EvidenceList kind="pos" title="支持证据" count={validation?.evidence_counts.supporting ?? supportingTop5.length}
                  items={supportingTop5} extra={supportingExtra} />
                <EvidenceList kind="neg" title="反对证据" count={validation?.evidence_counts.opposing ?? opposingTop5.length}
                  items={opposingTop5} extra={opposingExtra} />
                {validation?.debate && validation.debate.length > 0 && (
                  <DebateView debate={validation.debate} />
                )}
              </section>
              )}
              {activeTab === "candidates" && (
              <section>
                <div className="flex items-baseline justify-between mb-3">
                  {selectedFund && (
                    <div className="text-sm">
                      <span className="text-text-3">当前查看</span>
                      <span className="font-semibold ml-2">{selectedFund.fund_name}</span>
                      <span className="text-text-3 font-mono ml-2">{selectedFund.fund_code}</span>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <Stat label="匹配基金" value={fundMatches.length} unit="只" variant="accent" />
                  <Stat label="通过筛选" value={screenSnapshot?.passed_funds ?? fundMatches.length} unit="只" variant="pos" />
                  <Stat label="门禁拦截" value={gatedOut.length} unit="只" variant="neg" />
                  <Stat label="数据缺口" value={validation?.warnings?.length ?? 0} unit="条" />
                </div>
                {fundMatches.length > 5 && (
                  <Card className="mb-4">
                    <CardHeader title="匹配度分布" />
                    <CardBody>
                      <HorizontalBarChart
                        data={fundMatches.slice(0, 12).map((f) => ({
                          name: f.fund_name?.length > 16 ? `${f.fund_name.slice(0, 16)}…` : (f.fund_name ?? f.fund_code),
                          value: Number(f.match_pct ?? 0),
                        }))}
                        unit="%" height={Math.max(160, fundMatches.length * 28)} color="#3b82f6" />
                    </CardBody>
                  </Card>
                )}
                {fundMatches.length === 0 ? (
                  <EmptyState message="当前没有合格研究候选。所有匹配基金都未通过估值门禁或数据缺失。" />
                ) : (
                  <Card>
                    <CardBody className="p-0">
                      <Table>
                        <thead><tr><Th>代码</Th><Th>名称</Th><Th className="text-right">匹配度</Th><Th>门禁</Th></tr></thead>
                        <tbody>
                          {fundMatches.map((f) => {
                            const isSelected = selectedFundCode === f.fund_code;
                            return (
                              <tr key={f.fund_code} onClick={() => setSelectedFundCode(f.fund_code)}
                                className={`cursor-pointer hover:bg-surface-2 ${isSelected ? "bg-accent-soft" : ""}`}>
                                <Td className="font-mono text-xs">{f.fund_code}</Td>
                                <Td>{f.fund_name}</Td>
                                <Td className="font-semibold text-accent text-right">{fmt(f.match_pct, "%")}</Td>
                                <Td>{f.gate ? (
                                  f.gate.passed ? <Badge variant="pos">通过</Badge>
                                    : <span title={f.gate.violations.join("; ")}><Badge variant="neg">拦截</Badge></span>
                                ) : <span className="text-text-3">-</span>}</Td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </Table>
                    </CardBody>
                  </Card>
                )}
              </section>
              )}
              {activeTab === "risk" && (
              <section>
                {result.ic_review && <ICReviewInline ic={result.ic_review} />}
                {result.thesis_tracker?.health && <ThesisHealthInline health={result.thesis_tracker.health} />}
                {result.ic_review && result.ic_review.hurdles.length > 0 && (
                  <Card className="mb-4">
                    <CardHeader title="硬性门槛" />
                    <CardBody className="p-0">
                      <Table>
                        <thead><tr><Th>门槛</Th><Th>观测值</Th><Th>阈值</Th><Th>结果</Th></tr></thead>
                        <tbody>
                          {result.ic_review.hurdles.map((h) => (
                            <tr key={h.hurdle_id}>
                              <Td>{h.name}</Td>
                              <Td className="font-mono">{h.observed !== null ? h.observed : "-"}</Td>
                              <Td>{h.operator} {h.threshold}</Td>
                              <Td>{h.passed === null ? <Badge variant="neutral">无法判断</Badge> :
                                h.passed ? <Badge variant="pos">通过</Badge> : <Badge variant="neg">未通过</Badge>}</Td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </CardBody>
                  </Card>
                )}
                {gatedOut.length > 0 && (
                  <details className="bg-surface border border-border rounded-lg p-4">
                    <summary className="cursor-pointer font-semibold text-text-2">被门禁拦截的基金（{gatedOut.length}）</summary>
                    <Table className="mt-3">
                      <thead><tr><Th>代码</Th><Th>名称</Th><Th>匹配度</Th><Th>拦截原因</Th></tr></thead>
                      <tbody>
                        {gatedOut.map((f) => (
                          <tr key={f.fund_code}>
                            <Td className="font-mono text-xs">{f.fund_code}</Td>
                            <Td>{f.fund_name}</Td>
                            <Td>{fmt(f.match_pct, "%")}</Td>
                            <Td className="text-neg text-xs">{(f.gate?.violations ?? []).join("; ")}</Td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </details>
                )}
                {(result as { step5_portfolio?: { risk_review?: { verdict?: string; violations?: Array<{ type: string; severity: string; detail: string }>; recommendations?: string[] } } }).step5_portfolio?.risk_review && (() => {
                  const rr = (result as { step5_portfolio?: { risk_review?: { verdict?: string; violations?: Array<{ type: string; severity: string; detail: string }>; recommendations?: string[] } } }).step5_portfolio!.risk_review!;
                  const verdictColor = rr.verdict === "pass" ? "var(--color-pos, #16a34a)" : rr.verdict === "warn" ? "var(--color-warn, #d97706)" : "var(--color-neg, #dc2626)";
                  const verdictText = rr.verdict === "pass" ? "通过" : rr.verdict === "warn" ? "警告" : "不通过";
                  return (
                    <Card className="mt-4">
                      <CardHeader title="组合级二次裁决"
                        subtitle={`裁决结果：${verdictText}（基于信心强度 ${conviction}）`} />
                      <CardBody>
                        <div className="mb-3 px-3 py-2 rounded-lg" style={{ background: `${verdictColor}15`, border: `1px solid ${verdictColor}40` }}>
                          <span className="text-sm font-semibold" style={{ color: verdictColor }}>{verdictText}</span>
                          <span className="text-xs text-text-3 ml-2">{rr.violations?.length || 0} 项违规</span>
                        </div>
                        {rr.violations && rr.violations.length > 0 && (
                          <div className="space-y-1.5 mb-3">
                            {rr.violations.map((v, i) => (
                              <div key={i} className="flex items-start gap-2 text-sm">
                                <span className="shrink-0" style={{ color: v.severity === "fail" ? "var(--color-neg, #dc2626)" : "var(--color-warn, #d97706)" }}>
                                  {v.severity === "fail" ? "✕" : "⚠"}
                                </span>
                                <span className="text-text-2">{v.detail}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {rr.recommendations && rr.recommendations.length > 0 && (
                          <div className="border-t border-border pt-3">
                            <div className="text-xs text-text-3 mb-1">调整建议：</div>
                            <ul className="text-sm text-text-2 m-0 pl-5 list-disc space-y-0.5">
                              {rr.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                            </ul>
                          </div>
                        )}
                      </CardBody>
                    </Card>
                  );
                })()}
              </section>
              )}
              {activeTab === "portfolio" && (
              <>
              <section>
                {pf && (
                  <div className="mb-4">
                    <RadarChartViz data={[
                      { metric: "匹配度", value: Number(pf.top_funds?.[0]?.match_pct ?? 0) },
                      { metric: "估值安全", value: 100 - Number(fundMatches[0]?.valuation?.weighted_val_pct ?? 50) },
                      { metric: "分散度", value: Math.min(100, (pf.top_funds?.length ?? 0) * 20) },
                      { metric: "防守覆盖", value: pf.defense_weight ?? 0 },
                      { metric: "流动性", value: 80 },
                    ]} />
                  </div>
                )}
                {pf && pf.top_funds && pf.top_funds.length > 0 ? (
                  <Card className="mb-4">
                    <CardHeader title="组合草案" subtitle={pf.rationale} />
                    <CardBody>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center mb-4">
                        <DonutChart
                          data={[
                            { name: "认知仓位", value: pf.suggested_weight || 0, color: "#3b82f6" },
                            { name: "防守仓位", value: pf.defense_weight || 0, color: "#10b981" },
                            { name: "现金", value: pf.cash_pct || 0, color: "#e5e7eb" },
                          ].filter((d) => d.value > 0)}
                          size={160} innerRadius={42} outerRadius={65}
                          centerLabel="总投资" centerValue={`${(pf.total_invested || 0).toFixed(0)}%`} />
                        <div className="space-y-3">
                          <ProgressBar value={pf.suggested_weight} variant="accent" label="认知仓位" />
                          <ProgressBar value={pf.defense_weight} variant="pos" label="防守仓位" />
                          <ProgressBar value={pf.cash_pct} variant="neutral" label="现金" />
                        </div>
                      </div>
                      <Table>
                        <thead><tr><Th>代码</Th><Th>名称</Th><Th className="text-right">匹配度</Th></tr></thead>
                        <tbody>
                          {pf.top_funds.map((f, i) => {
                            const ff = f as Record<string, unknown>;
                            const code = String(ff.fund_code ?? "");
                            return (
                              <tr key={i} onClick={() => { if (code) setSelectedFundCode(code); }} className="cursor-pointer hover:bg-surface-2">
                                <Td className="font-mono text-xs">{code}</Td>
                                <Td>{String(ff.fund_name ?? "")}</Td>
                                <Td className="text-right font-semibold text-accent">{fmt(ff.match_pct as number | null, "%")}</Td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </Table>
                      <div className="mt-3 flex justify-end">
                        <button type="button" disabled={exporting} onClick={() => {
                          setExporting(true);
                          exportCognition(result).catch(() => {}).finally(() => setExporting(false));
                        }} className="px-4 py-2 text-xs bg-accent text-white border border-accent rounded hover:opacity-90 disabled:opacity-50">
                          {exporting ? "导出中…" : "导出 Excel"}
                        </button>
                      </div>
                    </CardBody>
                  </Card>
                ) : (
                  <div className="p-4 bg-warn-soft border border-warn/30 rounded-lg text-sm text-warn-text mb-4">
                    研究草案不可执行：候选为空时不展示可执行组合。
                  </div>
                )}
                {result.investment_memo && (
                  <details className="bg-surface border border-border rounded-lg p-4 mb-4" open>
                    <summary className="cursor-pointer font-semibold">投资备忘录（含场景分析）</summary>
                    <div className="mt-3"><MemoView memo={result.investment_memo} /></div>
                  </details>
                )}
              </section>

              {/* 7. Pipeline 详情（折叠） */}
              {pipelineResult && (
                <details className="bg-surface border border-border rounded-lg p-4">
                  <summary className="cursor-pointer font-semibold">Pipeline 阶段详情（{pipelineResult.run.run_id}）</summary>
                  <div className="mt-3 space-y-2 text-xs">
                    {pipelineResult.run.steps.map((step) => (
                      <div key={step.stage} className="flex justify-between items-center p-2 bg-surface-2 rounded">
                        <span className="font-semibold">{PIPELINE_STAGE_LABELS[step.stage] ?? step.stage}</span>
                        <div className="flex items-center gap-2">
                          <Badge variant={PIPELINE_STATUS_VARIANT[step.status] ?? "neutral"}>{PIPELINE_STATUS_LABEL[step.status] ?? step.status}</Badge>
                          {step.error && <span className="text-neg truncate max-w-[40%]">{step.error}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {/* Inbox 展开区域 */}
              {inbox && inbox.open_items > 0 && (
                <details className="bg-surface border border-border rounded-lg p-4" open>
                  <summary className="cursor-pointer font-semibold flex items-center gap-3">
                    Inbox 决策队列
                    <div className="flex gap-1">
                      {inbox.high_severity > 0 && <Badge variant="neg">高 {inbox.high_severity}</Badge>}
                      {inbox.medium_severity > 0 && <Badge variant="warn">中 {inbox.medium_severity}</Badge>}
                      {inbox.low_severity > 0 && <Badge variant="neutral">低 {inbox.low_severity}</Badge>}
                    </div>
                    <span className="text-xs text-text-3 ml-auto">共 {inbox.open_items} 项</span>
                  </summary>
                  <div className="mt-3 space-y-2">
                    {inbox.items.map((item: AttentionItem) => (
                      <div key={item.item_id} className="p-3 bg-surface-2 rounded border-l-4 border-border">
                        <div className="flex justify-between items-start gap-2 mb-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold">{item.title}</span>
                            <Badge variant={item.severity === "high" ? "neg" : item.severity === "medium" ? "warn" : "neutral"}>
                              {item.severity === "high" ? "高" : item.severity === "medium" ? "中" : "低"}
                            </Badge>
                          </div>
                          {item.fund_code && <span className="text-xs text-text-3 font-mono">{item.fund_code}</span>}
                        </div>
                        <p className="text-xs text-text-2 leading-relaxed">{item.body}</p>
                      </div>
                    ))}
                  </div>
                </details>
              )}
              </>
              )}
            </div>

            {/* 详情栏（sticky） */}
            <aside className="lg:col-span-4 lg:sticky lg:top-12 space-y-4">
              <FundDetailInline fund={selectedFund} />
              {selectedFund && !monitorFundCode && (
                <button type="button" onClick={() => setMonitorFundCode(selectedFund.fund_code)}
                  className="w-full px-4 py-2 text-sm text-accent border border-accent/30 rounded hover:bg-accent-soft">
                  查看监控面板
                </button>
              )}
              {monitorFundCode && (
                <details className="bg-surface border border-border rounded-lg p-4" open>
                  <summary className="cursor-pointer font-semibold flex items-center justify-between">
                    <span>监控面板</span>
                    <button type="button" onClick={(e) => { e.preventDefault(); e.stopPropagation(); setMonitorFundCode(null); }}
                      className="text-xs text-text-3 hover:text-neg">关闭</button>
                  </summary>
                  <MonitorInline fundCode={monitorFundCode} overview={monitorData}
                    loading={monitorLoading} error={monitorError} />
                </details>
              )}
              {evidencePacket && (
                <details className="bg-surface border border-border rounded-lg p-4">
                  <summary className="cursor-pointer font-semibold">证据包</summary>
                  <div className="mt-3 space-y-3">
                    {evidencePacket.evidence_bundle && (
                      <div className="p-2 bg-surface-2 rounded text-xs">
                        <div className="text-text-3 mb-1">Bundle ID</div>
                        <div className="font-mono font-semibold break-all">{evidencePacket.evidence_bundle.bundle_id}</div>
                        <div className="text-text-3 mt-1">来源数 {evidencePacket.evidence_bundle.source_ids.length}</div>
                      </div>
                    )}
                    {evidencePacket.evidence_sources.slice(0, 5).map((src) => (
                      <div key={src.source_id} className="p-2 bg-surface-2 rounded text-xs">
                        <div className="flex items-center gap-1.5 mb-1">
                          <Badge variant="accent">{src.kind}</Badge>
                          <span className="font-semibold flex-1 truncate">{src.title}</span>
                        </div>
                        <div className="flex justify-between text-text-3 text-[11px]">
                          <span>{src.publisher}</span>
                          <span className="font-mono truncate ml-2">{src.content_hash.slice(0, 12)}…</span>
                        </div>
                      </div>
                    ))}
                    {evidencePacket.data_quality_notes.length > 0 && (
                      <div className="text-xs">
                        <div className="text-warn-text font-semibold mb-1">数据缺口</div>
                        {evidencePacket.data_quality_notes.map((note, i) => (
                          <div key={i} className="text-text-2 py-0.5">- {note}</div>
                        ))}
                      </div>
                    )}
                  </div>
                </details>
              )}
            </aside>
          </div>
        </div>
      </CognitionErrorBoundary>
    );
  }

  return null;
}

// === 健康标签映射 ===
function healthVariant(label: string): "pos" | "warn" | "neg" | "neutral" {
  if (label === "Intact") return "pos";
  if (label === "Watching") return "warn";
  if (label === "Broken") return "neg";
  return "neutral";
}

// === KPI 单格（顶部 4 列） ===
function KpiTile({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="p-6 bg-surface border border-border rounded-lg">
      <div className="text-xs uppercase tracking-wide text-text-3 mb-2">{label}</div>
      {children}
    </div>
  );
}

// === 证据列表（支持 / 反对） ===
function EvidenceList({ kind, title, count, items, extra }: {
  kind: "pos" | "neg"; title: string; count: number; items: { claim: string; context?: string }[]; extra: number;
}) {
  const dotClass = kind === "pos" ? "bg-pos" : "bg-neg";
  const textClass = kind === "pos" ? "text-pos" : "text-neg";
  const borderClass = kind === "pos" ? "border-l-pos" : "border-l-neg";
  return (
    <div className={`p-6 bg-surface border border-border rounded-lg mb-4 border-l-4 ${borderClass}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
        <span className={`text-xs uppercase tracking-wide ${textClass} font-semibold`}>{title}</span>
        <span className="text-[11px] text-text-3">({count})</span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-text-3 m-0">暂无{title}</p>
      ) : (
        <ul className="space-y-2 m-0 p-0 list-none">
          {items.map((ev, i) => (
            <li key={i} className="text-sm leading-relaxed">
              <span className="text-text-3 mr-2">{i + 1}.</span>
              <span className="font-medium">{ev.claim}</span>
              {ev.context && <span className="text-text-2 ml-2">— {ev.context}</span>}
            </li>
          ))}
        </ul>
      )}
      {extra > 0 && <p className="text-[11px] text-text-3 mt-3">还有 {extra} 条未展开</p>}
    </div>
  );
}

// === 多空辩论（Bull vs Bear 对抗性分析） ===
function DebateView({ debate }: { debate: DebateRound[] }) {
  if (!debate || debate.length === 0) return null;
  return (
    <Card className="mb-4">
      <CardHeader title="多空辩论" subtitle="Bull vs Bear 对抗性分析（借鉴 TradingAgents）" />
      <CardBody className="space-y-3">
        {debate.map((round) => (
          <div key={round.round} className="border border-border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Badge variant="accent">第 {round.round} 轮</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Bull argument */}
              <div className="p-3 bg-pos-soft border-l-4 border-pos rounded-r">
                <div className="text-xs font-semibold text-pos mb-1">BULL 看多</div>
                <div className="text-sm">{round.bull_argument?.claim ?? "无论点"}</div>
                {round.bull_argument?.source && <div className="text-[11px] text-text-3 mt-1">来源：{round.bull_argument.source}</div>}
                {round.bull_argument?.context && <div className="text-xs text-text-3 mt-1">{round.bull_argument.context}</div>}
              </div>
              {/* Bear rebuttal */}
              <div className="p-3 bg-neg-soft border-l-4 border-neg rounded-r">
                <div className="text-xs font-semibold text-neg mb-1">BEAR 反驳</div>
                <div className="text-sm">{round.bear_rebuttal?.claim ?? "无反驳"}</div>
                {round.bear_rebuttal?.source && <div className="text-[11px] text-text-3 mt-1">来源：{round.bear_rebuttal.source}</div>}
                {round.bear_rebuttal?.context && <div className="text-xs text-text-3 mt-1">{round.bear_rebuttal.context}</div>}
              </div>
              {/* Bull response */}
              <div className="p-3 bg-accent-soft border-l-4 border-accent rounded-r">
                <div className="text-xs font-semibold text-accent mb-1">BULL 回应</div>
                <div className="text-sm">{round.bull_response?.claim ?? "无回应"}</div>
                {round.bull_response?.source && <div className="text-[11px] text-text-3 mt-1">来源：{round.bull_response.source}</div>}
                {round.bull_response?.context && <div className="text-xs text-text-3 mt-1">{round.bull_response.context}</div>}
              </div>
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

// === 基金详情（取代 FundDetailPanel） ===
function FundDetailInline({ fund }: { fund: CognitionResponse["step4_fund_matches"][number] | null }) {
  if (!fund) {
    return (
      <div className="p-6 bg-surface border border-border border-dashed rounded-lg text-center text-text-3 text-sm">
        选择一只基金查看详情
      </div>
    );
  }
  const v = (fund.valuation ?? {}) as Record<string, unknown>;
  const mgr = fund.manager as Record<string, unknown> | null | undefined;
  const holdings = (fund.holdings ?? []) as Array<Record<string, unknown>>;
  const trend = (fund.trend ?? {}) as Record<string, unknown>;
  const gate = (fund.gate ?? {}) as Record<string, unknown>;
  const tenureDays = Number(mgr?.tenure_days ?? 0);
  const tenureLabel = tenureDays > 1825 ? "经验丰富（>5年）" : tenureDays < 365 ? "任职不足1年" : "任职1-5年";
  const gatePassed = gate?.passed;
  const gateLabel = gatePassed === true ? "全部通过" : gatePassed === false ? "被拦截" : "未评估";

  return (
    <Card>
      <CardBody>
        <div className="mb-4">
          <div className="text-base font-semibold leading-tight">{String(fund.fund_name ?? fund.fund_code)}</div>
          <div className="text-xs text-text-3 font-mono mt-1">{String(fund.fund_code)}</div>
        </div>
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wide text-text-3 mb-1">匹配度</div>
          <div className="text-3xl font-bold text-accent font-mono">{fmt(fund.match_pct, "%")}</div>
        </div>
        <div className="p-3 bg-surface-2 rounded mb-4">
          <div className="text-xs uppercase tracking-wide text-text-3 mb-1">估值门禁</div>
          <Badge variant={gatePassed === true ? "pos" : gatePassed === false ? "neg" : "neutral"}>{gateLabel}</Badge>
          {!gatePassed && Array.isArray(gate.violations) && (gate.violations as string[]).length > 0 && (
            <div className="text-xs text-neg mt-2 leading-relaxed">{(gate.violations as string[]).join("；")}</div>
          )}
        </div>
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wide text-text-3 mb-2">估值</div>
          {v.weighted_val_pct != null && (
            <div className="mb-3">
              <ValuationGauge percentile={Number(v.weighted_val_pct)} />
            </div>
          )}
          <div className="space-y-1.5">
            <DetailRow label="加权 PE" value={fmt(v.weighted_pe as number | null)} />
            <DetailRow label="估值分位" value={fmt(v.weighted_val_pct as number | null, "%")} />
            <DetailRow label="PEG" value={fmt(v.peg as number | null)} />
            <DetailRow label="Price-in" value={v.price_in_years != null ? `${fmt(v.price_in_years as number)}年` : "-"} />
            {v.pe_premium_pct != null && (
              <DetailRow label="vs 同行 PE" value={`${(v.pe_premium_pct as number) > 0 ? "+" : ""}${fmt(v.pe_premium_pct as number)}%`} />
            )}
          </div>
        </div>
        {holdings.length > 0 && (
          <div className="mb-4">
            <div className="text-xs uppercase tracking-wide text-text-3 mb-2">持仓（前 5）</div>
            <div className="space-y-1">
              {holdings.slice(0, 5).map((h, i) => (
                <div key={i} className="flex justify-between text-xs">
                  <span className="truncate mr-2">{String(h.stock_name ?? h.stock_code)}</span>
                  <span className="font-mono text-text-2">{fmt(h.weight as number, "%")}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wide text-text-3 mb-1">趋势</div>
          <div className="text-sm">
            {String(trend.trend ?? "-")}
            {trend.change_pct != null && <span className="text-text-3 ml-1">({fmt(trend.change_pct as number, "%")})</span>}
          </div>
        </div>
        {mgr && (
          <div>
            <div className="text-xs uppercase tracking-wide text-text-3 mb-1">基金经理</div>
            <div className="text-sm">
              <div className="font-semibold">{String(mgr.name ?? "-")}</div>
              <div className="text-xs text-text-3 mt-1">{fmt(tenureDays / 365, "年")} · {tenureLabel}</div>
              {mgr.return_pct != null && (
                <div className={`text-xs font-mono mt-1 ${(mgr.return_pct as number) > 0 ? "text-pos" : "text-neg"}`}>
                  任职回报 {fmt(mgr.return_pct as number, "%")}
                </div>
              )}
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// 单行详情
function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-text-3">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}

// === 监控面板（取代 MonitorPanel） ===
function MonitorInline({ overview, loading, error }: {
  fundCode: string; overview: MonitorOverview | null; loading: boolean; error: string | null;
}) {
  if (loading) return <div className="mt-3 text-xs text-text-3">加载监控数据…</div>;
  if (error) return <div className="mt-3 text-xs text-neg">监控加载失败：{error}</div>;
  if (!overview) return <div className="mt-3 text-xs text-text-3">暂无监控数据</div>;
  return (
    <div className="mt-3 space-y-3 text-xs">
      <div className="text-text-3">截至 {overview.as_of_today}</div>
      {overview.risk_signals.length > 0 && (
        <div className="space-y-1">
          {overview.risk_signals.slice(0, 5).map((s) => (
            <div key={s.code} className={`p-2 rounded bg-surface-2 border-l-2 ${
              s.level === "critical" ? "border-l-neg" : s.level === "warning" ? "border-l-warn" : "border-l-accent"}`}>
              <div className="font-semibold">{s.title}</div>
              <div className="text-text-2 mt-0.5">{s.detail}</div>
            </div>
          ))}
        </div>
      )}
      {overview.valuation_history.length > 0 && (
        <details open>
          <summary className="cursor-pointer text-text-2 font-semibold">估值历史（{overview.valuation_history.length} 期）</summary>
          <Table className="mt-2">
            <thead><tr><Th>日期</Th><Th>PE</Th><Th>分位</Th></tr></thead>
            <tbody>
              {overview.valuation_history.slice(0, 5).map((h) => (
                <tr key={h.run_id}>
                  <Td className="text-xs">{h.as_of_date}</Td>
                  <Td className="font-mono text-xs">{h.weighted_pe != null ? h.weighted_pe.toFixed(1) : "—"}</Td>
                  <Td className="font-mono text-xs">{h.weighted_val_pct != null ? `${h.weighted_val_pct.toFixed(0)}%` : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </details>
      )}
    </div>
  );
}

// === IC 审查内联（三支柱） ===
function ICReviewInline({ ic }: { ic: ICReview }) {
  const isPass = ic.verdict === "pass";
  const pillarLabel: Record<string, string> = { conviction: "投资信心", constitution_fit: "策略适配", data_quality: "数据质量" };
  const pillarWeight = (name: string) => name === "conviction" ? "45%" : name === "constitution_fit" ? "35%" : "20%";
  return (
    <Card className="mb-4">
      <CardHeader title="投决会审查" subtitle={isPass ? "通过" : "未通过"}
        action={
          <div className="flex items-center gap-2">
            {ic.is_override && <Badge variant="warn">已覆盖</Badge>}
            <span className={`text-2xl font-bold font-mono ${isPass ? "text-pos" : "text-neg"}`}>{isPass ? "PASS" : "FAIL"}</span>
          </div>
        } />
      <CardBody className="space-y-4">
        <ProgressBar value={ic.gate_score} variant={isPass ? "pos" : "neg"} label={`Gate Score vs Cutoff ${ic.cutoff.toFixed(0)}`} />
        {ic.fail_reason && (
          <div className="p-3 bg-neg-soft border border-neg/30 rounded text-sm text-neg-text">{ic.fail_reason}</div>
        )}
        <div>
          <div className="text-xs uppercase tracking-wide text-text-3 font-semibold mb-2">评分支柱</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {ic.pillars.map((p) => {
              const weak = p.score < 25;
              const variant = weak ? "neg" : p.score >= 70 ? "pos" : "warn";
              return (
                <div key={p.name} className={`p-3 bg-surface-2 rounded-lg border ${weak ? "border-neg/40" : "border-transparent"}`}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-semibold">{pillarLabel[p.name] ?? p.name}</span>
                    <Badge variant="neutral">{pillarWeight(p.name)}</Badge>
                  </div>
                  <ProgressBar value={p.score} variant={variant} showValue={true} />
                </div>
              );
            })}
          </div>
        </div>
        {ic.is_override && ic.override_rationale && (
          <div className="p-3 bg-warn-soft border border-warn/30 rounded text-sm text-warn-text">
            覆盖原因：{ic.override_rationale}{ic.prior_verdict && `（原裁决：${ic.prior_verdict}）`}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// === 假设健康监控内联 ===
function ThesisHealthInline({ health }: { health: NonNullable<NonNullable<CognitionResponse["thesis_tracker"]>["health"]> }) {
  const variant = healthVariant(health.health_label);
  const statusVariant = (s: string): "pos" | "warn" | "neg" | "neutral" =>
    s === "intact" ? "pos" : s === "watch" ? "warn" : s === "broken" ? "neg" : "neutral";
  const statusLabel = (s: string) =>
    s === "intact" ? "正常" : s === "watch" ? "观察" : s === "broken" ? "已破坏" : s === "data_gap" ? "数据缺失" : "未知";
  return (
    <Card className="mb-4">
      <CardHeader title="假设健康监控" />
      <CardBody>
        <div className="flex items-center gap-3 mb-4">
          <Badge variant={variant} className="text-base px-3 py-1">{health.health_label}</Badge>
          <span className="text-xs text-text-3">正常 {health.intact} · 观察 {health.watch} · 破坏 {health.broken} · 数据缺失 {health.data_gap}</span>
        </div>
        <div className="space-y-2">
          {health.items.slice(0, 5).map((item) => {
            const sv = statusVariant(item.status);
            const borderClass = sv === "pos" ? "border-l-pos" : sv === "warn" ? "border-l-warn" : sv === "neg" ? "border-l-neg" : "border-l-border-2";
            return (
              <div key={item.item_id} className={`p-3 bg-surface-2 rounded border-l-4 ${borderClass}`}>
                <div className="flex justify-between items-start gap-2 mb-1">
                  <span className="text-sm font-semibold">{item.title}</span>
                  <Badge variant={statusVariant(item.status)}>{statusLabel(item.status)}</Badge>
                </div>
                <div className="text-xs text-text-3">
                  {item.metric ?? "-"}：{item.last_value !== null ? item.last_value : "-"} {item.comparator} {item.threshold !== null ? item.threshold : "-"}
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

// === 备忘录视图（决策标签 + 七段式 + 场景） ===
function MemoView({ memo }: { memo: NonNullable<CognitionResponse["investment_memo"]> }) {
  const dc = DECISION_CONFIG[memo.decision] ?? DECISION_CONFIG.needs_more_evidence;
  const scenarioData = [
    { scenario: "悲观", return: memo.scenario.bear.return, probability: memo.scenario.bear.probability, color: "#dc2626" },
    { scenario: "基准", return: memo.scenario.base.return, probability: memo.scenario.base.probability, color: "#2563eb" },
    { scenario: "乐观", return: memo.scenario.bull.return, probability: memo.scenario.bull.probability, color: "#16a34a" },
  ];
  const expectedReturn = scenarioData.reduce((acc, s) => acc + (s.probability * s.return) / 100, 0);
  return (
    <>
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-text-3">投资决策</span>
          <Badge variant={dc.variant} className="text-sm px-3 py-1">{dc.label}</Badge>
        </div>
        <span className="text-xs text-text-3">生成于 {memo.generated_at}</span>
      </div>
      {memo.sections.map((section, idx) => (
        <Card key={section.section_id} className="mb-3">
          <CardHeader title={`${idx + 1}. ${section.title}`} subtitle={section.thesis} />
          <CardBody><p className="text-sm leading-relaxed m-0">{section.content}</p></CardBody>
        </Card>
      ))}
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
    </>
  );
}