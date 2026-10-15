import type { LucideIcon } from "lucide-react";
import { RefreshCw } from "lucide-react";
import { LoadState, PageIntro, displayValue, safeEntries, useEndpoint } from "../components/AsyncPanel";

type DataPageProps = {
  title: string;
  description: string;
  endpoint: string;
  icon: LucideIcon;
  itemName: string;
  fields?: string[];
  kicker?: string;
  readOnly?: boolean;
};

export function DataPage({ title, description, endpoint, icon: Icon, itemName, fields, kicker, readOnly }: DataPageProps) {
  const state = useEndpoint<unknown>(endpoint);
  const rows = Array.isArray(state.data) ? state.data : state.data && typeof state.data === "object" ? [state.data] : [];
  return <>
    <PageIntro kicker={kicker} title={title} description={description} action={<button className="secondary" onClick={() => void state.refresh()} disabled={state.loading}><RefreshCw size={16} /> Refresh</button>} />
    {readOnly && <div className="read-only-note">View only — changes are not available from this screen.</div>}
    <LoadState loading={state.loading} error={state.error} unavailable={state.unavailable} empty={!rows.length}>
      <section className="data-grid">{rows.map((value, index) => {
        const row = value && typeof value === "object" ? value as Record<string, unknown> : { value } as Record<string, unknown>;
        const entries = safeEntries(row, fields);
        return <article className="data-card" key={String(row.id ?? index)}><div className="card-icon"><Icon /></div><div className="data-card-body"><h2>{String(row.name ?? row.title ?? row.action ?? `${itemName} ${index + 1}`)}</h2><dl>{entries.map(([key, entry]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{displayValue(entry)}</dd></div>)}</dl></div></article>;
      })}</section>
    </LoadState>
  </>;
}
