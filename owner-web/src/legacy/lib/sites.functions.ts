// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listSites = engineFn("listSites");
export const saveSite = engineFn("saveSite");
export const deleteSite = engineFn("deleteSite");
export const assignRouterToSite = engineFn("assignRouterToSite");
export const listRoutersWithSite = engineFn("listRoutersWithSite");
export const listPlatformActiveSites = engineFn("listPlatformActiveSites");
