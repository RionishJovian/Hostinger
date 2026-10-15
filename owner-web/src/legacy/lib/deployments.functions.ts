// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listDeployments = engineFn("listDeployments", { method: "GET", path: "/v1/owner/deployments", map: (r: any) => (Array.isArray(r) ? r : []) });
