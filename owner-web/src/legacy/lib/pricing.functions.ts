// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const PRICING_PROMO_FALLBACK: PricingPromo = {
  active: true,
  starts_on: "2026-08-23",
  ends_on: "2026-09-24",
  label: "Grand opening gift — 30% off Monthly & Annual",
  monthly_promo_mmk: 66500,
  monthly_standard_mmk: 95000,
  annual_promo_mmk: 731500,
  annual_standard_mmk: 1045000,
};
export type PricingPromo = any;
export const getPricingPromo = engineFn("getPricingPromo");
export const isPromoWindowLive = engineFn("isPromoWindowLive");
export const applyPromoWindow = engineFn("applyPromoWindow");
