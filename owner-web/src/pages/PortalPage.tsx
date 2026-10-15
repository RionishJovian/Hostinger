import { Radio, ShieldCheck, Ticket } from "lucide-react";
import { LoadState, PageIntro, displayValue, useEndpoint } from "../components/AsyncPanel";

type PortalState = { published_revision?: number | null; router_deployment_status?: string; published?: { language?: string; voucher_login?: boolean } | null };

export function PortalPage() {
  const state = useEndpoint<PortalState>("/v1/portal");
  return <>
    <PageIntro kicker="Guest access" title="Guest login" description="See the status of MikroMagic's one-box voucher login. Page editing is not available in the owner app." />
    <div className="read-only-note">View only — router installation or replacement must use a reviewed Safe Change with backup and rollback checks.</div>
    <LoadState loading={state.loading} error={state.error} unavailable={state.unavailable}>
      <section className="restored-sections">
        <article className="panel restored-section"><div className="restored-section-heading"><span className="card-icon"><Ticket /></span><div><h2>One voucher-code box</h2><p>Guest codes work in any letter case and ignore spaces and dashes.</p></div></div><dl><div><dt>Published revision</dt><dd>{displayValue(state.data?.published_revision)}</dd></div><div><dt>Language</dt><dd>{displayValue(state.data?.published?.language)}</dd></div></dl></article>
        <article className="panel restored-section"><div className="restored-section-heading"><span className="card-icon"><Radio /></span><div><h2>Router status</h2><p>Cloud content and router-installed files are separate states.</p></div></div><dl><div><dt>Deployment</dt><dd>{displayValue(state.data?.router_deployment_status)}</dd></div></dl></article>
        <article className="panel restored-section"><div className="restored-section-heading"><span className="card-icon"><ShieldCheck /></span><div><h2>First Customer Test</h2><p>A real phone, voucher login and Internet session are required before Site Ready.</p></div></div><div className="inline-empty"><strong>Coming soon</strong><span>Real phone acceptance is not available from this screen.</span></div></article>
      </section>
    </LoadState>
  </>;
}
