import { Link } from "@tanstack/react-router";
import { ArrowRight, CircleCheck, Printer, Router, Ticket, UsersRound } from "lucide-react";
import { LoadState, PageIntro, displayValue, useEndpoint } from "../components/AsyncPanel";

export function EasyPage() {
  const state = useEndpoint<Record<string, unknown>>("/v1/owner/overview");
  return <><PageIntro kicker="Your hotspot, simplified" title="Easy mode" description="The everyday jobs for your counter and guest Wi-Fi." />
    <LoadState loading={state.loading} error={state.error} unavailable={state.unavailable}>
      <section className="easy-hero"><div><p className="kicker">Today's sales</p><strong>{displayValue(state.data?.today_revenue ?? state.data?.revenue_today)} <small>MMK</small></strong><p>{displayValue(state.data?.active_sessions ?? 0)} guests online</p></div><div><p className="kicker">Magic Hub</p><h2>{String(state.data?.router_name ?? "Your network")}</h2><span className="status-good"><CircleCheck size={16} /> Ready when connected</span></div></section>
      <div className="action-grid"><EasyAction to="/app/easy/vouchers" icon={Ticket} title="Sell vouchers" body="Create access codes" /><EasyAction to="/app/easy/print-slips" icon={Printer} title="Print slips" body="Ready to hand out" /><EasyAction to="/app/easy/guests" icon={UsersRound} title="Guests" body="See who is online" /><EasyAction to="/app/easy/router" icon={Router} title="Router" body="Check connection health" /></div>
    </LoadState></>;
}

function EasyAction({ to, icon: Icon, title, body }: { to: string; icon: typeof Ticket; title: string; body: string }) {
  return <Link to={to} className="action-card tall"><span><Icon /></span><div><strong>{title}</strong><small>{body}</small></div><ArrowRight /></Link>;
}

export function EasyScreenPage({ screen }: { screen: string }) {
  const map: Record<string, { title: string; body: string; to: string }> = {
    "print-slips": { title: "Print voucher slips", body: "Choose a voucher batch and print from the full voucher workspace.", to: "/app/vouchers" },
    guests: { title: "Guests online", body: "See the current sessions reported by connected routers.", to: "/app/live" },
    router: { title: "Router health", body: "Check Magic Hub connection and router health.", to: "/app/routers" },
    "protect-hotspot": { title: "Protect your hotspot", body: "Review router changes before anything is applied.", to: "/app/routers" },
  };
  const item = map[screen];
  if (!item) return <><PageIntro title="Not available yet" description="This easy-mode shortcut is not connected yet." /></>;
  return <><PageIntro kicker="Easy mode" title={item.title} description={item.body} /><Link className="primary" to={item.to}>Continue <ArrowRight size={17} /></Link></>;
}
