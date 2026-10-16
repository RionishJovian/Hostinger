// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type TopologySite = { siteId: string; siteName: string; location: string | null; routers: Array<{ id: string; name: string; model: string | null }> };
export type TopologyPayload = { sites: Array<{ id: string; name: string; routers: TopologySite["routers"]; devices: Array<Record<string, unknown>> }> };
export const getOwnerTopology = engineFn<TopologyPayload>("getOwnerTopology", { method: "GET", path: "/v1/owner/topology" });
export const assertTopologyPlatformAccess = engineFn("assertTopologyOwnerAccess");
export const listTopologySites = engineFn<TopologySite[]>("listTopologySites", {
  method: "GET",
  path: "/v1/owner/topology",
  map: (value) => {
    const payload = (value && typeof value === "object" ? value : {}) as Partial<TopologyPayload>;
    return (payload.sites ?? []).map((site) => ({ siteId: site.id, siteName: site.name, location: null, routers: site.routers ?? [] }));
  },
});
export const getSiteTopology = engineFn<Record<string, unknown>>("getSiteTopology", { method: "GET", path: "/v1/owner/topology", map: (value) => ({ nodes: [], portLabels: [], ...(value && typeof value === "object" ? value : {}) }) });
export const investigateTopologyWithMagicDude = engineFn("investigateTopologyWithMagicDude");
export const saveSiteTopologyLabels = engineFn("saveSiteTopologyLabels");
