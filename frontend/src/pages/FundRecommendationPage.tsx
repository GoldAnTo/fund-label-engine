// 主题基金推荐 - 双轨榜单（主动基金 / ETF·指数基金）+ 最终组合

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchRecommendationRun,
  fetchRecommendationRunsByThesis,
  type RecommendationPortfolio,
  type RecommendationResult,
  type RecommendationRunDetail,
  type RecommendationRunSummary,
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

// === 推荐档位配置 ===
const TIER_CONFIG: Record<
  string,
  { label: string; variant: "pos" | "accent" | "warn" | "neutral" | "neg" }
> = {
  candidate_pool: { label: "建议纳入候选池", variant: "pos" },
  alternative: { label: "备选", variant: "accent" },
  watch: { label: "观察", variant: "warn" },
  excluded: { label: "排除", variant: "neg" },
  data_insufficient: { label: "数据不足", variant: "neutral" },
};

// === 四项评分标签 ===
const SCORE_LABELS: Array<{ key: string; label: string }> = [
  { key: "theme_exposure_score", label: "主题暴露纯度" },
  { key: "thesis_alignment_score", label: "投资假设匹配" },
  { key: "risk_return_score", label: "风险收益" },
  { key: "fund_quality_score", label: "基金质量" },
];

// === 格式化工具 ===
const fmtScore = (v: number | null | undefined) =>
  v === null || v === undefined ? "-" : v.toFixed(2);
const fmtPct = (v: number | null | undefined) =>
  v === null || v === undefined ? "-" : `${v.toFixed(1)}%`;
const fmtText = (v: string | null | undefined) =>
  v === null || v === undefined || v === "" ? "-" : v;
const tierLabel = (t: string) => TIER_CONFIG[t]?.label ?? t;

export default function FundRecommendationPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get("run") || "";
  const [runInput, setRunInput] = useState("");
  const [detail, setDetail] = useState<RecommendationRunDetail | null>(null);
  const [historyRuns, setHistoryRuns] = useState<RecommendationRunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // === 加载 RecommendationRun 详情 ===
  useEffect(() => {
    if (!runId) {
      setDetail(null);
      setHistoryRuns([]);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRecommendationRun(runId, controller.signal)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
      })
      .catch((e) => {
        if (cancelled || e?.name === "AbortError") return;
        setDetail(null);
        let msg = e instanceof Error ? e.message : String(e);
        if (msg.includes("404")) msg = `未找到推荐运行: ${runId}`;
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
    fetchRecommendationRunsByThesis(detail.thesis_id, controller.signal)
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

  const handleRunChange = (newId: string) => {
    setSearchParams(newId ? { run: newId } : {}, { replace: true });
  };
  const handleLoadInput = () => {
    const trimmed = runInput.trim();
    if (trimmed) handleRunChange(trimmed);
  };

  // === 派生：两个类别的候选 ===
  const activeFunds = useMemo(
    () => detail?.candidates_by_category?.active_fund ?? [],
    [detail],
  );
  const etfFunds = useMemo(
    () => detail?.candidates_by_category?.etf_or_index ?? [],
    [detail],
  );

  // === 派生：组合是否展示 ===
  const portfolio = detail?.portfolio ?? null;
  const showPortfolio =
    portfolio != null && portfolio.selection_source === "recommended_universe";

  // === 错误 / 初始空态 ===
  if (error || !runId) {
    return (
      <Card>
        <div className="p-4 space-y-3">
          <h1 className="text-base font-semibold text-text m-0">主题基金推荐</h1>
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
            请输入 RecommendationRun ID 加载推荐结果，或通过 URL 参数 ?run=xxx 直接访问。
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="rec-run-input" className="text-xs text-text-2">
              RecommendationRun ID
            </label>
            <input
              id="rec-run-input"
              className="w-80 px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
              placeholder="输入 recommendation_run_id"
              value={runInput}
              onChange={(e) => setRunInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLoadInput();
              }}
              aria-label="RecommendationRun ID 输入框"
            />
            <button
              className="px-4 py-1.5 text-sm font-semibold bg-accent text-surface border border-accent rounded hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleLoadInput}
              disabled={!runInput.trim()}
            >
              加载
            </button>
          </div>
          <p className="text-xs text-text-3">免责声明：推荐结果，不是买入建议。</p>
        </div>
      </Card>
    );
  }

  // === 加载中 ===
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

      <FundListCard
        title="主动基金推荐"
        funds={activeFunds}
        emptyHint="没有满足主题暴露和数据门槛的主动基金"
      />
      <FundListCard
        title="ETF / 指数基金推荐"
        funds={etfFunds}
        emptyHint="没有满足主题暴露和数据门槛的 ETF / 指数基金"
      />

      {showPortfolio && <PortfolioCard portfolio={portfolio} />}

      <div className="text-xs text-text-3 text-center py-2">免责声明：推荐结果，不是买入建议。</div>
    </div>
  );
}

