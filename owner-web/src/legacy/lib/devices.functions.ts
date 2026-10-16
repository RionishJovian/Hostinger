// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type DeviceKind = string;
export type DeviceRequest = Record<string, unknown>;
export const listDevices = engineFn<DeviceRequest[]>("listDevices", { method: "GET", path: "/v1/owner/devices" });
export const deviceLimits = engineFn("deviceLimits");
export const requestDeviceSlot = engineFn("requestDeviceSlot");
export const listDeviceRequests = engineFn("listDeviceRequests");
export const decideDeviceRequest = engineFn("decideDeviceRequest");
