// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const BASIC_DEFAULT_SUPPORT_ACTIONS = ["sync_plans"] as const;
export const inspectDeveloperSupportRouter = engineFn("inspectDeveloperSupportRouter");
export const rebootDeveloperSupportRouter = engineFn("rebootDeveloperSupportRouter");
export const syncPlansForSupportRouter = engineFn("syncPlansForSupportRouter");
export const getSupportGrantStatus = engineFn("getSupportGrantStatus");
export const getLatestSupportSyncAudit = engineFn("getLatestSupportSyncAudit");
