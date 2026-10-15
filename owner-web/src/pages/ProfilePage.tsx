import { LogOut, ShieldCheck, Smartphone } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { LoadState, PageIntro, displayValue, useEndpoint } from "../components/AsyncPanel";
import { useSession } from "../lib/session";

type SessionRecord = { id: string; current?: boolean; login_at?: number; last_active?: number; device?: string; browser?: string; source?: string };

export function ProfilePage() {
  const session = useSession();
  const navigate = useNavigate();
  const sessions = useEndpoint<SessionRecord[]>("/v1/account/sessions");
  const mfa = useEndpoint<Record<string, unknown>>(session.me?.staff_profile ? null : "/v1/account/mfa");
  return <><PageIntro kicker="Your account" title="Profile" description="Review your account security and signed-in devices." action={<button className="secondary" onClick={async () => { await session.signOut(); await navigate({ to: "/auth", replace: true }); }}><LogOut size={16} /> Sign out</button>} />
    <section className="profile-grid"><article className="panel profile-card"><span className="profile-avatar">{session.me?.username.slice(0, 1).toUpperCase()}</span><div><h2>{session.me?.username}</h2><p>{session.me?.staff_profile ? "Owner staff" : "Owner/Admin"}</p><span className="status-good"><ShieldCheck size={15} /> Account active</span></div></article><article className="panel"><p className="kicker">Two-step security</p><h2>{mfa.data?.enabled ? "Enabled" : "Not enabled"}</h2><p>Two-step security adds a code after your password.</p></article></section>
    <section className="section-block"><div className="section-heading"><div><p className="kicker">Security</p><h2>Signed-in devices</h2></div></div><LoadState loading={sessions.loading} error={sessions.error} empty={!sessions.data?.length}><div className="data-grid">{sessions.data?.map((item) => <article className="data-card" key={item.id}><span className="card-icon"><Smartphone /></span><div><h3>{item.device || "Device"} · {item.browser || "Browser"}</h3><p>{item.current ? "This device" : displayValue(item.source)}</p><small>Last active {displayValue(item.last_active)}</small></div></article>)}</div></LoadState></section>
  </>;
}
