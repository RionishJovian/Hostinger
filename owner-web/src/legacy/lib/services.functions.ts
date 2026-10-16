// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type ServicePlanRead = {
  status: { tier: string; tier_expires_at: number | null; never_expires: boolean };
  promo: null;
  roles: string[];
  wallet: { balance: number };
  services: Array<Record<string, unknown>>;
  purchases: Array<Record<string, unknown>>;
  isPlatformAdmin: boolean;
};
export const listServices = engineFn<ServicePlanRead>("listServices", {
  method: "GET",
  path: "/v1/owner/services/plan",
  map: (value) => {
    const plan = (value && typeof value === "object" ? value : {}) as { state?: string; period_end?: number | null };
    return {
      status: { tier: plan.state ?? "unassigned", tier_expires_at: plan.period_end ?? null, never_expires: false },
      promo: null,
      roles: [],
      wallet: { balance: 0 },
      services: [],
      purchases: [],
      isPlatformAdmin: false,
    };
  },
});
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
