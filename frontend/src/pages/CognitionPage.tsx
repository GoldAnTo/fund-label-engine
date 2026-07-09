import { useEffect, useState } from "react";
import {
  fetchThemes,
  fetchDirectionLinks,
  postCognition,
  searchConcepts,
  postConceptCognition,
  type ThemeInfo,
  type ChainLinkInfo,
  type CognitionResponse,
  type Evidence,
  type ConceptBoard,
  type DebateRound,
  type CognitionFeedback,
} from "../api";
import {
  KpiBar,
  ValuationQuad,
  SideNav,
  FundDetailPanel,
  useScrollSpy,
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

  // === 阶段1：选方向 ===
  if (step === 1) {
    return (
      <div className="main">
        <h2 style={{ marginBottom: "4px" }}>你相信什么？</h2>
        <p style={{ color: "var(--text-3)", marginBottom: "24px" }}>
          选择一个方向，系统帮你从认知推导到基金配置
        </p>

        <div className="cognition-direction-grid">
          {themes.map((t) => (
            <div key={t.key} className="card cognition-direction-card" onClick={() => pickDirection(t.key)}>
              <div style={{ fontWeight: 600, marginBottom: "6px" }}>{t.name}</div>
              <div style={{ fontSize: "13px", color: "var(--text-2)" }}>{t.belief}</div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: "24px" }}>
          <div style={{ fontSize: "13px", color: "var(--text-3)", marginBottom: "8px" }}>
            搜索概念板块（300+主题动态匹配）：
          </div>
          <input
            className="custom-direction-input"
            style={{ width: "100%" }}
            value={conceptKeyword}
            onChange={(e) => setConceptKeyword(e.target.value)}
            placeholder="输入关键词搜索，如：AI、芯片、创新药、白酒、新能源..."
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
          <div style={{ fontSize: "13px", color: "var(--text-3)", marginBottom: "8px" }}>
            或者输入你关注的方向：
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              className="custom-direction-input"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && customInput.trim() && pickDirection(customInput.trim())}
              placeholder="例如：新能源、军工、人形机器人..."
            />
            <button
              className="btn"
              disabled={!customInput.trim()}
              onClick={() => pickDirection(customInput.trim())}
            >
              确认
            </button>
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

        {loading && <p>加载产业链...</p>}

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

    // 章节列表（左侧导航）
    const sectionIds = ["sec-judgment", "sec-quad", "sec-chain", "sec-funds", "sec-gated", "sec-validation", "sec-portfolio"];
    const scrolled = useScrollSpy(sectionIds);

    return (
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
            <button className="btn btn-sm" onClick={() => setStep(2)}>换环节</button>
            <button className="btn btn-sm" onClick={reset}>换方向</button>
          </div>
        </div>

        {loading && <p>分析中...</p>}
        {error && <p style={{ color: "var(--neg)" }}>{error}</p>}

        {/* 顶部KPI条（4个并排卡片） */}
        <KpiBar
          judgment={j}
          conviction={result.conviction ?? "medium"}
        />

        {/* 三面板布局：左导航 / 中结果 / 右详情 */}
        <div className="cognition-three-panel">
          {/* 左侧导航 */}
          <SideNav
            active={scrolled}
            onSelect={(id) => setSelectedFundCode(id)}
            sections={[
              { id: "sec-judgment", label: "认知判断" },
              { id: "sec-quad", label: "估值四维" },
              { id: "sec-chain", label: "受益链路", count: result.step2_chain.length },
              { id: "sec-funds", label: "匹配基金", count: result.step4_fund_matches.length },
              ...(result.gated_out_funds && result.gated_out_funds.length > 0
                ? [{ id: "sec-gated", label: "门禁拦截", count: result.gated_out_funds.length }]
                : []),
              ...(result.step5_validation
                ? [{ id: "sec-validation", label: "认知验证",
                    count: result.step5_validation.supporting_evidence.length + result.step5_validation.opposing_evidence.length }]
                : []),
              { id: "sec-portfolio", label: "组合方案" },
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

            {/* 第5步：组合方案 */}
            <section id="sec-portfolio" className="card" style={{ marginBottom: "12px" }}>
              <div style={{ fontWeight: 600, marginBottom: "8px" }}>组合方案</div>
              <p style={{ color: "var(--text-2)", marginBottom: "12px" }}>{pf.rationale}</p>

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
                <div style={{ marginTop: "12px", padding: "8px 12px", background: "var(--bg-2)", borderRadius: "6px", fontSize: "13px" }}>
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
            </section>
          </div>

          {/* 右侧详情卡 */}
          <div className="cognition-detail-col">
            <FundDetailPanel fund={selectedFund} />
          </div>
        </div>
      </div>
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
