import { Check, Clipboard, RefreshCw, Router, ShieldCheck, Wifi } from "lucide-react";
import { useEffect, useState } from "react";
import { LoadState, PageIntro, displayValue, useEndpoint } from "../components/AsyncPanel";
import { get, post } from "../lib/api";

type RouterRecord = {
  id: string;
  name: string;
  model?: string | null;
  reported_routeros?: string | null;
  connection_state?: string;
  connection_verified?: boolean;
  lifecycle_state?: string | null;
  last_handshake?: number | null;
};
type ConnectResult = { token_id: string; router_id: string; expires: number; script: string; progress: Record<string, unknown> };
type Preview = { id: string; revision: number; status: string; diff: Record<string, unknown>; requires_owner_confirmation: boolean };

export function RoutersPage() {
  const state = useEndpoint<RouterRecord[]>("/v1/routers");
  const [selected, setSelected] = useState<RouterRecord | null>(null);
  const [connect, setConnect] = useState<ConnectResult | null>(null);
  const [progress, setProgress] = useState<Record<string, unknown> | null>(null);
  const [scriptCopied, setScriptCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [keepalive, setKeepalive] = useState(25);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!connect || !selected) return;
    let stopped = false;
    const check = async () => {
      try {
        const next = await fetchStatus(selected.id, connect.token_id);
        if (!stopped) setProgress(next);
      } catch {
        if (!stopped) setNotice("Connection progress could not be refreshed.");
      }
    };
    void check();
    const timer = window.setInterval(() => void check(), 4000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [connect, selected]);

  async function startConnect(router: RouterRecord) {
    setBusy(true); setNotice(""); setSelected(router); setPreview(null); setConfirmed(false);
    try {
      const result = await post<ConnectResult>(`/v1/routers/${router.id}/magic-hub-connect`, {});
      setConnect(result); setProgress(result.progress);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not start Magic Hub connect."); }
    finally { setBusy(false); }
  }

  async function createPreview() {
    if (!selected) return;
    setBusy(true); setNotice(""); setConfirmed(false);
    try { setPreview(await post<Preview>(`/v1/routers/${selected.id}/changes/preview`, { operation: "wireguard_peer_keepalive", persistent_keepalive_seconds: keepalive })); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Could not prepare the change preview."); }
    finally { setBusy(false); }
  }

  async function applyPreview() {
    if (!preview || !confirmed) return;
    setBusy(true); setNotice("");
    try {
      const result = await post<Record<string, unknown>>(`/v1/router-changes/${preview.id}/apply`, { expected_revision: preview.revision, confirm_high_risk: true });
      setPreview(null); setConfirmed(false); setNotice(`Safe Change status: ${displayValue(result.status)}`);
      await state.refresh();
    } catch (error) { setNotice(error instanceof Error ? error.message : "The protected change was not applied."); }
    finally { setBusy(false); }
  }

  const routers = state.data ?? [];
  return <>
    <PageIntro kicker="Magic Hub" title="Routers" description="Connect each shop router once, then check its verified connection and review protected changes." action={<button className="secondary" onClick={() => void state.refresh()}><RefreshCw size={16} /> Refresh</button>} />
    {notice && <div className="notice" role="status">{notice}</div>}
    <LoadState loading={state.loading} error={state.error} empty={!routers.length}>
      <section className="router-grid">{routers.map((router) => <article className={`router-card ${selected?.id === router.id ? "selected" : ""}`} key={router.id}>
        <div className="router-card-head"><span className="card-icon"><Router /></span><span className={router.connection_verified ? "status-good" : "status-warn"}>{router.connection_verified ? "● Connected" : "● Not connected"}</span></div>
        <h2>{router.name}</h2><p>{router.model || "Model detected after connection"} · {router.reported_routeros || "RouterOS detected after connection"}</p>
        <dl><div><dt>Connection</dt><dd>{displayValue(router.connection_state)}</dd></div><div><dt>Management</dt><dd>{displayValue(router.lifecycle_state)}</dd></div><div><dt>Last handshake</dt><dd>{displayValue(router.last_handshake)}</dd></div></dl>
        <div className="button-row"><button className="primary" disabled={busy} onClick={() => void startConnect(router)}><Wifi size={16} /> Connect with Magic Hub</button><button className="secondary" onClick={() => { setSelected(router); setConnect(null); setPreview(null); setConfirmed(false); }}>Safe Change</button></div>
      </article>)}</section>
    </LoadState>
    {connect && selected && <section className="panel connect-panel"><p className="kicker">One-paste connection</p><h2>Connect {selected.name}</h2><ol className="steps"><li><span>1</span>Open Terminal in WinBox.</li><li><span>2</span>Copy and paste this MikroMagic script once.</li><li><span>3</span>Keep this window open while connection checks finish.</li></ol><div className="script-box"><code>{connect.script}</code><button onClick={async () => { await navigator.clipboard.writeText(connect.script); setScriptCopied(true); }}><Clipboard size={16} /> {scriptCopied ? "Copied" : "Copy script"}</button></div><div className="progress-strip"><Progress label="Router reported" progress={progress} keys={["router_reported", "reported"]} /><Progress label="Hub peer added" progress={progress} keys={["hub_peer_added", "peer_added"]} /><Progress label="Handshake" progress={progress} keys={["handshake", "handshake_verified"]} /><Progress label="Management ready" progress={progress} keys={["management_ready", "management_applied"]} /><Progress label="Connected" progress={progress} keys={["connected"]} /></div></section>}
    {selected && !connect && <section className="panel"><p className="kicker"><ShieldCheck size={15} /> Safe Change</p><h2>Review before changing {selected.name}</h2><p>MikroMagic checks the live router, creates a preview, requires a safety backup, verifies the result and keeps rollback protection.</p><label className="field compact">Tunnel keepalive seconds<input type="number" min="1" max="3600" value={keepalive} onChange={(event) => setKeepalive(Number(event.target.value))} /></label><button className="secondary" disabled={busy || keepalive < 1 || keepalive > 3600} onClick={() => void createPreview()}>Prepare preview</button>
      {preview && <div className="change-preview"><h3>High-risk change preview</h3><dl>{Object.entries(preview.diff ?? {}).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{displayValue(value)}</dd></div>)}</dl><label className="check-row"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I reviewed this exact preview and confirm this high-risk change.</label><button className="danger-button" disabled={busy || !confirmed || !preview.requires_owner_confirmation} onClick={() => void applyPreview()}>Apply with Safe Change</button></div>}
    </section>}
  </>;
}

async function fetchStatus(routerId: string, tokenId: string) {
  return get<Record<string, unknown>>(`/v1/routers/${routerId}/magic-hub-connect/${tokenId}`);
}

function Progress({ label, progress, keys }: { label: string; progress: Record<string, unknown> | null; keys: string[] }) {
  const value = keys.some((key) => progress?.[key] === true) || keys.includes(String(progress?.status));
  return <span className={value ? "done" : ""}>{value ? <Check /> : <i />}{label}</span>;
}
