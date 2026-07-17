import { useEffect, useState } from "react";
import type { CognitionResponse, ChainLink, MonitorOverview } from "../api";

/* ===================================================================
   顶部 KPI 条（4 个并排卡片：认知 / 信心 / 风险 / 估值容忍）
   借鉴 Fincept Terminal 的多面板顶部 KPI 设计
   =================================================================== */

interface KpiBarProps {
  judgment: CognitionResponse["step1_judgment"];
  conviction: string;
  riskTolerance?: string | null;
  valuationTolerance?: string | null;
}

const VAL_TOL_LABEL: Record<string, string> = { low: "严格", medium: "中性", high: "宽松" };
const RISK_LABEL: Record<string, string> = { conservative: "保守", balanced: "平衡", aggressive: "激进" };

export function KpiBar({ judgment, conviction, riskTolerance, valuationTolerance }: KpiBarProps) {
  const tol = valuationTolerance ?? judgment.valuation_tolerance ?? "medium";
  const risk = riskTolerance ?? "balanced";
  const convictionLabel = conviction === "high" ? "高" : conviction === "low" ? "低" : "中";

  return (
    <div className="cognition-kpi-bar">
      <div className="cognition-kpi-card">
        <div className="cognition-kpi-label">认知</div>
        <div className="cognition-kpi-value" style={{ fontSize: "13px" }}>
          {judgment.belief.length > 36 ? `${judgment.belief.slice(0, 36)}…` : judgment.belief}
        </div>
        <div className="cognition-kpi-sub">层次：{judgment.level}</div>
      </div>
      <div className="cognition-kpi-card">
        <div className="cognition-kpi-label">信心</div>
        <div className="cognition-kpi-value" style={{
          color: conviction === "high" ? "var(--pos)" : conviction === "low" ? "var(--neg)" : "var(--warn)",
        }}>{convictionLabel}</div>
        <div className="cognition-kpi-sub">时间：{judgment.time_horizon}</div>
      </div>
      <div className="cognition-kpi-card">
        <div className="cognition-kpi-label">风险偏好</div>
        <div className="cognition-kpi-value">{RISK_LABEL[risk] ?? risk}</div>
        <div className="cognition-kpi-sub">防守仓位随偏好调整</div>
      </div>
      <div className="cognition-kpi-card">
        <div className="cognition-kpi-label">估值容忍</div>
        <div className="cognition-kpi-value">{VAL_TOL_LABEL[tol] ?? tol}</div>
        <div className="cognition-kpi-sub">核心指标：{judgment.key_metric}</div>
      </div>
    </div>
  );
}

/* ===================================================================
   估值四维卡片（成长空间 / 护城河 / 竞争格局 / 经营绩效）
   借鉴 AI 涨乐"四维度动态估值"卡片
   =================================================================== */

interface ValuationQuadProps {
  expectationGap: CognitionResponse["step3_expectation_gap"];
  chain: ChainLink[];
  fundMatches: CognitionResponse["step4_fund_matches"];
}

/** 把数字序列渲染成 sparkline（柱状） */
function SparkBars({ values, maxAbs }: { values: number[]; maxAbs: number }) {
  if (values.length === 0) return null;
  return (
    <div className="valuation-quad-spark">
      {values.map((v, i) => {
        const h = maxAbs > 0 ? Math.max(2, Math.abs(v) / maxAbs * 16) : 4;
        return (
          <div
            key={i}
            className="valuation-quad-spark-bar"
            style={{ height: `${h}px`, background: v < 0 ? "var(--neg)" : undefined }}
            title={`${v}`}
          />
        );
      })}
    </div>
  );
}

