import { Eye, Save, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { LoadState, PageIntro, useEndpoint } from "../components/AsyncPanel";
import { post } from "../lib/api";

type PortalSettings = { business_name: string; welcome: string; language: string; terms: string; contact: string; direct_purchase: boolean; voucher_login: boolean; payment_destination: string | null; payment_instructions: string | null; payment_methods: string[] };
type PortalState = { revision: number; draft: PortalSettings; published: PortalSettings | null; published_revision: number | null; router_deployment_status: string };

export function PortalPage() {
  const state = useEndpoint<PortalState>("/v1/portal");
  const [draft, setDraft] = useState<PortalSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => { if (state.data) setDraft(state.data.draft); }, [state.data]);
  const update = (field: keyof PortalSettings, value: string | boolean) => setDraft((current) => current ? { ...current, [field]: value } : current);
  async function act(kind: "draft" | "publish") {
    if (!state.data || !draft) return;
    setBusy(true); setNotice("");
    try {
      const next = kind === "draft" ? await post<PortalState>("/v1/portal/draft", { expected_revision: state.data.revision, settings: draft }) : await post<PortalState>("/v1/portal/publish", { expected_revision: state.data.revision });
      setDraft(next.draft); setNotice(kind === "draft" ? "Guest Wi-Fi page saved in MikroMagic." : "Guest Wi-Fi page published in MikroMagic."); await state.refresh();
    } catch (error) { setNotice(error instanceof Error ? error.message : "The page was not saved."); }
    finally { setBusy(false); }
  }
  return <><PageIntro kicker="Guest Wi-Fi" title="Guest Wi-Fi page" description="Keep the welcome page simple: one voucher-code box, your shop name and clear help for guests." />
    {notice && <div className="notice" role="status">{notice}</div>}
    <LoadState loading={state.loading} error={state.error} unavailable={state.unavailable}>
      {draft && <div className="portal-layout"><section className="panel form-panel"><h2>Page content</h2><label>Shop name<input value={draft.business_name} onChange={(event) => update("business_name", event.target.value)} /></label><label>Welcome message<textarea value={draft.welcome} onChange={(event) => update("welcome", event.target.value)} /></label><label>Language<select value={draft.language} onChange={(event) => update("language", event.target.value)}><option value="my">မြန်မာ</option><option value="en">English</option></select></label><label>Terms<textarea value={draft.terms} onChange={(event) => update("terms", event.target.value)} /></label><label>Guest help contact<input value={draft.contact} onChange={(event) => update("contact", event.target.value)} /></label><label className="check-row"><input type="checkbox" checked={draft.voucher_login} onChange={(event) => update("voucher_login", event.target.checked)} /> Show voucher-code login</label><div className="button-row"><button className="secondary" disabled={busy} onClick={() => void act("draft")}><Save size={16} /> Save page</button><button className="primary" disabled={busy} onClick={() => void act("publish")}><Send size={16} /> Publish</button></div></section><section className="panel preview-panel"><p className="kicker"><Eye size={15} /> Live preview</p><div className="phone"><div className="phone-screen"><span className="wifi-logo">M</span><h2>{draft.business_name || "Your shop"}</h2><p>{draft.welcome || "Welcome to our guest Wi-Fi"}</p><label>Voucher code<input readOnly placeholder="Enter voucher code" /></label><button>Connect</button><small>{draft.contact}</small></div></div><p className="muted">Publishing saves this page in MikroMagic. Router installation remains a separate reviewed Safe Change.</p></section></div>}
    </LoadState>
  </>;
}
