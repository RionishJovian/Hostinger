// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const listServices = engineFn("listServices");
export const developerBankAccounts = engineFn("developerBankAccounts");
export const listPlatformServiceBankAccounts = engineFn("listPlatformServiceBankAccounts");
export const savePlatformServiceBankAccount = engineFn("savePlatformServiceBankAccount");
export const submitServicePurchase = engineFn("submitServicePurchase");
export const purchaseServiceWithMagicCoins = engineFn("purchaseServiceWithMagicCoins");
export const submitMagicCoinPurchase = engineFn("submitMagicCoinPurchase");
export const serviceReceiptUrl = engineFn("serviceReceiptUrl");
export const listServicePurchases = engineFn("listServicePurchases");
export const approveServicePurchase = engineFn("approveServicePurchase");
export const rejectServicePurchase = engineFn("rejectServicePurchase");
export const refundServicePurchase = engineFn("refundServicePurchase");
