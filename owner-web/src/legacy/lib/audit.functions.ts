// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const AUDIT_OPS_DEFAULT_LIMIT = 100;
export const AUDIT_SAVE_LIMIT = 200;
export const AUDIT_POLL_MS = 15_000;
export const ROUTER_OPS_AUDIT_QUERY_KEY = ["router-ops-audit"] as const;
export const ROUTER_SAVE_AUDIT_QUERY_KEY = ["router-save-audit"] as const;
export const listRouterOpsAudit = engineFn("listRouterOpsAudit", { map: () => ({ rows: [], total: 0 }) });
