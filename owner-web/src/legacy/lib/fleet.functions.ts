// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const getFleetHealth = engineFn("getFleetHealth", { method: "GET", path: "/v1/owner/fleet", map: (r: any) => ({ routers: Array.isArray(r) ? r : [] }) });
export const listFleetScans = engineFn("listFleetScans");
export const getAiScanQuota = engineFn("getAiScanQuota");
export const runAiScanNow = engineFn("runAiScanNow");
export const listTerminalRouters = engineFn("listTerminalRouters");
export const runTerminalCommand = engineFn("runTerminalCommand");
export const applyInsightFix = engineFn("applyInsightFix");
export const DEFAULT_MONTHLY_AI_SCAN_LIMIT = 0;
