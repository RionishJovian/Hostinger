// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listAppUsers = engineFn("listAppUsers");
export const setAppUserScanLimit = engineFn("setAppUserScanLimit");
export const setAppUserExpires = engineFn("setAppUserExpires");
export const createAppUser = engineFn("createAppUser");
export const setAppUserRole = engineFn("setAppUserRole");
export const activateAppUser = engineFn("activateAppUser");
export const approvePendingUser = engineFn("approvePendingUser");
export const rejectPendingUser = engineFn("rejectPendingUser");
export const resetAppUserPassword = engineFn("resetAppUserPassword");
export const deleteAppUser = engineFn("deleteAppUser");