// === 头部：Thesis / 快照 / 运行 ID ===
function HeaderBar(props: {
  detail: RecommendationRunDetail;
  runId: string;
  runInput: string;
  setRunInput: (v: string) => void;
  historyRuns: RecommendationRunSummary[];
  onLoadInput: () => void;
  onRunChange: (id: string) => void;
}) {
  const { detail, runId, runInput, setRunInput, historyRuns, onLoadInput, onRunChange } = props;
  const thesis = detail.thesis;
  return (
    <Card>
      <div className="p-4 space-y-3">
        <h1 className="text-xl font-semibold text-text m-0">主题基金推荐</h1>
        {thesis && (
          <div>
            <h2 className="text-base font-semibold text-text m-0 leading-tight">
              {thesis.title || "投资假设"}
            </h2>
            {thesis.belief_statement && (
              <p className="text-sm text-text-2 leading-relaxed m-0 mt-1">
                {thesis.belief_statement}
              </p>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="neutral">Run: {detail.recommendation_run_id.slice(0, 16)}</Badge>
          <Badge variant="neutral">
            Strategy: {detail.strategy_policy_id} v{detail.strategy_policy_version}
          </Badge>
          {detail.data_snapshot_id && (
            <Badge variant="neutral">Snapshot: {detail.data_snapshot_id.slice(0, 12)}</Badge>
          )}
          <Badge variant="neutral">Method: {detail.recommendation_method_version}</Badge>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-border">
          <Stat label="评估候选" value={detail.evaluated_candidate_count} />
          <Stat label="建议纳入候选池" value={detail.recommended_count} variant="pos" />
          <Stat
            label="备选"
            value={detail.tier_counts?.alternative ?? 0}
            variant="accent"
          />
          <Stat
            label="扫描基金"
            value={detail.candidate_set_header?.scanned_fund_count ?? "-"}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border">
          <label className="text-xs text-text-2" htmlFor="rec-run-input">
            RecommendationRun URL
          </label>
          <input
            id="rec-run-input"
            className="flex-1 min-w-0 max-w-md px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
            placeholder="输入 recommendation_run_id"
            value={runInput}
            onChange={(e) => setRunInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onLoadInput();
            }}
            aria-label="RecommendationRun ID 输入框"
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
            className="min-w-60 px-3 py-1.5 text-sm border border-border-2 rounded bg-surface text-text focus:outline-none focus:border-accent"
            value={runId}
            onChange={(e) => onRunChange(e.target.value)}
            aria-label="历史运行选择"
          >
            {historyRuns.length === 0 ? (
              <option value={runId}>{runId.slice(0, 16)}</option>
            ) : (
              <>
                {!historyRuns.some((r) => r.recommendation_run_id === runId) && (
                  <option value={runId}>{runId.slice(0, 16)} (当前)</option>
                )}
                {historyRuns.map((r) => (
                  <option key={r.recommendation_run_id} value={r.recommendation_run_id}>
                    {r.created_at?.slice(0, 19).replace("T", " ")} ({r.recommendation_run_id.slice(0, 8)})
                  </option>
                ))}
              </>
            )}
          </select>
        </div>
      </div>
    </Card>
  );
}

// === 基金榜单卡（主动 / ETF 通用） ===
function FundListCard(props: {
  title: string;
  funds: RecommendationResult[];
  emptyHint: string;
}) {
  const { title, funds, emptyHint } = props;
  return (
    <Card>
      <div className="p-4 space-y-3">
        <h2 className="text-base font-semibold text-text m-0">{title}</h2>
        {funds.length > 0 ? (
          <div className="space-y-3">
            <Table>
              <thead>
                <tr>
                  <Th className="w-14 text-right">排名</Th>
                  <Th className="w-24">代码</Th>
                  <Th>名称</Th>
                  <Th className="w-20">档位</Th>
                  <Th className="w-20 text-right">总分</Th>
                  <Th className="w-28 text-right">主题暴露纯度</Th>
                </tr>
              </thead>
              <tbody>
                {funds.map((f) => (
                  <tr key={f.recommendation_result_id}>
                    <Td className="text-right tabular-nums">{f.category_rank ?? "-"}</Td>
                    <Td className="font-mono font-bold">{f.fund_code}</Td>
                    <Td className="text-text-2">{fmtText(f.fund_name)}</Td>
                    <Td>
                      <Badge variant={TIER_CONFIG[f.recommendation_tier]?.variant ?? "neutral"}>
                        {tierLabel(f.recommendation_tier)}
                      </Badge>
                    </Td>
                    <Td className="text-right tabular-nums">{fmtScore(f.total_score)}</Td>
                    <Td className="text-right tabular-nums">
                      {fmtScore(f.theme_exposure_score)}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>

            {/* 单基金详情：四项评分、理由、未选原因、证据日期 */}
            <div className="space-y-2">
              {funds.map((f) => (
                <FundDetail key={`detail-${f.recommendation_result_id}`} fund={f} />
              ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-6 text-xs text-text-3">{emptyHint}</div>
        )}
      </div>
    </Card>
  );
}

// === 单基金详情 ===
function FundDetail({ fund }: { fund: RecommendationResult }) {
  const evidence = fund.frozen_evidence ?? {};
  const evidenceDate = (evidence.holding_report_date as string | null | undefined) ?? null;
  const reasons = (fund.recommendation_reasons ?? []).slice(0, 3);
  const exclusions = fund.exclusion_reasons ?? [];
  const cfg = TIER_CONFIG[fund.recommendation_tier];
  return (
    <div className="px-3 py-2 bg-surface-2 rounded border border-border space-y-2">
      {/* 基金标题行 */}
      <div className="flex items-center gap-2">
        <span className="font-mono font-bold text-text">{fund.fund_code}</span>
        <span className="text-sm text-text-2">{fmtText(fund.fund_name)}</span>
        {cfg && <Badge variant={cfg.variant}>{cfg.label}</Badge>}
        <span className="text-xs text-text-3 ml-auto">类内排名 #{fund.category_rank ?? "-"}</span>
      </div>

      {/* 四项评分 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {SCORE_LABELS.map((s) => {
          const raw = fund[s.key as keyof RecommendationResult] as number | null;
          return (
            <div key={s.key}>
              <SectionTitle>{s.label}</SectionTitle>
              <ProgressBar
                value={(raw ?? 0) * 100}
                variant={cfg?.variant ?? "neutral"}
                showValue={false}
              />
              <div className="text-xs font-mono text-text-2 text-right">{fmtScore(raw)}</div>
            </div>
          );
        })}
      </div>

      {/* 理由（三条以内） */}
      {reasons.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-text-3 m-0 mb-1">推荐理由</h3>
          <ul className="m-0 pl-4 text-xs text-text-2 space-y-0.5">
            {reasons.map((r, i) => (
              <li key={`${r.code}-${i}`}>
                <strong className="font-semibold text-text">{r.code}</strong>
                {r.message && <span className="text-text-3 ml-1.5">· {r.message}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 未选原因 */}
      {exclusions.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-neg-text m-0 mb-1">未选原因</h3>
          <ul className="m-0 pl-4 text-xs text-neg-text space-y-0.5">
            {exclusions.map((r, i) => (
              <li key={`${r.code}-${i}`}>
                <strong className="font-semibold">{r.code}</strong>
                {r.message && <span className="text-text-3 ml-1.5">· {r.message}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 证据日期 */}
      <div className="text-xs text-text-3">
        证据日期：{fmtText(evidenceDate)}
      </div>
    </div>
  );
}

// === 最终组合建议 ===
function PortfolioCard({ portfolio }: { portfolio: RecommendationPortfolio }) {
  const holdings = portfolio.holdings ?? [];
  const enforcedActions = portfolio.enforced_actions ?? [];
  const metrics = portfolio.metrics ?? {};
  return (
    <Card>
      <div className="p-4 space-y-3">
        <h2 className="text-base font-semibold text-text m-0">最终组合建议</h2>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="pos">来源：推荐池</Badge>
          <Badge variant="neutral">状态：{portfolio.status ?? "-"}</Badge>
          {portfolio.recommendation_run_ids && (
            <Badge variant="neutral">
              Run: {portfolio.recommendation_run_ids.join(", ").slice(0, 16)}
            </Badge>
          )}
        </div>

        {/* 持仓表 */}
        {holdings.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th className="w-24">代码</Th>
                <Th>名称</Th>
                <Th className="w-28 text-right">权重</Th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, i) => (
                <tr key={`${h.fund_code}-${i}`}>
                  <Td className="font-mono font-bold">{h.fund_code}</Td>
                  <Td className="text-text-2">{fmtText(h.fund_name)}</Td>
                  <Td className="text-right tabular-nums">{fmtPct(h.weight)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <div className="text-center py-4 text-xs text-text-3">组合无持仓</div>
        )}

        {/* 风险强制调权 */}
        {enforcedActions.length > 0 && (
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-warn-text m-0 mb-1.5">
              风险强制调权
            </h3>
            <ul className="m-0 pl-4 text-xs text-text-2 space-y-0.5">
              {enforcedActions.map((a, i) => (
                <li key={`${a.fund_code}-${i}`}>
                  <strong className="font-semibold text-text">{a.type}</strong>
                  <span className="font-mono ml-1.5">{a.fund_code}</span>
                  <span className="text-text-3 ml-1.5">· {a.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 更新后的指标 */}
        {Object.keys(metrics).length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-border">
            {Object.entries(metrics).map(([k, v]) => (
              <Stat key={k} label={k} value={typeof v === "number" ? v.toFixed(3) : String(v)} />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