export function ValuationQuad({ expectationGap, chain, fundMatches }: ValuationQuadProps) {
  // 维度 1：成长空间 — 用环节的利润增速 sparkline
  const growthValues = chain.map((l) => Number(l.growth_pct ?? 0)).filter((v) => !isNaN(v));
  const avgGrowth = growthValues.length
    ? growthValues.reduce((a, b) => a + b, 0) / growthValues.length
    : null;
  const growthTag = avgGrowth === null
    ? { label: "数据不足", cls: "neutral" as const }
    : avgGrowth > 30
      ? { label: "高增长", cls: "pos" as const }
      : avgGrowth > 15
        ? { label: "稳健", cls: "warn" as const }
        : { label: "增长放缓", cls: "neg" as const };
  const growthMaxAbs = Math.max(1, ...growthValues.map((v) => Math.abs(v)));

  // 维度 2：护城河 — 用持仓匹配度（高匹配 = 主题代表性 = 强护城河）
  const matchValues = fundMatches.slice(0, 8).map((f) => Number(f.match_pct ?? 0));
  const avgMatch = matchValues.length
    ? matchValues.reduce((a, b) => a + b, 0) / matchValues.length
    : null;
  const moatTag = avgMatch === null
    ? { label: "数据不足", cls: "neutral" as const }
    : avgMatch > 60
      ? { label: "主题集中", cls: "pos" as const }
      : avgMatch > 40
        ? { label: "中等集中", cls: "warn" as const }
        : { label: "分散", cls: "neg" as const };

  // 维度 3：竞争格局 — 用 PE 溢价/折价
  const pePremiums = fundMatches
    .map((f) => Number((f.valuation as Record<string, unknown>)?.pe_premium_pct ?? 0))
    .filter((v) => !isNaN(v) && v !== 0);
  const avgPremium = pePremiums.length
    ? pePremiums.reduce((a, b) => a + b, 0) / pePremiums.length
    : null;
  const premiumTag = avgPremium === null
    ? { label: "无对比", cls: "neutral" as const }
    : avgPremium > 20
      ? { label: "高估", cls: "neg" as const }
      : avgPremium < -20
        ? { label: "折价", cls: "pos" as const }
        : { label: "合理", cls: "warn" as const };

  // 维度 4：经营绩效 — 用 price-in 年限（被市场已 price in 多少年增长）
  const priceInYears = fundMatches
    .map((f) => Number((f.valuation as Record<string, unknown>)?.price_in_years ?? 0))
    .filter((v) => !isNaN(v) && v !== 0);
  const avgPriceIn = priceInYears.length
    ? priceInYears.reduce((a, b) => a + b, 0) / priceInYears.length
    : null;
  const priceTag = avgPriceIn === null
    ? { label: "数据不足", cls: "neutral" as const }
    : avgPriceIn > 3
      ? { label: "透支", cls: "neg" as const }
      : avgPriceIn < 1.5
        ? { label: "低估", cls: "pos" as const }
        : { label: "合理", cls: "warn" as const };

  // gap summary 提示
  const gapText = expectationGap.summary ?? "";

  return (
    <div className="valuation-quad">
      <div className="valuation-quad-card fair">
        <div className="valuation-quad-label">成长空间</div>
        <div className="valuation-quad-headline">
          {avgGrowth === null ? "-" : `${avgGrowth.toFixed(1)}%`}
        </div>
        <span className={`valuation-quad-tag ${growthTag.cls}`}>{growthTag.label}</span>
        <SparkBars values={growthValues} maxAbs={growthMaxAbs} />
        <div className="valuation-quad-context">环节利润增速分布（条形=各环节）</div>
      </div>
      <div className="valuation-quad-card fair">
        <div className="valuation-quad-label">护城河</div>
        <div className="valuation-quad-headline">
          {avgMatch === null ? "-" : `${avgMatch.toFixed(1)}%`}
        </div>
        <span className={`valuation-quad-tag ${moatTag.cls}`}>{moatTag.label}</span>
        <SparkBars values={matchValues} maxAbs={Math.max(1, ...matchValues.map((v) => Math.abs(v)))} />
        <div className="valuation-quad-context">TOP基金持仓主题匹配度均值</div>
      </div>
      <div className="valuation-quad-card fair">
        <div className="valuation-quad-label">竞争格局</div>
        <div className={`valuation-quad-headline ${
          avgPremium === null ? "" : avgPremium > 20 ? "neg" : avgPremium < -20 ? "pos" : "warn"
        }`}>
          {avgPremium === null ? "-" : `${avgPremium > 0 ? "+" : ""}${avgPremium.toFixed(1)}%`}
        </div>
        <span className={`valuation-quad-tag ${premiumTag.cls}`}>{premiumTag.label}</span>
        <SparkBars
          values={pePremiums.slice(0, 8)}
          maxAbs={Math.max(1, ...pePremiums.slice(0, 8).map((v) => Math.abs(v)))}
        />
        <div className="valuation-quad-context">相对行业PE中位数溢价/折价</div>
      </div>
      <div className="valuation-quad-card fair">
        <div className="valuation-quad-label">经营绩效</div>
        <div className="valuation-quad-headline">
          {avgPriceIn === null ? "-" : `${avgPriceIn.toFixed(1)}年`}
        </div>
        <span className={`valuation-quad-tag ${priceTag.cls}`}>{priceTag.label}</span>
        <SparkBars
          values={priceInYears.slice(0, 8)}
          maxAbs={Math.max(1, ...priceInYears.slice(0, 8).map((v) => Math.abs(v)))}
        />
        <div className="valuation-quad-context">当前估值已 price in 多少年增长</div>
      </div>
      {gapText && (
        <div className="valuation-quad-context" style={{ gridColumn: "1 / -1", fontSize: "12px" }}>
          {gapText}
        </div>
      )}
    </div>
  );
}

