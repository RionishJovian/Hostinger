import { Navigate, Outlet, createRootRoute, createRoute, createRouter, useParams } from "@tanstack/react-router";
import { AppGuard } from "./components/Shell";
import { AuthPage } from "./pages/AuthPage";
import { EasyPage, EasyScreenPage } from "./pages/EasyPage";
import { EasyVouchersPage } from "./pages/EasyVouchersPage";
import { HomePage } from "./pages/HomePage";
import { I18nPage } from "./pages/I18nPage";
import { ManualPage } from "./pages/ManualPage";
import { PortalPage } from "./pages/PortalPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RoutersPage } from "./pages/RoutersPage";
import { Route as L_vouchers } from "./legacy/routes/_authenticated/app.vouchers";
import { Route as L_voucher_layouts } from "./legacy/routes/_authenticated/app.voucher-layouts";
import { Route as L_orders } from "./legacy/routes/_authenticated/app.orders";
import { Route as L_revenue } from "./legacy/routes/_authenticated/app.revenue";
import { Route as L_reseller_operation } from "./legacy/routes/_authenticated/app.reseller-operation";
import { Route as L_sites } from "./legacy/routes/_authenticated/app.sites";
import { Route as L_incidents } from "./legacy/routes/_authenticated/app.incidents";
import { Route as L_live } from "./legacy/routes/_authenticated/app.live";
import { Route as L_audit } from "./legacy/routes/_authenticated/app.audit";
import { Route as L_backups } from "./legacy/routes/_authenticated/app.backups";
import { Route as L_users } from "./legacy/routes/_authenticated/app.users";
import { Route as L_usage } from "./legacy/routes/_authenticated/app.usage";
import { Route as L_terminal } from "./legacy/routes/_authenticated/app.terminal";
import { Route as L_scripts } from "./legacy/routes/_authenticated/app.scripts";
import { Route as L_fleet } from "./legacy/routes/_authenticated/app.fleet";
import { MagicDudePage } from "./pages/MagicDudePage";
import { Route as L_agent } from "./legacy/routes/_authenticated/app.agent";
import { Route as L_connectors } from "./legacy/routes/_authenticated/app.connectors";
import { Route as L_devices } from "./legacy/routes/_authenticated/app.devices";
import { Route as L_topology } from "./legacy/routes/_authenticated/app.topology";
import { Route as L_syslog } from "./legacy/routes/_authenticated/app.syslog";
import { Route as L_quick_setup } from "./legacy/routes/_authenticated/app.quick-setup";
import { Route as L_deployments } from "./legacy/routes/_authenticated/app.deployments";
import { Route as L_services } from "./legacy/routes/_authenticated/app.services";
import { Route as L_readiness } from "./legacy/routes/_authenticated/app.readiness";
import { Route as L_test_lab } from "./legacy/routes/_authenticated/app.test-lab";
import { Route as L_test_lab_index } from "./legacy/routes/_authenticated/app.test-lab.index";
import { Route as L_test_lab_mcp } from "./legacy/routes/_authenticated/app.test-lab.mcp";
import { Route as L_test_lab_real } from "./legacy/routes/_authenticated/app.test-lab.real";
import { QuickSetupSteps } from "./legacy/QuickSetupSteps";
import { LegacyFrame, type Audience } from "./legacy/LegacyFrame";

