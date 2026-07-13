import { useEffect, useState, Component, ReactNode } from "react";
import {
  fetchThemes,
  fetchDirectionLinks,
  postCognition,
  searchConcepts,
  postConceptCognition,
  searchStocks,
  postStockCognition,
  exportCognition,
  type ThemeInfo,
  type ChainLinkInfo,
  type CognitionResponse,
  type Evidence,
  type ConceptBoard,
  type DebateRound,
  type CognitionFeedback,
  type StockSearchResult,
} from "../api";
import { DonutChart, HorizontalBarChart, SkeletonCard } from "../charts";
import {
  KpiBar,
  ValuationQuad,
  SideNav,
  FundDetailPanel,
  useScrollSpy,
  ResearchBrief,
  EvidenceSummary,
  FundCandidatesTable,
  MonitorPanel,
  type EvidenceItem,
} from "../components/CognitionComponents";

const CERTAINTY_LABEL: Record<string, string> = { high: "高确定性", medium: "中确定性", low: "低确定性" };
const ELASTICITY_LABEL: Record<string, string> = { high: "高弹性", medium: "中弹性", low: "低弹性", very_high: "极高弹性" };
const GAP_LABEL: Record<string, string> = { positive: "正预期差", neutral: "中性", negative: "负预期差", unknown: "数据不足" };
const GAP_CLASS: Record<string, string> = { positive: "gap-positive", neutral: "gap-neutral", negative: "gap-negative", unknown: "gap-unknown" };
const TREND_LABEL: Record<string, string> = { increasing: "↑ 加仓", decreasing: "↓ 减仓", stable: "→ 持平", insufficient_data: "数据不足" };

