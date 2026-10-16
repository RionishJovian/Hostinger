// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type OwnerOperationsDashboard = {
  status: Record<string, number>;
  alerts: { low_stock: boolean; routers_offline: string[]; cash_close_missing: boolean };
  gross_mmk: number;
  cash_mmk: number;
  routers: Array<{ name: string; online: boolean }>;
  open_cash_close: boolean;
  daily_closes: Array<{ business_day: string; counted_cash_mmk: number }>;
  resellers: Array<{ id: string; shop_name: string; contact_name: string; location?: string; phone?: string; cash_due_mmk: number; issued: number; sold: number; returned: number; cancelled: number }>;
  can_manage_reseller_inventory: boolean;
  reseller_add_key: { active_count: number };
};
export const getOwnerOperationsDashboard = engineFn<OwnerOperationsDashboard>("getOwnerOperationsDashboard");
export const createVoucherReseller = engineFn("createVoucherReseller");
export const assignVoucherToReseller = engineFn("assignVoucherToReseller");
export const setResellerAssignmentStatus = engineFn("setResellerAssignmentStatus");
export const closeOwnerBusinessDay = engineFn("closeOwnerBusinessDay");
