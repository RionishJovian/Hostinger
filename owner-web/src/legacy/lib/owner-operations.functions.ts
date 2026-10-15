// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const getOwnerOperationsDashboard = engineFn("getOwnerOperationsDashboard");
export const createVoucherReseller = engineFn("createVoucherReseller");
export const assignVoucherToReseller = engineFn("assignVoucherToReseller");
export const setResellerAssignmentStatus = engineFn("setResellerAssignmentStatus");
export const closeOwnerBusinessDay = engineFn("closeOwnerBusinessDay");
