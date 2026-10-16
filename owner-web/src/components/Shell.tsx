import { Link, Outlet, useLocation, useNavigate } from "@tanstack/react-router";
import { Activity, Archive, BadgeDollarSign, BookOpen, Building2, Cable, CheckCircle2, ChevronDown, CircleUserRound, ClipboardList, CloudCog, Coins, FileCode2, FileSearch2, FlaskConical, HardDrive, Languages, LayoutDashboard, Map, Menu, Network, Radio, Router, ServerCog, Settings2, ShieldAlert, Sparkles, TerminalSquare, Ticket, UsersRound, WalletCards, WandSparkles, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useSession } from "../lib/session";
import { filterNavigation } from "../lib/navigation.mjs";
import { ThemeToggle } from "./ThemeProvider";

export type NavigationItem = { to: string; label: string; icon: LucideIcon; ownerOnly?: boolean; agentOnly?: boolean; platformOnly?: boolean };

export const navigation: NavigationItem[] = [
  { to: "/app", label: "Home", icon: LayoutDashboard },
  { to: "/app/easy", label: "Easy mode", icon: Activity },
  { to: "/app/routers", label: "Routers", icon: Router },
  { to: "/app/vouchers", label: "Vouchers", icon: Ticket },
  { to: "/app/voucher-layouts", label: "Print layouts", icon: ClipboardList },
  { to: "/app/portal", label: "Guest login", icon: Radio },
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
  { to: "/app/fleet", label: "Fleet", icon: Network },
  { to: "/app/devices", label: "Devices & ports", icon: HardDrive },
  { to: "/app/topology", label: "Topology", icon: Map },
  { to: "/app/syslog", label: "Syslog", icon: FileSearch2 },
  { to: "/app/deployments", label: "Deployments", icon: CloudCog },
  { to: "/app/readiness", label: "Readiness", icon: CheckCircle2 },
  { to: "/app/connectors", label: "Connectors", icon: Cable },
  { to: "/app/services", label: "Services", icon: ServerCog },
  { to: "/app/magic-dude", label: "Magic Dude", icon: Sparkles },
  { to: "/app/quick-setup", label: "Quick setup", icon: WandSparkles },
  { to: "/app/scripts", label: "Scripts", icon: FileCode2, ownerOnly: true },
  { to: "/app/terminal", label: "Terminal", icon: TerminalSquare, ownerOnly: true },
  { to: "/app/agent", label: "Magic Coins", icon: Coins, agentOnly: true },
  { to: "/app/tenants", label: "Tenants", icon: Building2, platformOnly: true },
  { to: "/app/test-lab", label: "Test lab", icon: FlaskConical, platformOnly: true },
];

export function AppGuard() {
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    if (!session.loading && !session.me) {
      if (location.pathname.startsWith("/app")) sessionStorage.setItem("mm.owner.return-to", location.pathname);
      void navigate({ to: "/auth", replace: true });
    }
    else if (!session.loading && session.me && location.pathname === "/app") {
      if (session.me.role === "agent") void navigate({ to: "/app/agent" as never, replace: true });
      if (session.me.role === "platform") void navigate({ to: "/app/tenants" as never, replace: true });
    }
  }, [location.pathname, navigate, session.loading, session.me]);
  if (session.loading) return <main className="center-page"><div className="brand-orb" /><p>Opening your workspace…</p></main>;
  if (!session.me) return null;
  if (!["sme", "platform", "agent"].includes(session.me.role)) return <main className="center-page"><section className="auth-card"><h1>Workspace unavailable</h1><p>This account does not have an owner, platform or Agent workspace.</p><button onClick={() => void session.signOut()}>Sign out</button></section></main>;
  return <AppShell />;
}

function AppShell() {
  const session = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const visibleNavigation = filterNavigation(navigation, session.me);
  const current = visibleNavigation.find((item) => item.to === location.pathname) ?? visibleNavigation.find((item) => location.pathname.startsWith(item.to + "/"));
  return <div className="app-shell">
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand"><span className="brand-gem">M</span><div><strong>MikroMagic</strong><small>Owner workspace</small></div><button className="mobile-close" onClick={() => setOpen(false)} aria-label="Close menu"><X /></button></div>
      <nav>{visibleNavigation.map((item) => <Link key={item.to} to={item.to} activeOptions={{ exact: item.to === "/app" }} onClick={() => setOpen(false)}><item.icon size={18} /><span>{item.label}</span></Link>)}</nav>
      <div className="sidebar-footer"><Link to="/app/profile"><CircleUserRound size={20} /><span><strong>{session.me?.username}</strong><small>{session.me?.role === "platform" ? "Platform administrator" : session.me?.role === "agent" ? "Agent" : session.me?.staff_profile ? "Owner staff" : "Owner/Admin"}</small></span></Link></div>
    </aside>
    {open && <button className="scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}
    <div className="workspace">
      <header className="topbar"><button className="menu-button" onClick={() => setOpen(true)} aria-label="Open menu"><Menu /></button><div><span className="eyebrow">MikroMagic</span><strong>{current?.label ?? "Owner workspace"}</strong></div><div className="topbar-actions"><ThemeToggle /><button className="account-button" onClick={() => void navigate({ to: "/app/profile" })}><CircleUserRound size={18} /><span>{session.me?.username}</span><ChevronDown size={14} /></button></div></header>
      {session.me?.subscription_restricted && <div className="restriction-banner">Your subscription needs attention. Business records remain protected while workspace access is limited.</div>}
      <main className="page"><Outlet /></main>
      <nav className="bottom-nav">{visibleNavigation.slice(0, 5).map((item) => <Link key={item.to} to={item.to} activeOptions={{ exact: item.to === "/app" }}><item.icon /><span>{item.label}</span></Link>)}<button onClick={() => setOpen(true)}><Settings2 /><span>More</span></button></nav>
    </div>
  </div>;
}
