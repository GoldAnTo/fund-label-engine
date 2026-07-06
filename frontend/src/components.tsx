import { useEffect, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshCounter, setRefreshCounter] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fn()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refreshCounter]);

  return { data, error, loading, refresh: () => setRefreshCounter((c) => c + 1) };
}

export function reviewActionLabel(value: string) {
  const labels: Record<string, string> = {
    manual_review: "需复核",
    observe: "观察",
    confirm: "确认",
    reject: "驳回",
  };
  return labels[value] ?? value;
}

export function labelStatusLabel(value: string) {
  const labels: Record<string, string> = {
    active: "已命中",
    observe: "观察",
    inactive: "未命中",
  };
  return labels[value] ?? value;
}

export function runStatusLabel(value: string) {
  const labels: Record<string, string> = {
    succeeded: "成功",
    failed: "失败",
    running: "运行中",
    pending: "等待中",
  };
  return labels[value] ?? value;
}

export function ReviewActionBadge({ value }: { value: string }) {
  const cls = value === "manual_review" ? "badge-manual_review" : "badge-observe";
  return <span className={`badge ${cls}`}>{reviewActionLabel(value)}</span>;
}

export function LabelStatusBadge({ value }: { value: string }) {
  const cls = value === "observe" ? "badge-manual_review" : "badge-active";
  return <span className={`badge ${cls}`}>{labelStatusLabel(value)}</span>;
}
