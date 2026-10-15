import { useCallback, useEffect, useState } from "react";
import { ApiError, get } from "../lib/api";

export function useEndpoint<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState("");
  const [unavailable, setUnavailable] = useState(false);
  const refresh = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError("");
    setUnavailable(false);
    try {
      setData(await get<T>(path));
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) setUnavailable(true);
      else setError(cause instanceof Error ? cause.message : "Could not load this page.");
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { data, loading, error, unavailable, refresh };
}

export function PageIntro({ kicker, title, description, action }: { kicker?: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="page-intro">
    <div>{kicker && <p className="kicker">{kicker}</p>}<h1>{title}</h1><p>{description}</p></div>
    {action}
  </header>;
}

export function LoadState({ loading, error, unavailable, empty, children }: { loading: boolean; error: string; unavailable?: boolean; empty?: boolean; children: React.ReactNode }) {
  if (loading) return <div className="skeleton-stack" aria-label="Loading"><span /><span /><span /></div>;
  if (unavailable) return <EmptyState title="Not available yet" body="This feature is not connected to the MikroMagic engine yet." />;
  if (error) return <EmptyState title="We couldn't load this" body={error} tone="danger" />;
  if (empty) return <EmptyState title="Nothing here yet" body="New activity will appear here when it is available." />;
  return <>{children}</>;
}

export function EmptyState({ title, body, tone = "normal" }: { title: string; body: string; tone?: "normal" | "danger" }) {
  return <section className={`empty-state ${tone === "danger" ? "danger" : ""}`}><div className="empty-mark">{tone === "danger" ? "!" : "·"}</div><h2>{title}</h2><p>{body}</p></section>;
}

const blockedFields = /(password|passphrase|private|public_key|secret|credential|token|endpoint|address|unlock|checksum|storage_ref)/i;

export function safeEntries(record: Record<string, unknown>, preferred: string[] = []) {
  const keys = preferred.length ? preferred : Object.keys(record);
  return keys.filter((key) => key in record && !blockedFields.test(key)).map((key) => [key, record[key]] as const);
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && value > 1_000_000_000) return new Date(value * 1000).toLocaleString();
  if (typeof value === "object") return Array.isArray(value) ? `${value.length} items` : "Available";
  return String(value).replaceAll("_", " ");
}
