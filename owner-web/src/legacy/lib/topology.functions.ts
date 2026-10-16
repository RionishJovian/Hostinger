// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const getOwnerTopology = engineFn<Record<string, unknown>>("getOwnerTopology", { method: "GET", path: "/v1/owner/topology" });
export const assertTopologyPlatformAccess = engineFn("assertTopologyPlatformAccess");
export const listTopologySites = engineFn("listTopologySites");
export const getSiteTopology = engineFn("getSiteTopology");
export const investigateTopologyWithMagicDude = engineFn("investigateTopologyWithMagicDude");
export const saveSiteTopologyLabels = engineFn("saveSiteTopologyLabels");
