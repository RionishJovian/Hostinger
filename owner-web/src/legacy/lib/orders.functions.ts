// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listOrders = engineFn("listOrders");
export const recordCashSale = engineFn("recordCashSale");
export const refundOrder = engineFn("refundOrder");
export const cancelOrder = engineFn("cancelOrder");
export const listSessions = engineFn("listSessions");
export const getSession = engineFn("getSession");
export const syncRouterSessions = engineFn("syncRouterSessions");
export const revenueBreakdown = engineFn("revenueBreakdown");
export const requireFinanceAccess = engineFn("requireFinanceAccess");
