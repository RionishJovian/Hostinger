// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const probeCloudDns = engineFn("probeCloudDns");
export const checkPublicReachability = engineFn("checkPublicReachability");
export const probeWanExposure = engineFn("probeWanExposure");
export const getSnapshot = engineFn("getSnapshot");
export const kickUser = engineFn("kickUser");
export const banMac = engineFn("banMac");
export const removeBinding = engineFn("removeBinding");
export const unbanMac = engineFn("unbanMac");
export const setUserRate = engineFn("setUserRate");
export const addVoucher = engineFn("addVoucher");
export const bulkVouchers = engineFn("bulkVouchers");
export const deleteVoucher = engineFn("deleteVoucher");
export const redeemVoucher = engineFn("redeemVoucher");
export const executeQuickSetupRollback = engineFn("executeQuickSetupRollback");
