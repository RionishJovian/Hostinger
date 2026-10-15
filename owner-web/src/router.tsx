import { Navigate, Outlet, createRootRoute, createRoute, createRouter, useParams } from "@tanstack/react-router";
import { Activity, Archive, BadgeDollarSign, Building2, ClipboardList, Radio, ShieldAlert, Ticket, UsersRound, WalletCards } from "lucide-react";
import { AppGuard } from "./components/Shell";
import { AuthPage } from "./pages/AuthPage";
import { DataPage } from "./pages/DataPage";
import { EasyPage, EasyScreenPage } from "./pages/EasyPage";
import { EasyVouchersPage } from "./pages/EasyVouchersPage";
import { HomePage } from "./pages/HomePage";
import { I18nPage } from "./pages/I18nPage";
import { ManualPage } from "./pages/ManualPage";
import { PortalPage } from "./pages/PortalPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RoutersPage } from "./pages/RoutersPage";

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
  appRoute.addChildren([homeRoute, easyRoute, easyVouchersRoute, easyScreenRoute, routersRoute, vouchersRoute, layoutsRoute, portalRoute, ordersRoute, revenueRoute, resellerRoute, sitesRoute, incidentsRoute, liveRoute, auditRoute, backupsRoute, profileRoute, usersRoute, usageRoute, manualRoute, i18nRoute]),
]);

export const router = createRouter({ routeTree, basepath: "/owner" });

declare module "@tanstack/react-router" {
  interface Register { router: typeof router }
}
