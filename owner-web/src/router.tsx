import { Navigate, Outlet, createRootRoute, createRoute, createRouter, useParams } from "@tanstack/react-router";
import { Activity, Archive, BadgeDollarSign, Building2, Cable, CheckCircle2, ClipboardList, CloudCog, Coins, FlaskConical, HardDrive, Map, Network, Radio, ServerCog, ShieldAlert, Ticket, UsersRound, WalletCards } from "lucide-react";
import { AppGuard } from "./components/Shell";
import { AuthPage } from "./pages/AuthPage";
import { DataPage } from "./pages/DataPage";
import { EasyPage, EasyScreenPage } from "./pages/EasyPage";
import { EasyVouchersPage } from "./pages/EasyVouchersPage";
import { HomePage } from "./pages/HomePage";
import { I18nPage } from "./pages/I18nPage";
import { ManualPage } from "./pages/ManualPage";
import { MagicDudePage } from "./pages/MagicDudePage";
import { OwnerReadPage } from "./pages/OwnerReadPage";
import { PortalPage } from "./pages/PortalPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RoutersPage } from "./pages/RoutersPage";
import { ScriptsPage } from "./pages/ScriptsPage";
import { SyslogPage } from "./pages/SyslogPage";
import { TerminalPage } from "./pages/TerminalPage";

