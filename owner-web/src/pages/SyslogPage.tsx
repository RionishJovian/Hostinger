import { FileSearch2 } from "lucide-react";
import { useState } from "react";
import { post } from "../lib/api";
import { EmptyState, LoadState, PageIntro, useEndpoint } from "../components/AsyncPanel";

export function SyslogPage() {
  const state = useEndpoint<{ status?: string; lines?: string[] }>("/v1/owner/syslog");
  const [explanations, setExplanations] = useState<Record<number, string>>({});
  const lines = state.data?.lines ?? [];
  async function explain(line: string, index: number) {
    const result = await post<Record<string, unknown>>("/v1/owner/syslog/explain", { line });
    setExplanations((current) => ({ ...current, [index]: result.status === "coming_soon" ? "Explanation is coming soon." : String(result.explanation ?? "No explanation available.") }));
  }
  return <><PageIntro title="Syslog" description="Read router log lines and request an explanation for one line at a time." /><LoadState loading={state.loading} error={state.error} unavailable={state.unavailable} empty={!lines.length}>{lines.length ? <section className="panel log-list">{lines.map((line, index) => <article key={`${index}-${line}`}><code>{line}</code><button className="secondary" onClick={() => void explain(line, index)}><FileSearch2 size={16} /> Explain</button>{explanations[index] && <p>{explanations[index]}</p>}</article>)}</section> : <EmptyState title="Coming soon" body="Router syslog collection is not connected yet." />}</LoadState></>;
}
