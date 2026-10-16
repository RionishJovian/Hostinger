// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listManagedDevices = engineFn<Array<Record<string, unknown>>>("listManagedDevices", {
  method: "GET",
  path: "/v1/owner/devices",
  map: (value) => (Array.isArray(value) ? value as Array<Record<string, unknown>> : []),
});
export const saveManagedDevice = engineFn("saveManagedDevice");
export const deleteManagedDevice = engineFn("deleteManagedDevice");
export const readDevicePorts = engineFn("readDevicePorts");
export const cyclePoePort = engineFn("cyclePoePort");
