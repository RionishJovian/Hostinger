// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type TestStep = Record<string, unknown>;
export type RouterSummary = { id: string; site_id: string | null; name: string; model: string | null; routeros: string | null; connected: boolean; last_seen: number | null; router_path: string };
export const listRouters = engineFn<RouterSummary[]>("listRouters", { method: "GET", path: "/v1/owner/fleet" });
export const reactivateRouterWithKey = engineFn("reactivateRouterWithKey");
export const saveRouter = engineFn("saveRouter");
export const listRouterAudit = engineFn("listRouterAudit");
export const explainRouterAuditError = engineFn("explainRouterAuditError");
export const deleteRouter = engineFn("deleteRouter");
export const listRouterTests = engineFn("listRouterTests");
export const rebootRouter = engineFn("rebootRouter");
export const testConnection = engineFn("testConnection");
export const testRouter = engineFn("testRouter");
export const routerTelemetry = engineFn("routerTelemetry");
export const routerServiceCounts = engineFn("routerServiceCounts");
export const getFleetTrafficSnapshot = engineFn("getFleetTrafficSnapshot");
export const routersStatus = engineFn("routersStatus");