const rootRoute = createRootRoute({ component: Outlet });
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: () => <Navigate to="/app" replace /> });
const authRoute = createRoute({ getParentRoute: () => rootRoute, path: "auth", component: AuthPage });
const appRoute = createRoute({ getParentRoute: () => rootRoute, path: "app", component: AppGuard });
const homeRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: HomePage });
const easyRoute = createRoute({ getParentRoute: () => appRoute, path: "easy", component: EasyPage });
const easyVouchersRoute = createRoute({ getParentRoute: () => appRoute, path: "easy/vouchers", component: EasyVouchersPage });
const easyScreenRoute = createRoute({ getParentRoute: () => appRoute, path: "easy/$screen", component: EasyDynamic });
const routersRoute = createRoute({ getParentRoute: () => appRoute, path: "routers", component: RoutersPage });
const vouchersRoute = dataRoute("vouchers", () => <DataPage title="Vouchers" description="Prepare, verify and hand out voucher batches without exposing guest codes in list views." endpoint="/v1/voucher-jobs" icon={Ticket} itemName="Voucher batch" fields={["ref", "name", "quantity", "status", "available", "created"]} />);
const layoutsRoute = dataRoute("voucher-layouts", () => <DataPage title="Voucher print layouts" description="Saved layouts keep counter slips consistent across print runs." endpoint="/v1/voucher-templates" icon={ClipboardList} itemName="Print layout" fields={["name", "created", "archived_at"]} />);
const portalRoute = createRoute({ getParentRoute: () => appRoute, path: "portal", component: PortalPage });
const ordersRoute = dataRoute("orders", () => <DataPage title="Payments" description="Review guest payment requests and their current fulfillment state." endpoint="/v1/orders" icon={WalletCards} itemName="Payment" fields={["amount", "currency", "method", "status", "fulfillment", "created"]} />);
const revenueRoute = dataRoute("revenue", () => <DataPage title="Revenue" description="Follow recorded sales, refunds and reconciliation totals for your business." endpoint="/v1/revenue" icon={BadgeDollarSign} itemName="Revenue summary" fields={["today", "last_7_days", "last_30_days", "currency", "unreconciled"]} />);
const resellerRoute = dataRoute("reseller-operation", () => <DataPage title="Reseller operation" description="See owner-managed resellers, voucher stock and settlement balances." endpoint="/v1/dealers" icon={UsersRound} itemName="Reseller" fields={["name", "location", "phone", "settlement", "balance", "available_stock", "archived_at"]} />);
const sitesRoute = dataRoute("sites", () => <DataPage title="Sites" description="Your shops and their saved business settings." endpoint="/v1/sites" icon={Building2} itemName="Site" fields={["name", "timezone", "printed_ssid", "maintenance_until", "created"]} />);
const incidentsRoute = dataRoute("incidents", () => <DataPage title="Incidents" description="Follow shop outages and confirmed resolutions without automatic router changes." endpoint="/v1/incidents" icon={ShieldAlert} itemName="Incident" fields={["scope", "status", "started", "ended", "detection_source", "suspected_root_cause", "expected_reason"]} />);
const liveRoute = dataRoute("live", () => <DataPage title="Live guests" description="Read-only hotspot sessions reported by connected routers." endpoint="/v1/hotspot-sessions/summary" icon={Radio} itemName="Session summary" readOnly fields={["active", "total", "stale", "last_collected_at", "unable_to_verify"]} />);
const auditRoute = dataRoute("audit", () => <DataPage title="Audit log" description="A durable history of account and business actions." endpoint="/v1/audit" icon={ClipboardList} itemName="Audit event" readOnly fields={["action", "target", "actor_id", "created"]} />);
const backupsRoute = dataRoute("backups", () => <DataPage title="Backups" description="Read-only backup health and restore-verification history." endpoint="/v1/backups" icon={Archive} itemName="Backup" readOnly fields={["kind", "version", "encrypted", "status", "restore_verified", "integrity_verified", "created", "retention_until"]} />);
const profileRoute = createRoute({ getParentRoute: () => appRoute, path: "profile", component: ProfilePage });
const usersRoute = dataRoute("users", () => <DataPage title="Staff" description="Owner-managed staff accounts and their current access profiles." endpoint="/v1/staff" icon={UsersRound} itemName="Staff member" fields={["username", "profile", "active", "created"]} />);
const usageRoute = dataRoute("usage", () => <DataPage title="Usage & subscription" description="See the plan, term and limits currently recorded for your business." endpoint="/v1/subscription" icon={Activity} itemName="Subscription" readOnly fields={["state", "expires_on", "days_left", "warning", "restricted", "period_start", "period_end", "enforcement"]} />);
const manualRoute = createRoute({ getParentRoute: () => appRoute, path: "manual", component: ManualPage });
const i18nRoute = createRoute({ getParentRoute: () => appRoute, path: "i18n", component: I18nPage });
const terminalRoute = dataRoute("terminal", TerminalPage);
const scriptsRoute = dataRoute("scripts", () => <ScriptsPage />);
const fleetRoute = dataRoute("fleet", () => <OwnerReadPage title="Fleet" description="A read-only view of your routers and their latest verified connection state." endpoint="/v1/owner/fleet" icon={Network} itemName="Router" fields={["site_id", "model", "routeros", "connected", "last_seen"]} />);
const magicDudeRoute = dataRoute("magic-dude", MagicDudePage);
const agentRoute = dataRoute("agent", () => <OwnerReadPage title="Magic Coins" description="Your read-only referral ledger and current coin balance." endpoint="/v1/agent/coins" icon={Coins} itemName="Ledger entry" fields={["amount", "currency", "state", "created", "reversed_at"]} />);
const connectorsRoute = dataRoute("connectors", () => <OwnerReadPage title="Connectors" description="On-site PC connectors for managing equipment without exposing router secrets." endpoint="/v1/owner/connectors" icon={Cable} itemName="Connector" />);
const devicesRoute = dataRoute("devices", () => <OwnerReadPage title="Devices & ports" description="Read-only switches, access points and available port observations." endpoint="/v1/owner/devices" icon={HardDrive} itemName="Device" fields={["kind", "vendor", "model", "location", "firmware", "last_seen", "ports"]} />);
const topologyRoute = dataRoute("topology", () => <OwnerReadPage title="Topology" description="A read-only map built from stored router and device data." endpoint="/v1/owner/topology" icon={Map} itemName="Site" />);
const syslogRoute = dataRoute("syslog", SyslogPage);
const quickSetupRoute = dataRoute("quick-setup", () => <ScriptsPage quickSetup />);
const deploymentsRoute = dataRoute("deployments", () => <OwnerReadPage title="Deployments" description="Safe Change history, backup checks and rollback outcomes." endpoint="/v1/owner/deployments" icon={CloudCog} itemName="Safe Change" fields={["router_id", "operation", "status", "risk", "backup_verified", "rollback_attempted", "created", "updated"]} />);
const servicesRoute = dataRoute("services", () => <OwnerReadPage title="Services & plan" description="Your current MikroMagic plan and recorded service limits." endpoint="/v1/owner/services/plan" icon={ServerCog} itemName="Plan" fields={["state", "period_start", "period_end", "plan"]} />);
const tenantsRoute = dataRoute("tenants", () => <OwnerReadPage title="Tenants" description="Platform administrator view of registered businesses. Removal requires a separate explicit confirmation." endpoint="/v1/owner/tenants" icon={Building2} itemName="Business" fields={["name"]} />);
const readinessRoute = dataRoute("readiness", () => <OwnerReadPage title="Readiness" description="Connected requires both a fresh Hub handshake and authenticated management read within 180 seconds." endpoint="/v1/owner/readiness" icon={CheckCircle2} itemName="Router" fields={["hub", "management", "connected", "fix_path"]} />);
const testLabRoute = dataRoute("test-lab", () => <OwnerReadPage title="Test lab" description="Platform-only test routers. Live customer routers are always refused." endpoint="/v1/owner/test-lab" icon={FlaskConical} itemName="Test router" />);

function dataRoute(path: string, component: () => React.ReactNode) {
  return createRoute({ getParentRoute: () => appRoute, path, component });
}

function EasyDynamic() {
  const params = useParams({ strict: false });
  return <EasyScreenPage screen={String(params.screen ?? "")} />;
}

const routeTree = rootRoute.addChildren([
  indexRoute,
  authRoute,
  appRoute.addChildren([homeRoute, easyRoute, easyVouchersRoute, easyScreenRoute, routersRoute, vouchersRoute, layoutsRoute, portalRoute, ordersRoute, revenueRoute, resellerRoute, sitesRoute, incidentsRoute, liveRoute, auditRoute, backupsRoute, profileRoute, usersRoute, usageRoute, manualRoute, i18nRoute, terminalRoute, scriptsRoute, fleetRoute, magicDudeRoute, agentRoute, connectorsRoute, devicesRoute, topologyRoute, syslogRoute, quickSetupRoute, deploymentsRoute, servicesRoute, tenantsRoute, readinessRoute, testLabRoute]),
]);

export const router = createRouter({ routeTree, basepath: "/owner" });

declare module "@tanstack/react-router" {
  interface Register { router: typeof router }
}
