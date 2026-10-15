import { FileCode2, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { post } from "../lib/api";
import { PageIntro } from "../components/AsyncPanel";

export function ScriptsPage({ quickSetup = false }: { quickSetup?: boolean }) {
  const [routerId, setRouterId] = useState("");
  const [scriptId, setScriptId] = useState(quickSetup ? "quick-setup" : "");
  const [reviewed, setReviewed] = useState(false);
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    const result = await post<Record<string, unknown>>("/v1/owner/scripts/run", { router_id: routerId.trim(), script_id: scriptId.trim() });
    setMessage(result.status === "coming_soon" ? "Coming soon — no direct command was run." : "Safe Change proposal created.");
  }
  const steps = ["Connect the router to Magic Hub.", "Create MikroMagic's limited mm-monitor identity.", "Create the separate mm-safechange identity.", "Review removal of the old Lovable API user and old WireGuard peer."];
  return <>
    <PageIntro title={quickSetup ? "Quick setup" : "Router scripts"} description={quickSetup ? "Prepare one guided setup proposal for one router. Nothing runs directly." : "Choose one router and prepare a Safe Change proposal. Scripts never run directly from this screen."} />
    {quickSetup && <section className="panel"><ol className="guided-steps">{steps.map((step) => <li key={step}>{step}</li>)}</ol></section>}
    <section className="panel form-panel"><p className="kicker"><FileCode2 size={16} /> One router first</p><form onSubmit={submit}><label>Router ID<input value={routerId} onChange={(event) => setRouterId(event.target.value)} required /></label><label>Script or setup plan<input value={scriptId} onChange={(event) => setScriptId(event.target.value)} required readOnly={quickSetup} /></label><div className="change-preview"><h3>Safe Change preview</h3><p>MikroMagic will require current preflight evidence, a verified backup, exact readback and rollback protection before any supported apply.</p><label className="check-row"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} /> I reviewed this proposal target. Create it pending owner confirmation.</label></div><button className="primary" disabled={!reviewed}><ShieldCheck size={16} /> Create Safe Change proposal</button></form>{message && <p className="notice">{message}</p>}</section>
  </>;
}
