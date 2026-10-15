import type { LucideIcon } from "lucide-react";
import { RefreshCw } from "lucide-react";
import { LoadState, PageIntro, displayValue, safeEntries, useEndpoint } from "../components/AsyncPanel";

type Props = {
  title: string;
  description: string;
  endpoint: string;
  icon: LucideIcon;
  fields?: string[];
  itemName: string;
};

function rowsFrom(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== "object") return [];
  const record = value as Record<string, unknown>;
  for (const key of ["items", "routers", "connectors", "ledger", "sites", "lines"]) {
    if (Array.isArray(record[key])) return record[key] as unknown[];
  }
  return [record];
}

export function OwnerReadPage({ title, description, endpoint, icon: Icon, fields, itemName }: Props) {
  const state = useEndpoint<unknown>(endpoint);
  const rows = rowsFrom(state.data);
  return <>
    <PageIntro title={title} description={description} action={<button className="secondary" onClick={() => void state.refresh()} disabled={state.loading}><RefreshCw size={16} /> Refresh</button>} />
    <div className="read-only-note">View only — any router change must use a reviewed Safe Change.</div>
    <LoadState loading={state.loading} error={state.error} unavailable={state.unavailable} empty={!rows.length}>
      <section className="data-grid">{rows.map((value, index) => {
        const row = value && typeof value === "object" ? value as Record<string, unknown> : { value };
        return <article className="data-card" key={String(row.id ?? row.router_id ?? index)}><div className="card-icon"><Icon /></div><div className="data-card-body"><h2>{String(row.name ?? row.router_name ?? row.operation ?? `${itemName} ${index + 1}`)}</h2><dl>{safeEntries(row, fields).map(([key, entry]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{displayValue(entry)}</dd></div>)}</dl></div></article>;
      })}</section>
    </LoadState>
  </>;
}
