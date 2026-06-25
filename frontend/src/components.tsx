import { useEffect, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
  }, deps);

  return { data, error, loading, refresh: () => setLoading(true) };
}

export function ReviewActionBadge({ value }: { value: string }) {
  const cls = value === "manual_review" ? "badge-manual_review" : "badge-observe";
  const label = value === "manual_review" ? "需复核" : "观察";
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function LabelStatusBadge({ value }: { value: string }) {
  const cls = value === "observe" ? "badge-manual_review" : "badge-active";
  return <span className={`badge ${cls}`}>{value}</span>;
}
