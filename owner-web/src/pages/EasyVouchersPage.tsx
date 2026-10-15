import { Link } from "@tanstack/react-router";
import { ArrowRight, Ticket } from "lucide-react";
import { LoadState, PageIntro, displayValue, useEndpoint } from "../components/AsyncPanel";

type Job = { id: string; ref?: string; name?: string | null; quantity: number; status: string; available?: number; created?: number };
export function EasyVouchersPage() {
  const state = useEndpoint<Job[]>("/v1/voucher-jobs");
  return <><PageIntro kicker="Easy mode" title="Voucher codes" description="Create and print access codes for your guests." action={<Link className="secondary" to={"/app/vouchers" as never}>Open full workspace <ArrowRight size={16} /></Link>} /><LoadState loading={state.loading} error={state.error} empty={!state.data?.length}><section className="data-grid">{state.data?.slice(0, 6).map((job) => <article className="data-card" key={job.id}><span className="card-icon"><Ticket /></span><div><h2>{job.name || job.ref || "Voucher batch"}</h2><p>{job.quantity} codes · {displayValue(job.status)}</p><small>{displayValue(job.created)}</small></div></article>)}</section></LoadState></>;
}
