import { ShieldAlert, TerminalSquare } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ApiError, post } from "../lib/api";
import { PageIntro } from "../components/AsyncPanel";

export function TerminalPage() {
  const [routerId, setRouterId] = useState("");
  const [command, setCommand] = useState("/system resource print");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const result = await post<Record<string, unknown>>("/v1/owner/terminal", { router_id: routerId.trim(), command: command.trim() });
      setMessage(result.status === "coming_soon" ? "Coming soon — the request was audited, but no router command was executed." : "Request recorded.");
    } catch (cause) { setMessage(cause instanceof ApiError ? cause.message : "The request could not be recorded."); }
    finally { setBusy(false); }
  }
  return <>
    <PageIntro title="Terminal" description="Owner-only diagnostic requests. Every request is audited, and dangerous router or Magic Hub commands are blocked." />
    <section className="panel form-panel"><p className="kicker"><TerminalSquare size={16} /> Audited diagnostics</p><form onSubmit={submit}><label>Router ID<input value={routerId} onChange={(event) => setRouterId(event.target.value)} required /></label><label>Read command<textarea value={command} onChange={(event) => setCommand(event.target.value)} required /></label><div className="read-only-note"><ShieldAlert size={16} /> Reboot, shutdown, reset, private-key, Hub-key, UDP 51820 and listen-port commands are always blocked.</div><button className="primary" disabled={busy}>{busy ? "Checking…" : "Request command"}</button></form>{message && <p className="notice">{message}</p>}</section>
  </>;
}
