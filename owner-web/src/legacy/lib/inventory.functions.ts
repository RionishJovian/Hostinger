// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listManagedDevices = engineFn("listManagedDevices");
export const saveManagedDevice = engineFn("saveManagedDevice");
export const deleteManagedDevice = engineFn("deleteManagedDevice");
export const readDevicePorts = engineFn("readDevicePorts");
export const cyclePoePort = engineFn("cyclePoePort");
