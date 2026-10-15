// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const getWifiHotspotProbe = engineFn("getWifiHotspotProbe");
export const previewHotspotSetupFn = engineFn("previewHotspotSetupFn");
export const applyHotspotSetupFn = engineFn("applyHotspotSetupFn");
export const listHotspotSetupAuditFn = engineFn("listHotspotSetupAuditFn");
export const removeMagicHotspotGuestFn = engineFn("removeMagicHotspotGuestFn");
export const createWifiHotspotSsid = applyHotspotSetupFn;