/* ===================================================================
   左侧导航：环节列表 / 匹配基金 / 证据 / 辩论 等的快速跳转
   =================================================================== */

interface SideNavProps {
  sections: { id: string; label: string; count?: number }[];
  active: string;
  onSelect: (id: string) => void;
}

export function SideNav({ sections, active, onSelect }: SideNavProps) {
  return (
    <nav className="cognition-side-nav">
      <div className="cognition-side-nav-title">分析导航</div>
      {sections.map((s) => (
        <div
          key={s.id}
          className={`cognition-side-nav-item ${active === s.id ? "active" : ""}`}
          onClick={() => {
            onSelect(s.id);
            const el = document.getElementById(s.id);
            if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
        >
          <span>{s.label}</span>
          {s.count !== undefined && s.count > 0 && (
            <span className="cognition-side-nav-count">{s.count}</span>
          )}
        </div>
      ))}
    </nav>
  );
}

/* ===================================================================
   右侧详情卡：选中某只基金时显示完整证据/估值/经理
   =================================================================== */

interface FundDetailProps {
  fund: CognitionResponse["step4_fund_matches"][number] | null;
}

function fmt2(v: number | string | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "-";
  if (typeof v === "string") return v;
  return Number.isInteger(v) ? `${v}${suffix}` : `${v.toFixed(2)}${suffix}`;
}

export function FundDetailPanel({ fund }: FundDetailProps) {
  if (!fund) {
    return (
      <div className="cognition-detail-empty">
        点击基金匹配表中的某一行，查看完整证据链
      </div>
    );
  }

  const v = (fund.valuation ?? {}) as Record<string, unknown>;
  const mgr = fund.manager as Record<string, unknown> | null | undefined;
  const holdings = (fund.holdings ?? []) as Array<Record<string, unknown>>;
  const trend = (fund.trend ?? {}) as Record<string, unknown>;
  const gate = (fund.gate ?? {}) as Record<string, unknown>;

  // 经理任职可视化
  const tenureDays = Number(mgr?.tenure_days ?? 0);
  const tenureColor = tenureDays > 1825 ? "pos" : tenureDays < 365 ? "neg" : "";
  const tenureLabel = tenureDays > 1825
    ? "经验丰富（>5年）"
    : tenureDays < 365
      ? "任职不足1年"
      : "任职1-5年";

  return (
    <div className="fund-detail-card">
      <div className="fund-detail-header">
        <div>
          <div className="fund-detail-name">{String(fund.fund_name ?? fund.fund_code)}</div>
          <div className="fund-detail-code">{String(fund.fund_code)}</div>
        </div>
      </div>

      <div className="fund-detail-section">估值</div>
      <div className="fund-detail-row">
        <span className="fund-detail-row-label">加权PE</span>
        <span className="fund-detail-row-value">{fmt2(v.weighted_pe as number | null)}</span>
      </div>
      <div className="fund-detail-row">
        <span className="fund-detail-row-label">估值分位</span>
        <span className="fund-detail-row-value">
          {fmt2(v.weighted_val_pct as number | null, "%")}
        </span>
      </div>
      <div className="fund-detail-row">
        <span className="fund-detail-row-label">PEG</span>
        <span className="fund-detail-row-value">{fmt2(v.peg as number | null)}</span>
      </div>
      <div className="fund-detail-row">
        <span className="fund-detail-row-label">Price-in</span>
        <span className="fund-detail-row-value">
          {v.price_in_years != null ? `${fmt2(v.price_in_years as number)}年` : "-"}
        </span>
      </div>
      {v.pe_premium_pct != null && (
        <div className="fund-detail-row">
          <span className="fund-detail-row-label">vs同行PE</span>
          <span className={`fund-detail-row-value ${
            (v.pe_premium_pct as number) > 20 ? "neg" :
            (v.pe_premium_pct as number) < -20 ? "pos" : ""
          }`}>
            {(v.pe_premium_pct as number) > 0 ? "+" : ""}{fmt2(v.pe_premium_pct as number)}%
          </span>
        </div>
      )}

      <div className="fund-detail-section">匹配</div>
      <div className="fund-detail-row">
        <span className="fund-detail-row-label">主题匹配度</span>
        <span className="fund-detail-row-value">{fmt2(fund.match_pct as number, "%")}</span>
      </div>

      <div className="fund-detail-section">持仓趋势</div>
      <div className="fund-detail-row">
        <span className="fund-detail-row-label">趋势</span>
        <span className="fund-detail-row-value">
          {String(trend.trend ?? "-")}
          {trend.change_pct != null ? ` (${fmt2(trend.change_pct as number, "%")})` : ""}
        </span>
      </div>

      <div className="fund-detail-section">基金经理</div>
      {mgr ? (
        <>
          <div className="fund-detail-row">
            <span className="fund-detail-row-label">姓名</span>
            <span className="fund-detail-row-value">{String(mgr.name ?? "-")}</span>
          </div>
          <div className="fund-detail-row">
            <span className="fund-detail-row-label">任职</span>
            <span className={`fund-detail-row-value ${tenureColor}`}>
              {fmt2(tenureDays / 365, "年")} · {tenureLabel}
            </span>
          </div>
          {mgr.return_pct != null && (
            <div className="fund-detail-row">
              <span className="fund-detail-row-label">任职回报</span>
              <span className={`fund-detail-row-value ${
                (mgr.return_pct as number) > 0 ? "pos" : "neg"
              }`}>
                {fmt2(mgr.return_pct as number, "%")}
              </span>
            </div>
          )}
        </>
      ) : (
        <div className="fund-detail-row">
          <span className="fund-detail-row-value" style={{ color: "var(--text-3)" }}>
            无经理数据
          </span>
        </div>
      )}

      <div className="fund-detail-section">门禁</div>
      <div className="fund-detail-row">
        <span className="fund-detail-row-label">状态</span>
        <span className={`fund-detail-row-value ${gate.passed ? "pos" : "neg"}`}>
          {gate.passed ? "通过" : "拦截"}
        </span>
      </div>
      {!gate.passed && Array.isArray(gate.violations) && (gate.violations as string[]).length > 0 && (
        <div style={{ fontSize: "11px", color: "var(--neg)", marginTop: "4px", lineHeight: 1.4 }}>
          {(gate.violations as string[]).join("；")}
        </div>
      )}

      {holdings.length > 0 && (
        <>
          <div className="fund-detail-section">前5大持仓</div>
          <div className="fund-detail-holdings">
            {holdings.slice(0, 5).map((h, i) => (
              <div key={i} className="fund-detail-holding-row">
                <span className="fund-detail-holding-name">
                  {String(h.stock_name ?? h.stock_code)}
                </span>
                <span className="fund-detail-holding-weight">
                  {((h.weight as number) * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ===================================================================
   useScrollSpy：监听 scrollY，返回当前 active section id
   =================================================================== */

export function useScrollSpy(ids: string[], offset = 100): string {
  const [active, setActive] = useState<string>(ids[0] ?? "");

  useEffect(() => {
    if (ids.length === 0) return;
    const handler = () => {
      const y = window.scrollY + offset + 4;
      let current = ids[0] ?? "";
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.offsetTop <= y) {
          current = id;
        }
      }
      setActive(current);
    };
    window.addEventListener("scroll", handler, { passive: true });
    handler();
    return () => window.removeEventListener("scroll", handler);
  }, [ids, offset]);

  return active;
}

/* ===================================================================
   ResearchBrief（研究简报）：方向、用户观点、环节、信心、周期
   放在结果页顶部，紧跟 KpiBar
   =================================================================== */

export interface ResearchBriefProps {
  direction: string;
  beliefNote?: string | null;
  chainLabel?: string | null;
  convictionLabel: string;
  convictionLevel: "high" | "medium" | "low" | string;
  timeHorizon: string;
  valuationToleranceLabel: string;
  asOfDate?: string | null;
}

export function ResearchBrief(props: ResearchBriefProps) {
  return (
    <section
      className="research-brief"
      aria-label="研究简报"
    >
      <h3 className="research-brief-title">研究简报</h3>
      <dl className="research-brief-grid">
        <div className="research-brief-item">
          <dt>方向</dt>
          <dd>{props.direction || "—"}</dd>
        </div>
        <div className="research-brief-item">
          <dt>信心</dt>
          <dd>
            <span className={`conviction-badge conviction-${props.convictionLevel}`}>
              {props.convictionLabel}
            </span>
          </dd>
        </div>
        <div className="research-brief-item">
          <dt>时间周期</dt>
          <dd>{props.timeHorizon || "—"}</dd>
        </div>
        <div className="research-brief-item">
          <dt>估值容忍</dt>
          <dd>{props.valuationToleranceLabel}</dd>
        </div>
        {props.chainLabel && (
          <div className="research-brief-item">
            <dt>产业链环节</dt>
            <dd>{props.chainLabel}</dd>
          </div>
        )}
        {props.asOfDate && (
          <div className="research-brief-item">
            <dt>数据日期</dt>
            <dd>{props.asOfDate}</dd>
          </div>
        )}
      </dl>
      {props.beliefNote && (
        <div className="research-brief-note">
          <span className="research-brief-note-label">我的观点：</span>
          <span>{props.beliefNote}</span>
        </div>
      )}
    </section>
  );
}

/* ===================================================================
   EvidenceSummary（证据汇总）：支持、反对、待验证 三类
   数据从 CognitionResponse.step3_expectation_gap + step5_validation 整理
   =================================================================== */

export interface EvidenceItem {
  category: "support" | "oppose" | "pending";
  title: string;
  detail: string;
}

export interface EvidenceSummaryProps {
  items: EvidenceItem[];
}

export function EvidenceSummary({ items }: EvidenceSummaryProps) {
  const support = items.filter((i) => i.category === "support");
  const oppose = items.filter((i) => i.category === "oppose");
  const pending = items.filter((i) => i.category === "pending");

  return (
    <section className="evidence-summary" aria-label="证据汇总">
      <h3 className="evidence-title">证据汇总</h3>
      <div className="evidence-grid">
        <EvidenceColumn kind="support" title="支持认知" items={support} />
        <EvidenceColumn kind="oppose" title="反对 / 警惕" items={oppose} />
        <EvidenceColumn kind="pending" title="待验证" items={pending} />
      </div>
    </section>
  );
}

function EvidenceColumn({
  kind,
  title,
  items,
}: {
  kind: "support" | "oppose" | "pending";
  title: string;
  items: EvidenceItem[];
}) {
  return (
    <div className={`evidence-col evidence-col-${kind}`}>
      <div className="evidence-col-head">
        <span className={`evidence-col-dot evidence-col-dot-${kind}`} aria-hidden="true" />
        <span className="evidence-col-title">{title}</span>
        <span className="evidence-col-count">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="evidence-empty">暂无</div>
      ) : (
        <ul className="evidence-list">
          {items.map((it, i) => (
            <li key={i} className="evidence-item">
              <div className="evidence-item-title">{it.title}</div>
              {it.detail && <div className="evidence-item-detail">{it.detail}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ===================================================================
   CandidateDecision（研究结论）：把匹配、估值门禁、数据状态合成短结论
   4 类：可继续研究 / 估值待观察 / 数据不足 / 已剔除
   =================================================================== */

export type CandidateStatus = "continue" | "observe" | "insufficient" | "excluded";

export interface CandidateDecisionProps {
  status: CandidateStatus;
  reason?: string;
}

const STATUS_LABEL: Record<CandidateStatus, string> = {
  continue: "可继续研究",
  observe: "估值待观察",
  insufficient: "数据不足",
  excluded: "已剔除",
};

export function CandidateDecision({ status, reason }: CandidateDecisionProps) {
  return (
    <span className={`candidate-decision candidate-decision-${status}`} role="status">
      {STATUS_LABEL[status]}
      {reason && <span className="candidate-decision-reason"> · {reason}</span>}
    </span>
  );
}

/* ===================================================================
   FundCandidatesTable：研究候选表
   设计 §4.3：候选表名称为"认知匹配研究候选"，不使用"推荐基金"
   每行：基金名称、匹配度、核心产业链/股票暴露、估值门禁、研究结论
   表格行使用 button 打开右侧详情（避免点击 <tr>）
   =================================================================== */

export interface FundCandidate {
  fund_code: string;
  fund_name: string;
  match_pct: number;
  chain_breakdown?: Record<string, number>;
  valuation?: Record<string, unknown>;
  trend?: { trend: string; diff: number; periods?: Array<{ period: string; weight: number }> };
  gate?: { passed: boolean; violations: string[] };
}

export interface GatedOutFund {
  fund_code: string;
  fund_name: string;
  reason?: string;
}

export interface FundCandidatesTableProps {
  funds: FundCandidate[];
  gatedOut?: GatedOutFund[];
  selectedCode: string | null;
  onSelect: (code: string) => void;
  onMonitor?: (code: string) => void;
  monitoringCode?: string | null;
}

function inferCandidateStatus(fund: FundCandidate): { status: CandidateStatus; reason?: string } {
  // 估值门禁违例 → 估值待观察
  if (fund.gate && !fund.gate.passed) {
    const violations = fund.gate.violations || [];
    return {
      status: "observe",
      reason: violations[0] || "未通过估值门禁",
    };
  }
  // 估值数据缺失 → 数据不足
  const v = fund.valuation || {};
  if (v.weighted_pe == null && v.weighted_val_pct == null) {
    return { status: "insufficient", reason: "估值数据缺失" };
  }
  // 匹配度过低 → 数据不足
  if (fund.match_pct < 5) {
    return { status: "insufficient", reason: "匹配度过低" };
  }
  return { status: "continue" };
}

export function FundCandidatesTable({
  funds,
  gatedOut = [],
  selectedCode,
  onSelect,
  onMonitor,
  monitoringCode,
}: FundCandidatesTableProps) {
  return (
    <section className="card" aria-label="认知匹配研究候选">
      <h3 className="research-brief-title">认知匹配研究候选</h3>
      <table className="candidate-table">
        <thead>
          <tr>
            <th>基金</th>
            <th>匹配度</th>
            <th>核心暴露</th>
            <th>估值</th>
            <th>持仓趋势</th>
            <th>研究结论</th>
            <th aria-label="动作"></th>
            {onMonitor && <th aria-label="监控"></th>}
          </tr>
        </thead>
        <tbody>
          {funds.map((f) => {
            const { status, reason } = inferCandidateStatus(f);
            const chainStr = f.chain_breakdown
              ? Object.entries(f.chain_breakdown)
                  .sort((a, b) => (b[1] as number) - (a[1] as number))
                  .slice(0, 2)
                  .map(([k, v]) => `${k} ${(v as number).toFixed(0)}%`)
                  .join(" · ")
              : "—";
            const v = f.valuation || {};
            const pe = v.weighted_pe != null ? `PE ${Number(v.weighted_pe).toFixed(0)}` : "—";
            const valPct = v.weighted_val_pct != null ? `分位 ${v.weighted_val_pct}%` : "—";
            const trendStr = f.trend
              ? f.trend.trend === "increasing"
                ? "↑ 加仓"
                : f.trend.trend === "decreasing"
                ? "↓ 减仓"
                : f.trend.trend === "stable"
                ? "→ 持平"
                : "数据不足"
              : "—";
            return (
              <tr key={f.fund_code}>
                <td>
                  <div style={{ fontWeight: 600 }}>{f.fund_name}</div>
                  <div style={{ fontSize: "11px", color: "var(--text-3)" }}>{f.fund_code}</div>
                </td>
                <td>{f.match_pct.toFixed(0)}%</td>
                <td style={{ fontSize: "11px" }}>{chainStr}</td>
                <td style={{ fontSize: "11px" }}>
                  <div>{pe}</div>
                  <div style={{ color: "var(--text-3)" }}>{valPct}</div>
                </td>
                <td style={{ fontSize: "11px" }}>{trendStr}</td>
                <td>
                  <CandidateDecision status={status} reason={reason} />
                </td>
                <td>
                  <button
                    type="button"
                    className="candidate-row-button"
                    onClick={() => onSelect(f.fund_code)}
                    aria-label={`查看 ${f.fund_name} 详情`}
                  >
                    {selectedCode === f.fund_code ? "已选" : "查看"}
                  </button>
                </td>
                {onMonitor && (
                  <td>
                    <button
                      type="button"
                      className="candidate-row-button candidate-row-button-monitor"
                      onClick={() => onMonitor(f.fund_code)}
                      aria-label={`查看 ${f.fund_name} 监控面板`}
                    >
                      {monitoringCode === f.fund_code ? "监控中" : "监控"}
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      {gatedOut.length > 0 && (
        <details style={{ marginTop: "12px", fontSize: "12px", color: "var(--text-3)" }}>
          <summary style={{ cursor: "pointer" }}>已剔除候选（{gatedOut.length} 只，被估值门禁或数据缺失挡住）</summary>
          <ul style={{ marginTop: "6px", paddingLeft: "20px" }}>
            {gatedOut.map((g) => (
              <li key={g.fund_code}>
                {g.fund_name}（{g.fund_code}）{g.reason ? ` · ${g.reason}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

/* ===================================================================
   MonitorPanel：监控面板 v1（设计 §9 阶段 3）
   展示：估值历史趋势 + 持仓变化 + 风险信号
   数据：GET /v1/monitor/fund/{code}/overview
   =================================================================== */

export interface MonitorPanelProps {
  fundCode: string;
  overview: MonitorOverview | null;
  loading?: boolean;
  error?: string | null;
}

export function MonitorPanel({ fundCode, overview, loading, error }: MonitorPanelProps) {
  if (loading) {
    return (
      <div className="monitor-panel" role="status" aria-live="polite">
        <div className="monitor-empty">加载监控数据…</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="monitor-panel" role="alert">
        <div className="monitor-empty">监控加载失败：{error}</div>
      </div>
    );
  }
  if (!overview) {
    return (
      <div className="monitor-panel">
        <div className="monitor-empty">暂无监控数据</div>
      </div>
    );
  }

  return (
    <section className="monitor-panel" aria-label={`基金 ${fundCode} 监控面板`}>
      <div className="monitor-header">
        <span className="monitor-title">监控面板</span>
        <span className="monitor-meta">截至 {overview.as_of_today}</span>
      </div>

      {/* 风险信号 */}
      {overview.risk_signals.length > 0 && (
        <div className="monitor-signals">
          {overview.risk_signals.map((s) => (
            <div
              key={s.code}
              className={`monitor-signal monitor-signal-${s.level}`}
              role="status"
            >
              <span className="monitor-signal-title">{s.title}</span>
              <span className="monitor-signal-detail">{s.detail}</span>
            </div>
          ))}
        </div>
      )}
      {overview.risk_signals.length === 0 && (
        <div className="monitor-ok" role="status">无异常信号</div>
      )}

      {/* 估值历史 */}
      <MonitorValuationSection history={overview.valuation_history} />

      {/* 持仓历史 */}
      <MonitorHoldingSection history={overview.holding_history} />
    </section>
  );
}

function MonitorValuationSection({
  history,
}: {
  history: MonitorOverview["valuation_history"];
}) {
  return (
    <details className="monitor-section" open>
      <summary>估值历史（{history.length} 期）</summary>
      {history.length === 0 ? (
        <div className="monitor-empty">暂无估值快照</div>
      ) : (
        <table className="monitor-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>PE</th>
              <th>分位</th>
              <th>PEG</th>
              <th>隐含年限</th>
              <th>重仓</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.run_id}>
                <td>{h.as_of_date}</td>
                <td>{h.weighted_pe != null ? h.weighted_pe.toFixed(1) : "—"}</td>
                <td>
                  {h.weighted_val_pct != null
                    ? `${h.weighted_val_pct.toFixed(0)}%`
                    : "—"}
                </td>
                <td>{h.weighted_peg != null ? h.weighted_peg.toFixed(1) : "—"}</td>
                <td>{h.price_in_years != null ? `${h.price_in_years.toFixed(1)} 年` : "—"}</td>
                <td>
                  {h.top_holding_weight != null
                    ? `${(h.top_holding_weight * 100).toFixed(1)}%`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}

function MonitorHoldingSection({
  history,
}: {
  history: MonitorOverview["holding_history"];
}) {
  return (
    <details className="monitor-section">
      <summary>持仓变化（最近 {history.length} 个报告期）</summary>
      {history.length === 0 ? (
        <div className="monitor-empty">暂无持仓历史</div>
      ) : (
        <div className="monitor-periods">
          {history.map((p) => (
            <div key={p.report_period} className="monitor-period">
              <div className="monitor-period-head">
                <strong>{p.report_period}</strong>
                <span className="meta">{p.total_stocks} 只</span>
              </div>
              <table className="monitor-table monitor-table-compact">
                <thead>
                  <tr>
                    <th>代码</th>
                    <th>名称</th>
                    <th>权重</th>
                  </tr>
                </thead>
                <tbody>
                  {p.top_holdings.map((h) => (
                    <tr key={h.stock_code}>
                      <td><code>{h.stock_code}</code></td>
                      <td>{h.stock_name}</td>
                      <td>{(h.weight * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {p.top_industries.length > 0 && (
                <div className="monitor-period-aux">
                  <span className="meta">行业：</span>
                  {p.top_industries.map((ind) => (
                    <span key={ind.name} className="monitor-pill">
                      {ind.name} {(ind.weight * 100).toFixed(0)}%
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </details>
  );
}
