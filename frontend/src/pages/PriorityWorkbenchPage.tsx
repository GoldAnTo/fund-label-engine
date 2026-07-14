// 优先级工作台 - 双栏布局：结论先行，扫描 -> 匹配 -> 5档 -> 选中详情

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchPriorityRun,
  fetchPriorityRunsByThesis,
  type PriorityCandidate,
  type PriorityRunDetail,
  type PriorityRunSummary,
} from "../api";
import {
  Badge,
  Card,
  ProgressBar,
  SectionTitle,
  Stat,
  Table,
  Td,
  Th,
} from "../components/ui";

// === 投资假设状态中文映射 ===
const THESIS_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  researching: "研究中",
  validated: "已验证",
  approved: "已批准",
  watching: "观察中",
  invalidated: "已失效",
  closed: "已关闭",
};

// === 五档固定顺序与配置 ===
const TIER_ORDER = [
  "research_now",
  "research_next",
  "valuation_watch",
  "data_insufficient",
  "excluded",
] as const;

type TierKey = (typeof TIER_ORDER)[number];

const TIER_CONFIG: Record<
  TierKey,
  { label: string; variant: "pos" | "accent" | "warn" | "neutral" | "neg" }
> = {
  research_now: { label: "立即研究", variant: "pos" },
  research_next: { label: "下一步研究", variant: "accent" },
  valuation_watch: { label: "估值观察", variant: "warn" },
  data_insufficient: { label: "数据不足", variant: "neutral" },
  excluded: { label: "排除", variant: "neg" },
};

// === 原因码中文映射 ===
const REASON_LABELS: Record<string, string> = {
  all_required_evidence_present: "全部必需证据齐全",
  partial_evidence_sufficient: "部分证据充足",
  valuation_soft_breach: "估值软性超标",
  valuation_hard_breach: "估值硬性超标",
  valuation_data_missing: "估值数据缺失",
  holding_data_missing: "持仓数据缺失",
  holding_data_stale: "持仓数据过期",
  holding_report_date_missing: "持仓报告期缺失",
  disclosed_holding_weight_low: "已披露持仓权重不足",
  factor_coverage_insufficient: "因子覆盖不足",
  manager_identity_missing: "基金经理信息缺失",
  policy_asset_type_not_allowed: "资产类型不在策略允许范围",
  policy_universe_excluded: "基金在策略排除清单中",
  target_exposure_below_minimum: "目标持仓低于最低要求",
};

// === 格式化工具 ===
const fmtWeight = (v: number | null | undefined) =>
  v === null || v === undefined ? "-" : `${(v * 100).toFixed(1)}%`;
const fmtScore = (v: number | null | undefined) =>
  v === null || v === undefined ? "-" : v.toFixed(2);
const fmtText = (v: string | null | undefined) =>
  v === null || v === undefined || v === "" ? "-" : v;
const fmtTime = (v: string | null | undefined) =>
  !v ? "-" : v.slice(0, 19).replace("T", " ");
const reasonLabel = (code: string) => REASON_LABELS[code] ?? code;
const renderEvidenceItem = (c: unknown): string =>
  typeof c === "string" ? c : JSON.stringify(c);

