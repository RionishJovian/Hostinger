// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listDeployments = engineFn<Array<Record<string, unknown>>>("listDeployments", { method: "GET", path: "/v1/owner/deployments", map: (r) => (Array.isArray(r) ? r as Array<Record<string, unknown>> : []) });
