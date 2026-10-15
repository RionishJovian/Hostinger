// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listVoucherPrices = engineFn("listVoucherPrices");
export const saveVoucherPrice = engineFn("saveVoucherPrice");
export const deleteVoucherPrice = engineFn("deleteVoucherPrice");
export const recordVoucherSale = engineFn("recordVoucherSale");
export const deleteVoucherSale = engineFn("deleteVoucherSale");
export const listVoucherSales = engineFn("listVoucherSales");
export const revenueRollup = engineFn("revenueRollup");
export const revenueDashboard = engineFn("revenueDashboard");
export const planPerformanceReport = engineFn("planPerformanceReport");
export const voucherLedger = engineFn("voucherLedger");
