// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const getMyPortalModePermissions = engineFn("getMyPortalModePermissions");
export const listPortalModeGrantsAdmin = engineFn("listPortalModeGrantsAdmin");
export const setPortalModeRoleDefaults = engineFn("setPortalModeRoleDefaults");
export const setPortalModeUserGrants = engineFn("setPortalModeUserGrants");
export const assertCanOperateGuestMode = engineFn("assertCanOperateGuestMode");