export default function PriorityWorkbenchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get("run") || "";
  const [runInput, setRunInput] = useState("");
  const [detail, setDetail] = useState<PriorityRunDetail | null>(null);
  const [historyRuns, setHistoryRuns] = useState<PriorityRunSummary[]>([]);
  const [selectedResultId, setSelectedResultId] = useState<string>("");
  const [activeTier, setActiveTier] = useState<TierKey>("research_now");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // === 加载 PriorityRun 详情（支持取消） ===
  useEffect(() => {
    if (!runId) {
      setDetail(null);
      setHistoryRuns([]);
      setSelectedResultId("");
      setError(null);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchPriorityRun(runId, controller.signal)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setSelectedResultId("");
        // 默认选中第一档第一个候选，并切到该档
        for (const tier of TIER_ORDER) {
          const candidates = data.candidates_by_tier?.[tier] ?? [];
          if (candidates.length > 0) {
            setSelectedResultId(candidates[0].priority_result_id);
            setActiveTier(tier);
            break;
          }
        }
      })
      .catch((e) => {
        if (cancelled || e?.name === "AbortError") return;
        setDetail(null);
        let msg = e instanceof Error ? e.message : String(e);
        if (msg.includes("404")) msg = `未找到 PriorityRun: ${runId}`;
        else if (msg.includes("500")) msg = "服务器内部错误，请稍后重试";
        else if (msg.includes("Failed to fetch")) msg = "网络连接失败，请检查后端服务是否运行";
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [runId]);

  // === 加载同 Thesis 的历史运行列表 ===
  useEffect(() => {
    if (!detail?.thesis_id) {
      setHistoryRuns([]);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    fetchPriorityRunsByThesis(detail.thesis_id, controller.signal)
      .then((runs) => {
        if (!cancelled) setHistoryRuns(runs);
      })
      .catch((e) => {
        if (cancelled || e?.name === "AbortError") return;
        setHistoryRuns([]);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [detail?.thesis_id]);

  // === URL 同步切换运行 ===
  const handleRunChange = (newId: string) => {
    setSearchParams(newId ? { run: newId } : {}, { replace: true });
  };
  const handleLoadInput = () => {
    const trimmed = runInput.trim();
    if (trimmed) handleRunChange(trimmed);
  };
  // 选中基金行：自动切换到对应档
  const handleSelect = (candidate: PriorityCandidate) => {
    setSelectedResultId(candidate.priority_result_id);
    setActiveTier(candidate.priority_tier as TierKey);
  };

  // === 派生：5档排序（按档内数量降序） ===
  const sortedTiers = useMemo(() => {
    if (!detail) return [] as TierKey[];
    return [...TIER_ORDER].sort((a, b) => {
      const ca = detail.tier_counts?.[a] ?? 0;
      const cb = detail.tier_counts?.[b] ?? 0;
      if (cb !== ca) return cb - ca;
      return TIER_ORDER.indexOf(a) - TIER_ORDER.indexOf(b);
    });
  }, [detail]);

  // === 派生：选中候选 ===
  const selectedCandidate: PriorityCandidate | null = useMemo(() => {
    if (!detail || !selectedResultId) return null;
    for (const tier of TIER_ORDER) {
      const candidates = detail.candidates_by_tier?.[tier] ?? [];
      const found = candidates.find((c) => c.priority_result_id === selectedResultId);
      if (found) return found;
    }
    return null;
  }, [detail, selectedResultId]);

  // === 错误 / 初始空态：仅显示输入框 ===
  if (error || !runId) {
    return (
      <Card>
        <div className="p-4 space-y-3">
          <h2 className="text-base font-semibold text-text m-0">投资假设详情 / 基金研究优先级</h2>
          {error && (
            <div
              className="rounded-lg border border-warn/30 bg-warn-soft px-3 py-2 text-warn-text text-sm flex items-center gap-3"
              role="alert"
            >
              <span className="flex-1">{error}</span>
              <button
                className="text-xs px-3 py-1 border border-warn/40 bg-surface text-warn-text rounded hover:bg-warn-soft transition-colors"
                onClick={() => {
                  setError(null);
                  const current = runId;
                  setSearchParams({}, { replace: true });
                  setTimeout(() => setSearchParams({ run: current }, { replace: true }), 0);
                }}
              >
                重试
              </button>
            </div>
          )}
          <p className="text-sm text-text-2">
            请输入 PriorityRun ID 加载工作台，或通过 URL 参数 ?run=xxx 直接访问。
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="priority-run-input" className="text-xs text-text-2">
              PriorityRun ID
            </label>
            <input
              id="priority-run-input"
              className="w-80 px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
              placeholder="输入 priority_run_id"
              value={runInput}
              onChange={(e) => setRunInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLoadInput();
              }}
              aria-label="PriorityRun ID 输入框"
            />
            <button
              className="px-4 py-1.5 text-sm font-semibold bg-accent text-surface border border-accent rounded hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleLoadInput}
              disabled={!runInput.trim()}
            >
              加载
            </button>
          </div>
          <p className="text-xs text-text-3">免责声明：研究顺序，不是买入建议。</p>
        </div>
      </Card>
    );
  }

  // === 加载中：轻量提示 ===
  if (!detail) {
    return (
      <div
        className="rounded-lg border border-accent/30 bg-accent-soft px-3 py-2 text-accent-text text-sm"
        role="status"
        aria-live="polite"
      >
        加载中...
      </div>
    );
  }

  // === 已加载：双栏主布局 ===
  return (
    <div className="space-y-3">
      <HeaderBar
        detail={detail}
        runId={runId}
        runInput={runInput}
        setRunInput={setRunInput}
        historyRuns={historyRuns}
        onLoadInput={handleLoadInput}
        onRunChange={handleRunChange}
      />

      {loading && (
        <div
          className="rounded-lg border border-accent/30 bg-accent-soft px-3 py-1.5 text-accent-text text-xs"
          role="status"
          aria-live="polite"
        >
          刷新中...
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-start">
        {/* === 主栏（左 col-span-8）===" */}
        <div className="lg:col-span-8 space-y-3 min-w-0">
          <Callout detail={detail} />
          <ThesisCard detail={detail} />
          <EvidenceCard detail={detail} />
          <TiersCard
            detail={detail}
            sortedTiers={sortedTiers}
            activeTier={activeTier}
            setActiveTier={setActiveTier}
            selectedResultId={selectedResultId}
            onSelect={handleSelect}
          />
          <InvalidationCard detail={detail} />
        </div>

        {/* === 详情栏（右 col-span-4，sticky）===" */}
        <div className="lg:col-span-4 lg:sticky lg:top-12 space-y-3">
          {selectedCandidate ? (
            <CandidateDetail candidate={selectedCandidate} />
          ) : (
            <Card>
              <div className="p-4 space-y-2">
                <h2 className="text-base font-semibold text-text m-0">选中基金详情</h2>
                <p className="text-sm text-text-3 m-0">点击左侧基金行查看详情。</p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* 底部免责声明 */}
      <div className="text-xs text-text-3 text-center py-2">免责声明：研究顺序，不是买入建议。</div>
    </div>
  );
}

// 头部（状态徽章 + URL 输入 + 历史下拉）
function HeaderBar(props: {
  detail: PriorityRunDetail;
  runId: string;
  runInput: string;
  setRunInput: (v: string) => void;
  historyRuns: PriorityRunSummary[];
  onLoadInput: () => void;
  onRunChange: (id: string) => void;
}) {
  const { detail, runId, runInput, setRunInput, historyRuns, onLoadInput, onRunChange } = props;
  return (
    <Card>
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant={
              detail.result_status === "completed"
                ? "pos"
                : detail.result_status === "running"
                  ? "accent"
                  : detail.result_status === "failed"
                    ? "neg"
                    : "neutral"
            }
          >
            PriorityRun：{detail.result_status}
          </Badge>
          <Badge variant="neutral">
            Strategy Policy: {detail.strategy_policy_id} v{detail.strategy_policy_version}
          </Badge>
          {detail.data_snapshot_id && (
            <Badge variant="neutral">Snapshot: {detail.data_snapshot_id.slice(0, 12)}</Badge>
          )}
          <Badge variant="neutral">Method: {detail.ranking_method_version}</Badge>
          {!detail.approved_for_production && <Badge variant="neg">非生产</Badge>}
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border">
          <label className="text-xs text-text-2" htmlFor="priority-run-input">
            PriorityRun URL
          </label>
          <input
            id="priority-run-input"
            className="flex-1 min-w-0 max-w-md px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
            placeholder="输入 priority_run_id"
            value={runInput}
            onChange={(e) => setRunInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onLoadInput();
            }}
            aria-label="PriorityRun ID 输入框"
          />
          <button
            className="px-4 py-1.5 text-sm font-semibold bg-accent text-surface border border-accent rounded hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={onLoadInput}
            disabled={!runInput.trim()}
          >
            加载
          </button>
          <label className="text-xs text-text-2 ml-2">历史运行</label>
          <select
            className="min-w-70 px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
            value={runId}
            onChange={(e) => onRunChange(e.target.value)}
            aria-label="历史运行选择"
          >
            {historyRuns.length === 0 ? (
              <option value={runId}>{runId.slice(0, 16)}</option>
            ) : (
              <>
                {!historyRuns.some((r) => r.priority_run_id === runId) && (
                  <option value={runId}>{runId.slice(0, 16)} (当前)</option>
                )}
                {historyRuns.map((r) => (
                  <option key={r.priority_run_id} value={r.priority_run_id}>
                    {r.created_at?.slice(0, 19).replace("T", " ")} ({r.priority_run_id.slice(0, 8)})
                  </option>
                ))}
              </>
            )}
          </select>
          <span className="text-xs text-text-3">共 {historyRuns.length} 个历史运行</span>
        </div>
      </div>
    </Card>
  );
}

// 一句话结论 callout（结论 + 4 KPI）
function Callout({ detail }: { detail: PriorityRunDetail }) {
  const tier = detail.tier_counts ?? {};
  const now = tier.research_now ?? 0;
  const next = tier.research_next ?? 0;
  const watch = tier.valuation_watch ?? 0;
  const insufficient = tier.data_insufficient ?? 0;
  const excluded = tier.excluded ?? 0;
  const scanned = detail.candidate_set_header?.scanned_fund_count ?? 0;
  const thesisName = detail.thesis?.title || "当前投资假设";
  // 一句话结论：投资假设 + 扫描 + 匹配 + 建议立即研究 + 下一步研究
  const summary = `${thesisName}：扫描 ${scanned} 只，匹配 ${detail.evaluated_candidate_count} 只，建议立即研究 ${now} 只，下一步研究 ${next} 只。`;
  return (
    <Card>
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="text-xs uppercase tracking-wide text-text-3">结论</span>
          <p className="text-base text-text m-0 leading-relaxed flex-1">{summary}</p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-border">
          <Stat label="扫描基金" value={scanned} />
          <Stat label="立即研究" value={now} variant="pos" />
          <Stat label="下一步研究" value={next} variant="accent" />
          <Stat label="估值观察" value={watch} variant="warn" />
        </div>
        {(insufficient > 0 || excluded > 0) && (
          <div className="text-xs text-text-3 pt-1">
            补充：数据不足 {insufficient} 只、排除 {excluded} 只
          </div>
        )}
      </div>
    </Card>
  );
}

// 投资假设卡（标题 + 信念 + 状态流程 + 元数据）
function ThesisCard({ detail }: { detail: PriorityRunDetail }) {
  const thesis = detail.thesis;
  const statusLabel = thesis?.status ? (THESIS_STATUS_LABELS[thesis.status] ?? thesis.status) : "—";
  // 状态流程：草稿 -> 研究中 -> 已验证 -> 已批准
  const flow = [
    { key: "draft", label: "草稿" },
    { key: "researching", label: "研究中" },
    { key: "validated", label: "已验证" },
    { key: "approved", label: "已批准" },
  ];
  const currentIdx = thesis?.status ? flow.findIndex((s) => s.key === thesis.status) : -1;
  return (
    <Card>
      <div className="p-4 space-y-3">
        {thesis && (
          <div>
            <h2 className="text-xl font-semibold text-text m-0 leading-tight">
              {thesis.title || "投资假设"}
            </h2>
            <p className="text-sm text-text-2 leading-relaxed m-0 mt-1">
              {thesis.belief_statement}
            </p>
          </div>
        )}

        {detail.research_input?.raw_text && (
          <div className="px-3 py-2 bg-surface-2 rounded border border-border text-xs text-text-3">
            <strong className="text-text-2">研究请求：</strong>
            {detail.research_input.raw_text}
          </div>
        )}

        {/* 状态流程条 */}
        {thesis && currentIdx >= 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-text-3 mr-1">状态流程：</span>
            {flow.map((s, i) => {
              const reached = i <= currentIdx;
              return (
                <span key={s.key} className="inline-flex items-center gap-1.5">
                  <span
                    className={`px-2 py-0.5 rounded border ${
                      reached
                        ? "bg-pos-soft text-pos-text border-pos/30"
                        : "bg-surface-2 text-text-3 border-border"
                    }`}
                  >
                    {s.label}
                  </span>
                  {i < flow.length - 1 && (
                    <span className={`${reached ? "text-pos" : "text-text-3"}`}>›</span>
                  )}
                </span>
              );
            })}
            <span className="ml-2 text-text-2">当前：{statusLabel}</span>
          </div>
        )}

        {/* 元数据栅格 4 列 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm pt-2 border-t border-border">
          <MetaItem label="状态" value={statusLabel} />
          <MetaItem label="时间范围" value={fmtText(thesis?.time_horizon)} />
          <MetaItem label="研究员" value={fmtText(thesis?.owner)} />
          <MetaItem label="截止日期" value={fmtText(thesis?.as_of_date)} />
          <MetaItem
            label="下次复审"
            value={thesis?.next_review_at ? thesis.next_review_at.slice(0, 10) : "-"}
          />
          <MetaItem label="创建人" value={fmtText(detail.created_by)} />
          <MetaItem label="创建时间" value={fmtTime(detail.created_at)} />
          <MetaItem
            label="方法版本"
            value={fmtText(detail.ranking_method_version)}
            mono
          />
        </div>
      </div>
    </Card>
  );
}

// 元数据项
function MetaItem({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <SectionTitle>{label}</SectionTitle>
      <div className={`text-text ${mono ? "font-mono text-xs" : ""}`}>{value}</div>
    </div>
  );
}


// 关键证据（叙事式分块）
function EvidenceCard({ detail }: { detail: PriorityRunDetail }) {
  const thesis = detail.thesis;
  const blocks: Array<{ key: string; title: string; variant: "pos" | "warn" | "accent" | "neutral"; items: unknown[] }> = [
    { key: "supporting", title: "支持证据", variant: "pos", items: (thesis?.supporting_evidence ?? []) as unknown[] },
    { key: "opposing", title: "反对证据", variant: "warn", items: (thesis?.opposing_evidence ?? []) as unknown[] },
    { key: "catalysts", title: "催化剂", variant: "accent", items: (thesis?.catalysts ?? []) as unknown[] },
    { key: "keyMetrics", title: "关键指标", variant: "neutral", items: (thesis?.key_metrics ?? []) as unknown[] },
  ];
  const visible = blocks.filter((b) => b.items.length > 0);
  if (visible.length === 0) return null;
  const titleColor: Record<"pos" | "warn" | "accent" | "neutral", string> = {
    pos: "text-pos-text", warn: "text-warn-text", accent: "text-accent-text", neutral: "text-text-2",
  };
  return (
    <Card>
      <div className="p-4 space-y-3">
        <h2 className="text-base font-semibold text-text m-0">关键证据</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {visible.map((b) => (
            <div key={b.key} className="px-3 py-2 bg-surface-2 rounded border border-border">
              <h3 className={`text-xs font-bold uppercase tracking-wide m-0 mb-1.5 ${titleColor[b.variant]}`}>
                {b.title}
              </h3>
              <ul className="m-0 pl-4 text-xs text-text-2 space-y-0.5">
                {b.items.slice(0, 5).map((c, i) => (
                  <li key={i}>{renderEvidenceItem(c)}</li>
                ))}
                {b.items.length > 5 && <li className="text-text-3 italic">…还有 {b.items.length - 5} 条</li>}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// 5 档基金（顶部 4 KPI + Tabs + 表格）
function TiersCard(props: {
  detail: PriorityRunDetail;
  sortedTiers: TierKey[];
  activeTier: TierKey;
  setActiveTier: (t: TierKey) => void;
  selectedResultId: string;
  onSelect: (c: PriorityCandidate) => void;
}) {
  const { detail, sortedTiers, activeTier, setActiveTier, selectedResultId, onSelect } = props;
  const header = detail.candidate_set_header;
  const candidates = detail.candidates_by_tier?.[activeTier] ?? [];
  return (
    <Card>
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold text-text m-0">基金候选（5 档）</h2>
          {header && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs flex-1 max-w-2xl">
              <HeaderKpi label="扫描基金" value={header.scanned_fund_count} />
              <HeaderKpi label="映射候选" value={header.mapped_candidate_count} />
              <HeaderKpi label="数据不足" value={header.unmapped_due_to_data_count} />
              <HeaderKpi label="不相关" value={header.unrelated_fund_count} />
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-1 border-b border-border -mx-1">
          {sortedTiers.map((tier) => {
            const cfg = TIER_CONFIG[tier];
            const count = detail.tier_counts?.[tier] ?? 0;
            const isActive = tier === activeTier;
            const empty = count === 0;
            return (
              <button
                key={tier}
                onClick={() => !empty && setActiveTier(tier)}
                className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  isActive
                    ? "border-accent text-accent"
                    : empty
                      ? "border-transparent text-text-3 cursor-not-allowed"
                      : "border-transparent text-text-2 hover:text-text"
                }`}
              >
                <span className="inline-flex items-center gap-1.5">
                  <Badge variant={cfg.variant} className="!py-0">{cfg.label}</Badge>
                  <span className="text-xs text-text-3 font-mono">{count}</span>
                </span>
              </button>
            );
          })}
        </div>

        {candidates.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th className="w-14 text-right">排名</Th>
                <Th className="w-24">代码</Th>
                <Th>名称</Th>
                <Th className="w-28 text-right">真实持仓</Th>
                <Th className="w-24 text-right">披露覆盖</Th>
                <Th className="w-28">数据质量</Th>
                <Th className="w-20 text-right">证据分</Th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => (
                <tr
                  key={c.priority_result_id}
                  tabIndex={0}
                  aria-selected={selectedResultId === c.priority_result_id}
                  onClick={() => onSelect(c)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(c);
                    }
                  }}
                  className={`cursor-pointer outline-none focus:outline-2 focus:outline-accent focus:-outline-offset-2 ${
                    selectedResultId === c.priority_result_id
                      ? "bg-accent-soft"
                      : "hover:bg-surface-2"
                  }`}
                >
                  <Td className="text-right tabular-nums">{c.priority_rank ?? "-"}</Td>
                  <Td className="font-mono font-bold">{c.fund_code}</Td>
                  <Td className="text-text-2">{fmtText(c.fund_name)}</Td>
                  <Td className="text-right tabular-nums">{fmtWeight(c.matched_holding_weight)}</Td>
                  <Td className="text-right tabular-nums">{fmtWeight(c.disclosed_holding_weight)}</Td>
                  <Td>{fmtText(c.data_quality_status)}</Td>
                  <Td className="text-right tabular-nums">{fmtScore(c.evidence_score)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <div className="text-center py-8 text-xs text-text-3">该档位暂无候选</div>
        )}
      </div>
    </Card>
  );
}

// 候选集头部 KPI
function HeaderKpi({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span className="text-text-3">{label}：</span>
      <strong className="text-text font-mono">{value}</strong>
    </div>
  );
}

// 失效条件（仅在有内容时展示）
function InvalidationCard({ detail }: { detail: PriorityRunDetail }) {
  const conditions = (detail.thesis?.invalidation_conditions ?? []) as unknown[];
  if (conditions.length === 0) return null;
  return (
    <Card>
      <div className="p-4 space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wide text-neg-text m-0">失效条件</h3>
        <ul className="m-0 pl-5 text-xs text-text-2 space-y-0.5">
          {conditions.map((c, i) => (
            <li key={i}>{renderEvidenceItem(c)}</li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

// 选中基金详情（详情栏 sticky）
function CandidateDetail({ candidate }: { candidate: PriorityCandidate }) {
  const tier = candidate.priority_tier as TierKey | undefined;
  const config = tier ? TIER_CONFIG[tier] : undefined;
  const matchPct = candidate.normalized_match_pct ?? 0;
  return (
    <Card>
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2 border-b border-border pb-2">
          <div className="min-w-0">
            <div className="font-mono font-bold text-text text-base">{candidate.fund_code}</div>
            <div className="text-sm text-text-2 truncate">{fmtText(candidate.fund_name)}</div>
          </div>
          {config ? (
            <Badge variant={config.variant}>{config.label}</Badge>
          ) : (
            <Badge variant="neutral">{candidate.priority_tier}</Badge>
          )}
        </div>

        {/* 匹配度进度条：标题 + 进度条 + 数字（叙事式） */}
        <div>
          <SectionTitle>匹配度</SectionTitle>
          <ProgressBar value={matchPct * 100} variant="accent" showValue={false} />
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-xs text-text-3">归一化匹配率</span>
            <span className="text-base font-mono font-semibold text-text tabular-nums">
              {fmtWeight(candidate.normalized_match_pct)}
            </span>
          </div>
        </div>

        <div>
          <SectionTitle>基本信息</SectionTitle>
          <dl className="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1 text-sm m-0">
            <DataRow label="档内排名" value={candidate.priority_rank ?? "-"} mono />
            <DataRow label="资格状态" value={fmtText(candidate.eligibility_status)} />
            <DataRow label="报告日期" value={fmtText(candidate.holding_report_date)} />
          </dl>
        </div>

        <div>
          <SectionTitle>关键指标</SectionTitle>
          <dl className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-sm m-0">
            <DataRow label="真实目标持仓" value={fmtWeight(candidate.matched_holding_weight)} mono />
            <DataRow label="已披露持仓" value={fmtWeight(candidate.disclosed_holding_weight)} mono />
            <DataRow label="归一化匹配率" value={fmtWeight(candidate.normalized_match_pct)} mono />
            <DataRow label="适配分" value={fmtScore(candidate.fit_score)} mono />
            <DataRow label="证据分" value={fmtScore(candidate.evidence_score)} mono />
          </dl>
        </div>

        <div>
          <SectionTitle>状态信息</SectionTitle>
          <dl className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-sm m-0">
            <DataRow label="数据质量" value={fmtText(candidate.data_quality_status)} />
            <DataRow label="估值状态" value={fmtText(candidate.valuation_status)} />
            <DataRow label="持仓真实度" value={fmtText(candidate.holdings_truth_status)} />
          </dl>
        </div>

        {candidate.priority_reasons.length > 0 && (
          <div>
            <SectionTitle>稳定原因码</SectionTitle>
            <ul className="m-0 pl-4 text-xs space-y-0.5">
              {candidate.priority_reasons.map((r, i) => (
                <li key={`${r.code}-${i}`}>
                  <strong className="font-semibold text-text">{reasonLabel(r.code)}</strong>
                  {r.message && <span className="text-text-3 ml-1.5">· {r.message}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {candidate.exclusion_reasons.length > 0 && (
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-neg-text m-0 mb-1.5">排除原因码</h3>
            <ul className="m-0 pl-4 text-xs space-y-0.5 text-neg-text">
              {candidate.exclusion_reasons.map((r, i) => (
                <li key={`${r.code}-${i}`}>
                  <strong className="font-semibold">{reasonLabel(r.code)}</strong>
                  {r.message && <span className="text-text-3 ml-1.5">· {r.message}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}

// dl/dt/dd 单行（兼容 e2e 选择器）
function DataRow({ label, value, mono }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <>
      <dt className="text-text-3">{label}</dt>
      <dd className={`text-text m-0 ${mono ? "font-mono tabular-nums" : ""}`}>{value}</dd>
    </>
  );
}