function fmt(v: number | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "-";
  return Number.isInteger(v) ? `${v}${suffix}` : `${v.toFixed(1)}${suffix}`;
}

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
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [direction, setDirection] = useState("");
  const [links, setLinks] = useState<ChainLinkInfo[]>([]);
  const [isCustom, setIsCustom] = useState(false);
  const [selectedLink, setSelectedLink] = useState<string | null>(null);
  const [conviction, setConviction] = useState("medium");
  const [result, setResult] = useState<CognitionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState("");
  const [conceptKeyword, setConceptKeyword] = useState("");
  const [conceptResults, setConceptResults] = useState<ConceptBoard[]>([]);
  const [conceptLoading, setConceptLoading] = useState(false);
  const [selectedFundCode, setSelectedFundCode] = useState<string | null>(null);
  const [stockKeyword, setStockKeyword] = useState("");
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [stockLoading, setStockLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  // 选基 v1：用户的"我的观点"文本（仅展示，不参与模型判定）
  const [beliefNote, setBeliefNote] = useState("");
  // 监控面板 v1：当前查看监控的基金
  const [monitorFundCode, setMonitorFundCode] = useState<string | null>(null);
  const [monitorData, setMonitorData] = useState<import("../api").MonitorOverview | null>(null);
  const [monitorLoading, setMonitorLoading] = useState(false);
  const [monitorError, setMonitorError] = useState<string | null>(null);

  // 监控面板 v1：异步加载
  useEffect(() => {
    if (!monitorFundCode) {
      setMonitorData(null);
      setMonitorError(null);
      return;
    }
    let cancelled = false;
    setMonitorLoading(true);
    setMonitorError(null);
    import("../api").then((m) =>
      m.fetchMonitorOverview(monitorFundCode).then(
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
      )
    );
    return () => {
      cancelled = true;
    };
  }, [monitorFundCode]);

  useEffect(() => {
    fetchThemes().then((r) => setThemes(r.themes)).catch(() => {});
  }, []);

  // 概念板块搜索
  useEffect(() => {
    if (!conceptKeyword.trim()) {
      setConceptResults([]);
      return;
    }
    setConceptLoading(true);
    const timer = setTimeout(() => {
      searchConcepts(conceptKeyword.trim())
        .then(setConceptResults)
        .catch(() => setConceptResults([]))
        .finally(() => setConceptLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [conceptKeyword]);

  // 个股搜索
  useEffect(() => {
    if (!stockKeyword.trim()) {
      setStockResults([]);
      return;
    }
    setStockLoading(true);
    const timer = setTimeout(() => {
      searchStocks(stockKeyword.trim())
        .then(setStockResults)
        .catch(() => setStockResults([]))
        .finally(() => setStockLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [stockKeyword]);

  // 用个股运行认知分析
  const pickStock = (stock: StockSearchResult) => {
    setLoading(true);
    setError(null);
    postStockCognition(stock.stock_code, stock.stock_name, conviction)
      .then((r) => {
        setResult(r as CognitionResponse);
        setDirection(`${stock.stock_name}（个股认知）`);
        setStep(3);
      })
      .catch(() => setError("个股分析失败"))
      .finally(() => setLoading(false));
  };

  // 用概念板块运行认知分析
  const pickConcept = (concept: ConceptBoard) => {
    setLoading(true);
    setError(null);
    postConceptCognition(concept.code, concept.name, conviction)
      .then((r) => {
        setResult(r);
        setDirection(concept.name);
        setStep(3);
      })
      .catch(() => setError("概念分析失败"))
      .finally(() => setLoading(false));
  };

  // 阶段1 -> 阶段2
  const pickDirection = (dir: string) => {
    setDirection(dir);
    setStep(2);
    setLinks([]);
    setSelectedLink(null);
    setLoading(true);
    fetchDirectionLinks(dir)
      .then((r) => {
        setLinks(r.links);
        setIsCustom(r.is_custom);
      })
      .catch(() => setError("加载产业链失败"))
      .finally(() => setLoading(false));
  };

  // 阶段2 -> 阶段3
  const analyze = () => {
    setLoading(true);
    setError(null);
    postCognition(direction, selectedLink ?? undefined, conviction)
      .then((r) => {
        setResult(r);
        setStep(3);
      })
      .catch(() => setError("分析失败，请重试"))
      .finally(() => setLoading(false));
  };

  const reset = () => {
    setStep(1);
    setDirection("");
    setResult(null);
    setLinks([]);
    setSelectedLink(null);
    setCustomInput("");
  };

  // useScrollSpy 必须在所有条件 return 之前调用，避免 Hooks 顺序变化
  const sectionIds = ["sec-brief", "sec-evidence", "sec-candidates", "sec-portfolio"];
  const scrolled = useScrollSpy(sectionIds);

  // === 阶段1：选方向 ===
  if (step === 1) {
    return (
      <div className="main cognition-form">
        <h2 style={{ marginBottom: "4px" }}>你相信什么？</h2>
        <p style={{ color: "var(--text-3)", marginBottom: "24px" }}>
          选择一个方向，系统帮你从认知推导到基金配置
        </p>

        <div className="cognition-direction-grid" role="listbox" aria-label="预设主题">
          {themes.map((t) => (
            <button
              key={t.key}
              type="button"
              className="card theme-card cognition-direction-card"
              onClick={() => pickDirection(t.key)}
              aria-label={`选择方向：${t.name}`}
            >
              <div style={{ fontWeight: 600, marginBottom: "6px" }}>{t.name}</div>
              <div style={{ fontSize: "13px", color: "var(--text-2)" }}>{t.belief}</div>
            </button>
          ))}
        </div>

        <div style={{ marginTop: "24px" }}>
          <label htmlFor="cognition-concept-kw" style={{ fontSize: "13px", color: "var(--text-3)", marginBottom: "8px" }}>
            搜索概念板块（300+主题动态匹配）：
          </label>
          <input
            id="cognition-concept-kw"
            className="custom-direction-input"
            style={{ width: "100%" }}
            value={conceptKeyword}
            onChange={(e) => setConceptKeyword(e.target.value)}
            placeholder="输入关键词搜索，如：AI、芯片、创新药、白酒、新能源..."
            aria-label="概念板块搜索关键词"
          />
          {conceptLoading && <p style={{ fontSize: "13px", color: "var(--text-3)", marginTop: "4px" }}>搜索中...</p>}
          {conceptResults.length > 0 && (
            <div className="concept-search-results">
              {conceptResults.map((c) => (
                <div
                  key={c.code}
                  className="card concept-result-item"
                  onClick={() => pickConcept(c)}
                >
                  <div style={{ fontWeight: 600 }}>{c.name}</div>
                  <div style={{ fontSize: "13px", color: "var(--text-2)" }}>{c.stock_count} 只成分股</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginTop: "24px" }}>
          <label htmlFor="cognition-stock-kw" style={{ fontSize: "13px", color: "var(--text-3)", marginBottom: "8px" }}>
            搜索个股（找持有该股票占比最高的基金）：
          </label>
          <input
            id="cognition-stock-kw"
            className="custom-direction-input"
            style={{ width: "100%" }}
            value={stockKeyword}
            onChange={(e) => setStockKeyword(e.target.value)}
            placeholder="输入股票名称或代码，如：贵州茅台、中际旭创、寒武纪..."
            aria-label="个股搜索关键词"
          />
          {stockLoading && <p style={{ fontSize: "13px", color: "var(--text-3)", marginTop: "4px" }}>搜索中...</p>}
          {stockResults.length > 0 && (
            <div className="concept-search-results">
              {stockResults.map((s) => (
                <div
                  key={s.stock_code}
                  className="card concept-result-item"
                  onClick={() => pickStock(s)}
                >
                  <div style={{ fontWeight: 600 }}>
                    {s.stock_name}
                    <span style={{ fontSize: "12px", color: "var(--text-3)", marginLeft: "8px" }}>{s.stock_code}</span>
                  </div>
                  <div style={{ fontSize: "13px", color: "var(--text-2)" }}>
                    {s.fund_count} 只基金持有
                    {s.pe && ` · PE ${s.pe}`}
                    {s.val_pct != null && ` · 分位 ${s.val_pct}%`}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginTop: "24px" }}>
          <label htmlFor="cognition-custom" style={{ fontSize: "13px", color: "var(--text-3)", marginBottom: "8px" }}>
            或者输入你关注的方向：
          </label>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              id="cognition-custom"
              className="custom-direction-input"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && customInput.trim() && pickDirection(customInput.trim())}
              placeholder="例如：新能源、军工、人形机器人..."
              aria-label="自定义方向"
            />
            <button
              type="button"
              className="btn"
              disabled={!customInput.trim()}
              onClick={() => pickDirection(customInput.trim())}
            >
              确认
            </button>
          </div>
        </div>

        {/* v1 选基："我的观点" 文本框（仅展示，不参与模型判定） */}
        <div style={{ marginTop: "24px" }}>
          <label htmlFor="cognition-belief-note" style={{ fontSize: "13px", color: "var(--text-3)", marginBottom: "8px" }}>
            我的观点（可选，1000 字内，仅在结果页研究简报中显示）：
          </label>
          <textarea
            id="cognition-belief-note"
            className="custom-direction-input"
            style={{ width: "100%", minHeight: "60px", fontFamily: "inherit", resize: "vertical" }}
            value={beliefNote}
            onChange={(e) => setBeliefNote(e.target.value.slice(0, 1000))}
            placeholder="例如：受益于国产替代 + 下游需求扩张 + 估值合理..."
            aria-describedby="belief-note-help"
          />
          <div id="belief-note-help" style={{ fontSize: "11px", color: "var(--text-3)", marginTop: "4px" }}>
            观点只作为研究简报显示，不影响现有引擎判定
          </div>
        </div>
      </div>
    );
  }

  // === 阶段2：选环节+信心 ===
  if (step === 2) {
    return (
      <div className="main">
        <div className="cognition-back-link" onClick={reset}>← 换方向</div>
        <h2 style={{ marginBottom: "4px" }}>{direction}</h2>
        <p style={{ color: "var(--text-3)", marginBottom: "20px" }}>
          在这个产业链里，你最相信哪个环节会先受益？
        </p>

        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <SkeletonCard lines={1} />
            <SkeletonCard lines={2} />
            <SkeletonCard lines={2} />
          </div>
        )}

        {!loading && links.length === 0 && isCustom && (
          <p style={{ color: "var(--text-2)" }}>
            未找到预设产业链，系统将自动分析该方向。
          </p>
        )}

        {!loading && links.length > 0 && (
          <div className="link-option-list">
            <div
              className={`link-option ${selectedLink === null ? "selected" : ""}`}
              onClick={() => setSelectedLink(null)}
            >
              <div className="link-option-head">
                <span className="link-option-name">我全相信</span>
              </div>
              <div className="link-option-desc">分析整个产业链，找出预期差最好的环节</div>
            </div>

            {links.map((link) => (
              <div
                key={link.name}
                className={`link-option ${selectedLink === link.name ? "selected" : ""}`}
                onClick={() => setSelectedLink(link.name)}
              >
                <div className="link-option-head">
                  <span className="link-option-name">{link.name}</span>
                  <span className={`link-tag cert-${link.certainty}`}>{CERTAINTY_LABEL[link.certainty] ?? link.certainty}</span>
                  <span className={`link-tag elastic-${link.elasticity}`}>{ELASTICITY_LABEL[link.elasticity] ?? link.elasticity}</span>
                </div>
                <div className="link-option-logic">{link.benefit_logic}</div>
                {link.stocks.length > 0 && (
                  <div className="link-option-stocks">{link.stocks.join("、")}</div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && (
          <div style={{ marginTop: "24px" }}>
            <div style={{ fontSize: "13px", color: "var(--text-3)", marginBottom: "8px" }}>你的信心：</div>
            <div className="conviction-row">
              {["low", "medium", "high"].map((c) => (
                <button
                  key={c}
                  className={`conviction-btn ${conviction === c ? "selected" : ""}`}
                  onClick={() => setConviction(c)}
                >
                  {c === "low" ? "低" : c === "medium" ? "中" : "高"}
                </button>
              ))}
            </div>
          </div>
        )}

        {!loading && (
          <button
            className="btn"
            style={{ marginTop: "20px", width: "100%" }}
            onClick={analyze}
          >
            开始分析
          </button>
        )}
      </div>
    );
  }

  // === 阶段3：看结果 ===
  if (step === 3 && result) {
    const j = result.step1_judgment;
    const gap = result.step3_expectation_gap;
    const pf = result.step5_portfolio;

    // 选中基金（用于右侧详情）
    const selectedFund = selectedFundCode
      ? result.step4_fund_matches.find((f) => f.fund_code === selectedFundCode) ?? null
      : null;

    // 把 step3 + step5 validation 整理为支持/反对/待验证三类证据
    const evidenceItems: EvidenceItem[] = [];
    if (result.step5_validation) {
      for (const ev of result.step5_validation.supporting_evidence || []) {
        evidenceItems.push({
          category: "support",
          title: ev.claim || ev.source,
          detail: [ev.context, ev.source].filter(Boolean).join(" · "),
        });
      }
      for (const ev of result.step5_validation.opposing_evidence || []) {
        evidenceItems.push({
          category: "oppose",
          title: ev.claim || ev.source,
          detail: [ev.context, ev.source].filter(Boolean).join(" · "),
        });
      }
    }
    // step3 expectation gap 拆分为三类（设计 §4.2 反对/支持/待验证）
    if (gap) {
      if (gap.negative && gap.negative.length > 0) {
        evidenceItems.push({
          category: "oppose",
          title: `负向预期差（${gap.negative.length} 条）`,
          detail: gap.negative.map((c) => c.link_name).slice(0, 3).join("、"),
        });
      }
      if (gap.positive && gap.positive.length > 0) {
        evidenceItems.push({
          category: "support",
          title: `正向预期差（${gap.positive.length} 条）`,
          detail: gap.positive.map((c) => c.link_name).slice(0, 3).join("、"),
        });
      }
      if ((gap.neutral && gap.neutral.length > 0) || (!gap.best_link)) {
        evidenceItems.push({
          category: "pending",
          title: "中性 / 数据不足",
          detail: gap.summary || "需要等待更多数据验证",
        });
      }
    }

    // 候选状态映射（设计 §4.3）
    // portfolio.top_funds 为实际入选（build_portfolio 返回的 selected_funds）
    const hasCandidates = (pf?.top_funds?.length ?? 0) > 0;

    // 副作用：滚动到顶部章节
    const scrollToSection = (id: string) => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };

    return (
      <CognitionErrorBoundary>
        <div className="main">
          {/* 选择摘要 */}
          <div className="cognition-selection-bar">
          <div className="cognition-selection-info">
            <span>方向：<strong>{result.direction}</strong></span>
            <span className="cognition-selection-sep">|</span>
            <span>相信：<strong>{result.belief_link ?? "全部环节"}</strong></span>
            <span className="cognition-selection-sep">|</span>
            <span>信心：<strong>{result.conviction === "high" ? "高" : result.conviction === "low" ? "低" : "中"}</strong></span>
          </div>
          <div className="cognition-selection-actions">
            <button type="button" className="btn btn-sm" onClick={() => setStep(2)}>换环节</button>
            <button type="button" className="btn btn-sm" onClick={reset}>换方向</button>
          </div>
        </div>

        {/* aria-live 错误区域（设计 §5 + §7） */}
        <div role="alert" aria-live="assertive" className="cognition-aria-live">
          {error || ""}
        </div>

        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", margin: "16px 0" }}>
            <SkeletonCard lines={2} />
            <div style={{ display: "flex", gap: "12px" }}>
              <SkeletonCard lines={1} />
              <SkeletonCard lines={1} />
              <SkeletonCard lines={1} />
              <SkeletonCard lines={1} />
            </div>
            <SkeletonCard lines={4} />
            <SkeletonCard lines={4} />
          </div>
        )}
        {error && (
          <div role="alert" className="cognition-error" style={{ color: "var(--neg)", padding: "12px 16px", background: "var(--neg-soft)", borderRadius: "var(--r)", marginTop: "12px" }}>
            {error}
          </div>
        )}

        {/* 顶部KPI条（4个并排卡片） */}
        <KpiBar
          judgment={j}
          conviction={result.conviction ?? "medium"}
        />

        {/* v1 选基：研究简报（设计 §4.1 - §4.2） */}
        <div id="sec-brief">
          <ResearchBrief
            direction={result.direction}
            beliefNote={beliefNote || null}
            chainLabel={result.belief_link ?? null}
            convictionLabel={result.conviction === "high" ? "高" : result.conviction === "low" ? "低" : "中"}
            convictionLevel={result.conviction ?? "medium"}
            timeHorizon={j.time_horizon}
            valuationToleranceLabel={
              (j.valuation_tolerance === "high" ? "宽松" : j.valuation_tolerance === "low" ? "严格" : "中性")
            }
            asOfDate={null}
          />
        </div>

        {/* 三面板布局：左导航 / 中结果 / 右详情 */}
        <div className="cognition-three-panel fade-in-up">
          {/* 左侧导航：选基 v1 仅滚动/高亮，不写 ID 到基金状态 */}
          <SideNav
            active={scrolled}
            onSelect={(id) => scrollToSection(id)}
            sections={[
              { id: "sec-brief", label: "研究简报" },
              { id: "sec-evidence", label: "证据汇总", count: evidenceItems.length },
              {
                id: "sec-candidates",
                label: "研究候选",
                count: result.step4_fund_matches.length,
              },
              {
                id: "sec-portfolio",
                label: "组合草案",
                count: pf?.top_funds?.length ?? 0,
              },
            ]}
          />

          {/* 中间主内容 */}
          <div className="cognition-main-col">
            {/* 估值四维 */}
            <section id="sec-quad">
              <ValuationQuad
                expectationGap={gap}
                chain={result.step2_chain}
                fundMatches={result.step4_fund_matches}
              />
            </section>

            {/* 第1步：认知判断 */}
            <section id="sec-judgment" className="card" style={{ marginBottom: "12px" }}>
              <div style={{ fontWeight: 600, marginBottom: "8px" }}>认知判断</div>
              <p style={{ marginBottom: "8px" }}>{j.belief}</p>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <span className="judgment-badge">认知层次：{j.level}</span>
                <span className="judgment-badge">时间：{j.time_horizon}</span>
                <span className="judgment-badge">估值容忍：{j.valuation_tolerance}</span>
                <span className="judgment-badge">核心指标：{j.key_metric}</span>
              </div>
            </section>

            {/* 第2+3步：受益链路与预期差 */}
            <section id="sec-chain" className="card" style={{ marginBottom: "12px" }}>
              <div style={{ fontWeight: 600, marginBottom: "8px" }}>受益链路与预期差</div>
              <table className="table-v2">
                <thead>
                  <tr>
                    <th>环节</th>
                    <th>确定性</th>
                    <th>PE</th>
                    <th>增速</th>
                    <th>PEG</th>
                    <th>估值分位</th>
                    <th>预期差</th>
                    <th>评分</th>
                  </tr>
                </thead>
                <tbody>
                  {result.step2_chain.map((link) => (
                    <tr key={link.link_name}>
                      <td>{link.link_name}</td>
                      <td>{CERTAINTY_LABEL[link.certainty] ?? link.certainty}</td>
                      <td>{fmt(link.pe)}</td>
                      <td>{fmt(link.growth_pct, "%")}</td>
                      <td>{fmt(link.peg)}</td>
                      <td>{fmt(link.val_pct, "%")}</td>
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
              {gap.summary && (
                <p style={{ marginTop: "8px", color: "var(--text-2)", fontSize: "13px" }}>{gap.summary}</p>
              )}
            </section>

            {/* v1 选基：证据汇总（设计 §4.2 - §4.3） */}
            <section id="sec-evidence" style={{ marginBottom: "12px" }}>
              <EvidenceSummary items={evidenceItems} />
            </section>

            {/* v1 选基：研究候选（设计 §4.3） */}
            <section id="sec-candidates" style={{ marginBottom: "12px" }}>
              {result.step4_fund_matches.length === 0 ? (
                <div className="cognition-empty-state" role="status">
                  <div className="cognition-empty-state-title">当前没有合格研究候选</div>
                  <div className="cognition-empty-state-detail">
                    所有匹配基金都未通过估值门禁或数据缺失。建议调整方向、产业链环节或估值容忍度。
                  </div>
                </div>
              ) : (
                <FundCandidatesTable
                  funds={result.step4_fund_matches}
                  gatedOut={result.gated_out_funds || []}
                  onSelect={(code) => setSelectedFundCode(code)}
                  selectedCode={selectedFundCode}
                  onMonitor={(code) =>
                    setMonitorFundCode((prev) => (prev === code ? null : code))
                  }
                  monitoringCode={monitorFundCode}
                />
              )}
            </section>

            {/* 第4步：基金匹配 + 估值门禁 */}
            {result.step4_fund_matches.length > 0 && (
              <section id="sec-funds" className="card" style={{ marginBottom: "12px" }}>
                <div style={{ fontWeight: 600, marginBottom: "8px" }}>匹配基金</div>
                <table className="table-v2 cognition-fund-table">
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>匹配度</th>
                      <th>PE</th>
                      <th>估值分位</th>
                      <th>PEG</th>
                      <th>Price-in</th>
                      <th>vs同行</th>
                      <th>门禁</th>
                      <th>经理</th>
                      <th>趋势</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.step4_fund_matches.map((f) => {
                      const v = f.valuation as Record<string, unknown>;
                      const mgr = f.manager;
                      const isSelected = selectedFundCode === f.fund_code;
                      return (
                        <tr
                          key={f.fund_code}
                          className={isSelected ? "selected" : ""}
                          onClick={() => setSelectedFundCode(f.fund_code)}
                        >
                          <td>{f.fund_code}</td>
                          <td>{f.fund_name}</td>
                          <td>{fmt(f.match_pct, "%")}</td>
                          <td>{fmt(v.weighted_pe as number | null)}</td>
                          <td>{fmt(v.weighted_val_pct as number | null, "%")}</td>
                          <td>{fmt(v.peg as number | null)}</td>
                          <td>{v.price_in_years != null ? `${fmt(v.price_in_years as number)}年` : "-"}</td>
                          <td>
                            {v.pe_premium_pct != null ? (
                              <span style={{ color: (v.pe_premium_pct as number) > 20 ? "var(--neg)" : (v.pe_premium_pct as number) < -20 ? "var(--pos)" : "var(--text-2)" }}>
                                {(v.pe_premium_pct as number) > 0 ? "+" : ""}{fmt(v.pe_premium_pct as number)}%
                              </span>
                            ) : "-"}
                          </td>
                          <td>
                            {f.gate ? (
                              f.gate.passed ? (
                                <span style={{ color: "var(--pos)" }}>通过</span>
                              ) : (
                                <span style={{ color: "var(--neg)" }} title={f.gate.violations.join("; ")}>拦截</span>
                              )
                            ) : "-"}
                          </td>
                          <td>
                            {mgr ? (
                              <span style={{ fontSize: "12px" }}>
                                {mgr.name}
                                {mgr.tenure_days != null && (
                                  <span style={{ color: mgr.tenure_days > 1825 ? "var(--pos)" : mgr.tenure_days < 365 ? "var(--warn)" : "var(--text-3)" }}>
                                    {" "}{(mgr.tenure_days / 365).toFixed(1)}年
                                  </span>
                                )}
                              </span>
                            ) : "-"}
                          </td>
                          <td>{TREND_LABEL[f.trend.trend] ?? f.trend.trend}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <p style={{ fontSize: "11.5px", color: "var(--text-3)", marginTop: "6px" }}>
                  点击行查看完整证据链
                </p>
              </section>
            )}

            {/* 被门禁拦截的基金 */}
            {result.gated_out_funds && result.gated_out_funds.length > 0 && (
              <section id="sec-gated" className="card" style={{ marginBottom: "12px" }}>
                <div style={{ fontWeight: 600, marginBottom: "8px", color: "var(--text-2)" }}>
                  被估值门禁拦截的基金（{result.gated_out_funds.length}）
                </div>
                <table className="table-v2">
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>匹配度</th>
                      <th>拦截原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.gated_out_funds.map((f) => (
                      <tr key={f.fund_code}>
                        <td>{f.fund_code}</td>
                        <td>{f.fund_name}</td>
                        <td>{fmt(f.match_pct, "%")}</td>
                        <td style={{ color: "var(--neg)", fontSize: "13px" }}>{f.gate.violations.join("; ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}

            {/* 第5步：认知验证（证据溯源面板） */}
            {result.step5_validation && (
              <section id="sec-validation">
                <ValidationPanel validation={result.step5_validation} />
              </section>
            )}

            {/* v1 选基：组合草案（设计 §4.4，默认折叠 + 标注"研究草案，非交易指令"） */}
            <section id="sec-portfolio" className="card" style={{ marginBottom: "12px" }}>
              {hasCandidates ? (
                <details>
                  <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                    查看组合草案（研究草案，非交易指令）
                  </summary>
                  <p style={{ color: "var(--text-3)", fontSize: "12px", marginTop: "6px" }}>
                    下方为基于认知的组合研究草案，不构成投资建议。认知仓位、估值数据日期、组合穿透均按当前最新数据计算。
                  </p>
                  <p style={{ color: "var(--text-2)", marginTop: "12px", marginBottom: "12px" }}>{pf.rationale}</p>

              {/* 仓位配置环形图 + 进度条 */}
              <div style={{ display: "flex", gap: "24px", alignItems: "center", flexWrap: "wrap" }}>
                <DonutChart
                  data={[
                    { name: "认知仓位", value: pf.suggested_weight || 0, color: "#3b82f6" },
                    { name: "防守仓位", value: pf.defense_weight || 0, color: "#10b981" },
                    { name: "现金", value: pf.cash_pct || 0, color: "#e5e7eb" },
                  ]}
                  size={160}
                  innerRadius={40}
                  outerRadius={65}
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
                  {pf.top_funds && pf.top_funds.length > 0 && (
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
                            <tr key={i}>
                              <td>{String(ff.fund_code ?? "")}</td>
                              <td>{String(ff.fund_name ?? "")}</td>
                              <td>{fmt(ff.match_pct as number | null, "%")}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
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

              {/* 持仓重叠度分析 */}
              {pf.overlap_analysis && pf.overlap_analysis.max_overlap_pct > 0 && (
                <div style={{ marginTop: "12px", padding: "8px 12px", background: "var(--surface-2)", borderRadius: "6px", fontSize: "13px" }}>
                  <span style={{ color: "var(--text-3)" }}>持仓重叠度：</span>
                  {pf.overlap_analysis.high_overlap_pairs.length > 0 ? (
                    <span style={{ color: "var(--warn)" }}>
                      最高 {fmt(pf.overlap_analysis.max_overlap_pct, "%")}
                      （{pf.overlap_analysis.high_overlap_pairs.map(p => `${p[0]}↔${p[1]}`).join("、")}高度重叠）
                    </span>
                  ) : (
                    <span style={{ color: "var(--pos)" }}>最高 {fmt(pf.overlap_analysis.max_overlap_pct, "%")}，重叠度低</span>
                  )}
                </div>
              )}

              {/* 组合级风险指标 */}
              {pf.metrics && (() => {
                const m = pf.metrics;
                const hp = m.holdings_penetration || [];
                const ie = m.industry_exposure || [];
                return (
                  <>
                    {/* KPI 卡片 */}
                    <div style={{ display: "flex", gap: "12px", marginTop: "16px", flexWrap: "wrap" }}>
                      {m.portfolio_pe != null && (
                        <div className="kpi-box" style={{ minWidth: "120px" }}>
                          <div className="kpi-label">组合加权PE</div>
                          <div className="kpi-value">{m.portfolio_pe}</div>
                        </div>
                      )}
                      {m.portfolio_volatility != null && (
                        <div className="kpi-box" style={{ minWidth: "120px" }}>
                          <div className="kpi-label">年化波动率</div>
                          <div className="kpi-value">{fmt(m.portfolio_volatility, "%")}</div>
                        </div>
                      )}
                      {m.portfolio_max_drawdown != null && (
                        <div className="kpi-box" style={{ minWidth: "120px" }}>
                          <div className="kpi-label">最大回撤</div>
                          <div className="kpi-value" style={{ color: "var(--neg)" }}>{fmt(m.portfolio_max_drawdown, "%")}</div>
                        </div>
                      )}
                    </div>

                    {/* 持仓穿透条形图 */}
                    {hp.length > 0 && (
                      <div style={{ marginTop: "16px" }}>
                        <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-2)", marginBottom: "8px" }}>持仓穿透 Top 10</div>
                        <HorizontalBarChart
                          data={hp.slice(0, 10).map(h => ({
                            name: h.stock_name || h.stock_code,
                            value: h.weight,
                          }))}
                          height={280}
                          color="#6366f1"
                        />
                      </div>
                    )}

                    {/* 行业暴露条形图 */}
                    {ie.length > 0 && (
                      <div style={{ marginTop: "16px" }}>
                        <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-2)", marginBottom: "8px" }}>行业暴露</div>
                        <HorizontalBarChart
                          data={ie.map(ind => ({
                            name: ind.name,
                            value: ind.weight,
                          }))}
                          height={200}
                          color="#10b981"
                        />
                      </div>
                    )}
                  </>
                );
              })()}

              {/* 导出按钮 */}
              <button
                className="btn"
                style={{ marginTop: "12px" }}
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
                </details>
              ) : (
                <div className="cognition-empty-state" role="status">
                  <div className="cognition-empty-state-title">没有合格组合</div>
                  <div className="cognition-empty-state-detail">
                    候选为空时不展示可执行组合。请先调整方向、产业链环节或估值容忍度。
                  </div>
                </div>
              )}
            </section>
          </div>

          {/* 右侧详情卡 */}
          <div className="cognition-detail-col">
            <FundDetailPanel fund={selectedFund} />
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
          </div>
        </div>
        </div>
      </CognitionErrorBoundary>
    );
  }

  return null;
}

// === 证据溯源面板组件 ===

const SOURCE_TYPE_LABEL: Record<string, string> = {
  chain_analysis: "产业链分析",
  market_data: "市场数据",
  estimate: "推算",
  trend: "持仓趋势",
  fund_report: "基金经理",
};

const SOURCE_TYPE_COLOR: Record<string, string> = {
  chain_analysis: "var(--info)",
  market_data: "var(--accent)",
  estimate: "var(--warn)",
  trend: "var(--text-3)",
  fund_report: "#9b59b6",
};

function EvidenceCard({ evidence, type }: { evidence: Evidence; type: "support" | "oppose" | "warn" }) {
  const borderColor = type === "support" ? "var(--pos)" : type === "oppose" ? "var(--neg)" : "var(--warn)";
  const bgColor = type === "support" ? "rgba(46,204,113,0.05)" : type === "oppose" ? "rgba(231,76,60,0.05)" : "rgba(243,156,18,0.05)";

  return (
    <div style={{
      borderLeft: `3px solid ${borderColor}`,
      background: bgColor,
      padding: "8px 12px",
      borderRadius: "0 6px 6px 0",
      marginBottom: "6px",
    }}>
      <div style={{ fontWeight: 500, marginBottom: "4px" }}>{evidence.claim}</div>
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", fontSize: "12px", color: "var(--text-3)" }}>
        <span style={{
          padding: "1px 6px",
          borderRadius: "3px",
          background: SOURCE_TYPE_COLOR[evidence.source_type] ?? "var(--text-3)",
          color: "#fff",
          fontSize: "11px",
        }}>
          {SOURCE_TYPE_LABEL[evidence.source_type] ?? evidence.source_type}
        </span>
        <span>来源：{evidence.source}</span>
      </div>
      {evidence.context && (
        <div style={{ fontSize: "12px", color: "var(--text-2)", marginTop: "4px" }}>{evidence.context}</div>
      )}
      {evidence.raw_data && Object.keys(evidence.raw_data).length > 0 && (
        <div style={{ fontSize: "11px", color: "var(--text-3)", marginTop: "4px", fontFamily: "monospace" }}>
          {Object.entries(evidence.raw_data).map(([k, v]) => `${k}=${v}`).join("  ")}
        </div>
      )}
    </div>
  );
}

function ValidationPanel({ validation }: { validation: NonNullable<CognitionResponse["step5_validation"]> }) {
  const verdictColor =
    validation.verdict === "认知有效" ? "var(--pos)" :
    validation.verdict === "认知基本有效" ? "var(--pos)" :
    validation.verdict === "认知有分歧" ? "var(--warn)" :
    "var(--neg)";

  return (
    <div className="card" style={{ marginBottom: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <span style={{ fontWeight: 600 }}>认知验证</span>
        <span style={{
          padding: "4px 12px",
          borderRadius: "4px",
          background: verdictColor,
          color: "#fff",
          fontSize: "13px",
          fontWeight: 600,
        }}>
          {validation.verdict}
        </span>
      </div>

      <p style={{ color: "var(--text-2)", fontSize: "13px", marginBottom: "12px" }}>{validation.verdict_detail}</p>

      {/* 证据计数 */}
      <div style={{ display: "flex", gap: "16px", marginBottom: "12px", fontSize: "13px" }}>
        <span style={{ color: "var(--pos)" }}>支持证据 {validation.evidence_counts.supporting}</span>
        <span style={{ color: "var(--neg)" }}>反对证据 {validation.evidence_counts.opposing}</span>
      </div>

      {/* 支持证据 */}
      {validation.supporting_evidence.length > 0 && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ fontSize: "13px", color: "var(--pos)", fontWeight: 600, marginBottom: "6px" }}>支持证据</div>
          {validation.supporting_evidence.map((e, i) => (
            <EvidenceCard key={i} evidence={e} type="support" />
          ))}
        </div>
      )}

      {/* 反对证据 */}
      {validation.opposing_evidence.length > 0 && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ fontSize: "13px", color: "var(--neg)", fontWeight: 600, marginBottom: "6px" }}>反对证据</div>
          {validation.opposing_evidence.map((e, i) => (
            <EvidenceCard key={i} evidence={e} type="oppose" />
          ))}
        </div>
      )}

      {/* 警告 */}
      {validation.warnings.length > 0 && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ fontSize: "13px", color: "var(--warn)", fontWeight: 600, marginBottom: "6px" }}>风险提示</div>
          {validation.warnings.map((e, i) => (
            <EvidenceCard key={i} evidence={e} type="warn" />
          ))}
        </div>
      )}

      {/* 推理链 */}
      {validation.reasoning_chain.length > 0 && (
        <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
          <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>推理链</div>
          {validation.reasoning_chain.map((node, i) => (
            <div key={i} style={{ display: "flex", gap: "8px", marginBottom: "6px", fontSize: "13px" }}>
              <span style={{ color: "var(--text-3)", minWidth: "80px" }}>{node.step}</span>
              <span style={{ flex: 1 }}>{node.description}</span>
            </div>
          ))}
        </div>
      )}

      {/* 多空辩论 */}
      {validation.debate && validation.debate.length > 0 && (
        <DebatePanel debate={validation.debate} />
      )}

      {/* 认知反馈闭环 */}
      {validation.cognition_feedback && (
        <FeedbackPanel feedback={validation.cognition_feedback} />
      )}
    </div>
  );
}

function DebatePanel({ debate }: { debate: DebateRound[] }) {
  return (
    <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
      <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "10px" }}>多空辩论</div>
      {debate.map((round) => (
        <div key={round.round} style={{ marginBottom: "12px", padding: "8px 12px", background: "var(--bg-2)", borderRadius: "6px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-3)", marginBottom: "6px" }}>Round {round.round}</div>

          {/* Bull论点 */}
          <div style={{ borderLeft: "3px solid var(--pos)", paddingLeft: "8px", marginBottom: "6px" }}>
            <span style={{ fontSize: "12px", color: "var(--pos)", fontWeight: 600 }}>Bull </span>
            <span style={{ fontSize: "13px" }}>{round.bull_argument.claim}</span>
          </div>

          {/* Bear反驳 */}
          {round.bear_rebuttal ? (
            <div style={{ borderLeft: "3px solid var(--neg)", paddingLeft: "8px", marginBottom: "6px" }}>
              <span style={{ fontSize: "12px", color: "var(--neg)", fontWeight: 600 }}>Bear </span>
              <span style={{ fontSize: "13px" }}>{round.bear_rebuttal.claim}</span>
            </div>
          ) : (
            <div style={{ borderLeft: "3px solid var(--text-3)", paddingLeft: "8px", marginBottom: "6px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-3)" }}>Bear 无反驳（利好无争议）</span>
            </div>
          )}

          {/* Bull回应 */}
          {round.bull_response && (
            <div style={{ borderLeft: "3px solid var(--pos)", paddingLeft: "8px" }}>
              <span style={{ fontSize: "12px", color: "var(--pos)", fontWeight: 600 }}>Bull回应 </span>
              <span style={{ fontSize: "13px" }}>{round.bull_response.claim}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function FeedbackPanel({ feedback }: { feedback: CognitionFeedback }) {
  const showFeedback = feedback.validation_verdict !== "认知有效" || feedback.correction_suggestions.length > 0;
  if (!showFeedback) return null;

  return (
    <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
      <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>认知反馈</div>

      {/* 原始认知 vs 修正认知 */}
      <div style={{ marginBottom: "8px", fontSize: "13px" }}>
        <div style={{ color: "var(--text-3)" }}>原始认知：{feedback.original_belief}</div>
        {feedback.adjusted_belief !== feedback.original_belief && (
          <div style={{ color: "var(--warn)", marginTop: "4px" }}>修正认知：{feedback.adjusted_belief}</div>
        )}
      </div>

      {/* 修正建议 */}
      {feedback.correction_suggestions.length > 0 && (
        <div>
          {feedback.correction_suggestions.map((s, i) => (
            <div key={i} style={{
              fontSize: "13px",
              color: "var(--text-2)",
              padding: "4px 8px",
              marginBottom: "4px",
              background: "rgba(243,156,18,0.05)",
              borderRadius: "4px",
            }}>
              {s}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
