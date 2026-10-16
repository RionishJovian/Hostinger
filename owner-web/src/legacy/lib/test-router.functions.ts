// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const checkRouterConnection = engineFn("checkRouterConnection");
export const setRouterEnvironment = engineFn("setRouterEnvironment");
export const setInsecureTlsException = engineFn("setInsecureTlsException");
export const listRoutersByEnvironment = engineFn("listRoutersByEnvironment");
export const getTestLabAccess = engineFn("getTestLabAccess");
export { listRouterOpsAudit } from "./audit.functions";
