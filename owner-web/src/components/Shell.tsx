import { Link, Outlet, useLocation, useNavigate } from "@tanstack/react-router";
import { Activity, Archive, BadgeDollarSign, BookOpen, Building2, ChevronDown, CircleUserRound, ClipboardList, Globe2, Languages, LayoutDashboard, Menu, Radio, Router, Settings2, ShieldAlert, Ticket, UsersRound, WalletCards, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSession } from "../lib/session";
import { ThemeToggle } from "./ThemeProvider";

const navigation = [
  { to: "/app", label: "Home", icon: LayoutDashboard },
  { to: "/app/easy", label: "Easy mode", icon: Activity },
  { to: "/app/routers", label: "Routers", icon: Router },
  { to: "/app/vouchers", label: "Vouchers", icon: Ticket },
  { to: "/app/voucher-layouts", label: "Print layouts", icon: ClipboardList },
  { to: "/app/portal", label: "Guest Wi-Fi page", icon: Globe2 },
  { to: "/app/orders", label: "Payments", icon: WalletCards },
  { to: "/app/revenue", label: "Revenue", icon: BadgeDollarSign },
  { to: "/app/reseller-operation", label: "Resellers", icon: UsersRound },
  { to: "/app/sites", label: "Sites", icon: Building2 },
  { to: "/app/incidents", label: "Incidents", icon: ShieldAlert },
  { to: "/app/live", label: "Live guests", icon: Radio },
  { to: "/app/audit", label: "Audit", icon: ClipboardList },
  { to: "/app/backups", label: "Backups", icon: Archive },
  { to: "/app/users", label: "Staff", icon: UsersRound },
  { to: "/app/usage", label: "Usage", icon: Activity },
  { to: "/app/manual", label: "Manual", icon: BookOpen },
  { to: "/app/i18n", label: "Language", icon: Languages },
];

export function AppGuard() {
  const session = useSession();
  const navigate = useNavigate();
  useEffect(() => {
    if (!session.loading && !session.me) void navigate({ to: "/auth", replace: true });
  }, [navigate, session.loading, session.me]);
  if (session.loading) return <main className="center-page"><div className="brand-orb" /><p>Opening your workspace…</p></main>;
  if (!session.me) return null;
  if (session.me.role !== "sme") return <main className="center-page"><section className="auth-card"><h1>Owner workspace only</h1><p>Use a MikroMagic Owner/Admin or owner staff account.</p><button onClick={() => void session.signOut()}>Sign out</button></section></main>;
  return <AppShell />;
}

function AppShell() {
  const session = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const current = navigation.find((item) => item.to === location.pathname) ?? navigation.find((item) => location.pathname.startsWith(item.to + "/"));
  return <div className="app-shell">
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand"><span className="brand-gem">M</span><div><strong>MikroMagic</strong><small>Owner workspace</small></div><button className="mobile-close" onClick={() => setOpen(false)} aria-label="Close menu"><X /></button></div>
      <nav>{navigation.map((item) => <Link key={item.to} to={item.to} activeOptions={{ exact: item.to === "/app" }} onClick={() => setOpen(false)}><item.icon size={18} /><span>{item.label}</span></Link>)}</nav>
      <div className="sidebar-footer"><Link to="/app/profile"><CircleUserRound size={20} /><span><strong>{session.me?.username}</strong><small>{session.me?.staff_profile ? "Owner staff" : "Owner/Admin"}</small></span></Link></div>
    </aside>
    {open && <button className="scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}
    <div className="workspace">
      <header className="topbar"><button className="menu-button" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></button><div><span className="eyebrow">MikroMagic</span><strong>{current?.label ?? "Owner workspace"}</strong></div><div className="topbar-actions"><ThemeToggle /><button className="account-button" onClick={() => void navigate({ to: "/app/profile" })}><CircleUserRound size={18} /><span>{session.me?.username}</span><ChevronDown size={14} /></button></div></header>
      {session.me?.subscription_restricted && <div className="restriction-banner">Your subscription needs attention. Business records remain protected while workspace access is limited.</div>}
      <main className="page"><Outlet /></main>
      <nav className="bottom-nav">{navigation.slice(0, 5).map((item) => <Link key={item.to} to={item.to} activeOptions={{ exact: item.to === "/app" }}><item.icon /><span>{item.label}</span></Link>)}<button onClick={() => setOpen(true)}><Settings2 /><span>More</span></button></nav>
    </div>
  </div>;
}
