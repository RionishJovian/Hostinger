import { Link } from "@tanstack/react-router";
import { ArrowRight, CircleCheck, Router, ShieldCheck, Ticket, UsersRound, Wifi } from "lucide-react";
import { LoadState, PageIntro, displayValue, useEndpoint } from "../components/AsyncPanel";

type Overview = Record<string, unknown>;

export function HomePage() {
  const state = useEndpoint<Overview>("/v1/owner/overview");
  const values = state.data ?? {};
  const metric = (keys: string[]) => keys.map((key) => values[key]).find((value) => value !== undefined);
  return <>
    <PageIntro kicker="Your shop today" title="Good to see you" description="A quick look at your Wi-Fi business, routers and guests." />
    <LoadState loading={state.loading} error={state.error} unavailable={state.unavailable}>
      <section className="metrics">
        <Metric icon={Wifi} label="Connected routers" value={metric(["connected_routers", "connectedRouters"])} />
        <Metric icon={UsersRound} label="Guests online" value={metric(["active_sessions", "activeSessions"])} />
        <Metric icon={Ticket} label="Active vouchers" value={metric(["active_vouchers", "activeVouchers"])} />
        <Metric icon={CircleCheck} label="Open incidents" value={metric(["open_incidents", "openIncidents"])} />
      </section>
      <section className="feature-panel"><div><p className="kicker">Magic Hub</p><h2>Your router, safely within reach</h2><p>Connect once, then monitor the hotspot and review protected changes from MikroMagic.</p><Link to="/app/routers" className="primary">Open routers <ArrowRight size={17} /></Link></div><div className="network-art" aria-hidden><span><Wifi /></span><i /><span><Router /></span><i /><span className="hub-node">M</span></div></section>
      <section><div className="section-heading"><div><p className="kicker">Quick actions</p><h2>Run your business</h2></div></div><div className="action-grid"><Action to="/app/easy/vouchers" icon={Ticket} title="Create vouchers" body="Prepare access codes for guests" /><Action to="/app/live" icon={UsersRound} title="See live guests" body="Check current hotspot sessions" /><Action to="/app/audit" icon={ShieldCheck} title="Review activity" body="See protected business and router actions" /><Action to="/app/routers" icon={Router} title="Router health" body="See connection and health status" /></div></section>
    </LoadState>
  </>;
}

function Metric({ icon: Icon, label, value }: { icon: typeof Wifi; label: string; value: unknown }) {
  return <article className="metric-card"><span><Icon /></span><div><strong>{displayValue(value)}</strong><small>{label}</small></div></article>;
}

function Action({ to, icon: Icon, title, body }: { to: string; icon: typeof Wifi; title: string; body: string }) {
  return <Link to={to} className="action-card"><span><Icon /></span><div><strong>{title}</strong><small>{body}</small></div><ArrowRight size={17} /></Link>;
}