const rootRoute = createRootRoute({ component: Outlet });
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: () => <Navigate to="/app" replace /> });
const authRoute = createRoute({ getParentRoute: () => rootRoute, path: "auth", component: AuthPage });
const appRoute = createRoute({ getParentRoute: () => rootRoute, path: "app", component: AppGuard });
const homeRoute = createRoute({ getParentRoute: () => appRoute, path: "/", component: HomePage });
const easyRoute = createRoute({ getParentRoute: () => appRoute, path: "easy", component: EasyPage });
const easyVouchersRoute = createRoute({ getParentRoute: () => appRoute, path: "easy/vouchers", component: EasyVouchersPage });
const easyScreenRoute = createRoute({ getParentRoute: () => appRoute, path: "easy/$screen", component: EasyDynamic });
const routersRoute = createRoute({ getParentRoute: () => appRoute, path: "routers", component: RoutersPage });
const vouchersRoute = dataRoute("vouchers", legacyScreen(L_vouchers, "sme"));
const layoutsRoute = dataRoute("voucher-layouts", legacyScreen(L_voucher_layouts, "sme"));
const portalRoute = createRoute({ getParentRoute: () => appRoute, path: "portal", component: PortalPage });
const ordersRoute = dataRoute("orders", legacyScreen(L_orders, "sme"));
const revenueRoute = dataRoute("revenue", legacyScreen(L_revenue, "sme"));
const resellerRoute = dataRoute("reseller-operation", legacyScreen(L_reseller_operation, "sme"));
const sitesRoute = dataRoute("sites", legacyScreen(L_sites, "sme"));
const incidentsRoute = dataRoute("incidents", legacyScreen(L_incidents, "sme"));
const liveRoute = dataRoute("live", legacyScreen(L_live, "sme"));
const auditRoute = dataRoute("audit", legacyScreen(L_audit, "sme"));
const backupsRoute = dataRoute("backups", legacyScreen(L_backups, "sme"));
const profileRoute = createRoute({ getParentRoute: () => appRoute, path: "profile", component: ProfilePage });
const usersRoute = dataRoute("users", legacyScreen(L_users, "owner"));
const usageRoute = dataRoute("usage", legacyScreen(L_usage, "sme"));
const manualRoute = createRoute({ getParentRoute: () => appRoute, path: "manual", component: ManualPage });
const i18nRoute = createRoute({ getParentRoute: () => appRoute, path: "i18n", component: I18nPage });
const terminalRoute = dataRoute("terminal", legacyScreen(L_terminal, "owner"));
const scriptsRoute = dataRoute("scripts", legacyScreen(L_scripts, "sme"));
const fleetRoute = dataRoute("fleet", legacyScreen(L_fleet, "sme"));
const magicDudeRoute = dataRoute("magic-dude", MagicDudePage); // Lovable Magic Dude was a floating chat tied to the old backend; owner advisor page kept
const agentRoute = dataRoute("agent", legacyScreen(L_agent, "agent"));
const connectorsRoute = dataRoute("connectors", legacyScreen(L_connectors, "owner"));
const devicesRoute = dataRoute("devices", legacyScreen(L_devices, "sme"));
const topologyRoute = dataRoute("topology", legacyScreen(L_topology, "owner"));
const syslogRoute = dataRoute("syslog", legacyScreen(L_syslog, "sme"));
const quickSetupRoute = dataRoute("quick-setup", () => <LegacyFrame audience="sme"><QuickSetupSteps /><QuickSetupScreen /></LegacyFrame>);
const QuickSetupScreen = L_quick_setup.options.component;
const deploymentsRoute = dataRoute("deployments", legacyScreen(L_deployments, "sme"));
const servicesRoute = dataRoute("services", legacyScreen(L_services, "sme"));
const tenantsRoute = dataRoute("tenants", legacyScreen(L_users, "platform"));
const readinessRoute = dataRoute("readiness", legacyScreen(L_readiness, "sme"));
const testLabRoute = dataRoute("test-lab", legacyScreen(L_test_lab, "platform"));
const testLabIndexRoute = dataRoute("test-lab/index", legacyScreen(L_test_lab_index, "platform"));
const testLabMcpRoute = dataRoute("test-lab/mcp", legacyScreen(L_test_lab_mcp, "platform"));
const testLabRealRoute = dataRoute("test-lab/real", legacyScreen(L_test_lab_real, "platform"));
const testLabSandboxRoute = dataRoute("test-lab/sandbox", legacyScreen(L_test_lab_real, "platform"));

function legacyScreen(route: { options: { component: React.ComponentType } }, audience: Audience) {
  const Screen = route.options.component;
  return () => <LegacyFrame audience={audience}><Screen /></LegacyFrame>;
}

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
  appRoute.addChildren([homeRoute, easyRoute, easyVouchersRoute, easyScreenRoute, routersRoute, vouchersRoute, layoutsRoute, portalRoute, ordersRoute, revenueRoute, resellerRoute, sitesRoute, incidentsRoute, liveRoute, auditRoute, backupsRoute, profileRoute, usersRoute, usageRoute, manualRoute, i18nRoute, terminalRoute, scriptsRoute, fleetRoute, magicDudeRoute, agentRoute, connectorsRoute, devicesRoute, topologyRoute, syslogRoute, quickSetupRoute, deploymentsRoute, servicesRoute, tenantsRoute, readinessRoute, testLabRoute, testLabIndexRoute, testLabMcpRoute, testLabRealRoute, testLabSandboxRoute]),
]);

export const router = createRouter({ routeTree, basepath: "/owner" });

declare module "@tanstack/react-router" {
  interface Register { router: typeof router }
}
