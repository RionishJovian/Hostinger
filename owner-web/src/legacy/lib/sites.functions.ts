// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type OwnerSite = { id: string; name: string; location: string | null; routers: Array<Record<string, unknown>>; devices: Array<Record<string, unknown>> };
export const listSites = engineFn<OwnerSite[]>("listSites", {
  method: "GET",
  path: "/v1/owner/topology",
  map: (value) => {
    const payload = (value && typeof value === "object" ? value : {}) as { sites?: OwnerSite[] };
    return payload.sites ?? [];
  },
});
export const saveSite = engineFn("saveSite");
export const deleteSite = engineFn("deleteSite");
export const assignRouterToSite = engineFn("assignRouterToSite");
export const listRoutersWithSite = engineFn<Array<Record<string, unknown>>>("listRoutersWithSite", { method: "GET", path: "/v1/owner/fleet", map: (value) => Array.isArray(value) ? value as Array<Record<string, unknown>> : [] });
export const listPlatformActiveSites = engineFn("listPlatformActiveSites");
