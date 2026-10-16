// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type TestStep = any;
export const listRouters = engineFn("listRouters");
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
