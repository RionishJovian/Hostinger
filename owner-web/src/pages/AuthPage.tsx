import { useNavigate } from "@tanstack/react-router";
import { LockKeyhole, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useSession } from "../lib/session";

function returnTo(): string {
  const stored = sessionStorage.getItem("mm.owner.return-to") || "";
  sessionStorage.removeItem("mm.owner.return-to");
  return /^\/app(?:\/|$)/.test(stored) ? stored : "/app";
}

export function AuthPage() {
  const session = useSession();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (session.me) void navigate({ to: returnTo() as never, replace: true }); }, [navigate, session.me]);
  return <main className="auth-page">
    <div className="auth-aurora" />
    <section className="auth-story"><div className="brand large"><span className="brand-gem">M</span><div><strong>MikroMagic</strong><small>Run your Wi-Fi business with confidence</small></div></div><div><p className="kicker"><Sparkles size={15} /> Made for busy shops</p><h1>Everything your hotspot needs, in one calm workspace.</h1><p>Connect your router, create vouchers, follow guest activity and keep your shop moving.</p></div></section>
    <section className="auth-card"><div className="lock-badge"><LockKeyhole /></div><p className="kicker">Owner workspace</p><h2>Welcome back</h2><p>Sign in with your MikroMagic account.</p><form onSubmit={async (event) => { event.preventDefault(); setBusy(true); setError(""); try { await session.signIn(username, password, mfaCode); } catch (cause) { setError(cause instanceof Error ? cause.message : "Sign-in failed"); } finally { setBusy(false); } }}>
      <label>Username<input autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} /></label>
      <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <label>Security code <span className="optional">if enabled</span><input inputMode="numeric" autoComplete="one-time-code" value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} /></label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary wide" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form><small className="privacy-note">Your sign-in is checked securely by MikroMagic. We never ask for your router password.</small></section>
  </main>;
}
