// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type DeviceKind = any;
export type DeviceRequest = any;
export const deviceLimits = engineFn("deviceLimits");
export const requestDeviceSlot = engineFn("requestDeviceSlot");
export const listDeviceRequests = engineFn("listDeviceRequests");
export const decideDeviceRequest = engineFn("decideDeviceRequest");
