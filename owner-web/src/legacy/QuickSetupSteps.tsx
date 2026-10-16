import { useState } from "react";
import { post } from "../lib/api";

const STEPS = [
  "Connect the router to Magic Hub.",
  "Create MikroMagic's limited mm-monitor identity.",
  "Create the separate mm-safechange identity.",
  "Remove the old Lovable API user and its old WireGuard peer (Safe Change: preview, backup, apply, readback).",
];

/** Required onboarding steps (screen decision 11). Cleanup runs only as a Safe Change proposal the owner confirms. */
export function QuickSetupSteps() {
  const [routerId, setRouterId] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function proposeCleanup() {
    setBusy(true); setMessage("");
    try {
      const r = await post<Record<string, unknown>>("/v1/owner/scripts/run", { router_id: routerId.trim(), script_id: "remove-legacy-lovable-api-user-and-wg-peer" });
      setMessage(r.status === "coming_soon" ? "Coming soon — no command was run on the router." : "Safe Change proposal created. Review and confirm it before anything changes.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "The proposal was not created."); }
    finally { setBusy(false); }
  }
  return <section className="mx-auto mb-4 max-w-5xl rounded-xl border border-border/60 p-4">
    <h2 className="text-base font-semibold">Guided setup steps</h2>
    <ol className="mt-2 list-decimal pl-5 text-sm">{STEPS.map((s) => <li key={s}>{s}</li>)}</ol>
    <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
      <input className="rounded-md border border-border bg-transparent px-2 py-1" placeholder="Router ID" value={routerId} onChange={(e) => setRouterId(e.target.value)} aria-label="Router ID for old access cleanup" />
      <button className="rounded-md border border-border px-3 py-1" disabled={busy || !routerId.trim()} onClick={() => void proposeCleanup()}>Prepare cleanup proposal</button>
    </div>
    {message && <p className="mt-2 text-sm" role="status">{message}</p>}
  </section>;
}
