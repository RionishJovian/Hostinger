// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export type OverviewSummary = {
  shops: Array<{ id: string; name: string }>;
  routers: Array<{ id: string; name: string; connected: boolean; last_seen: number | null }>;
  open_incidents: number;
  today_revenue: { amount: number; currency: string };
  subscription_status: string;
};
export type LegacyOverview = OverviewSummary & {
  router_count: number;
  site_count: number;
};
export const getOverviewSummary = engineFn<LegacyOverview>("getOverviewSummary", {
  method: "GET",
  path: "/v1/owner/overview",
  map: (value) => {
    const result = (value && typeof value === "object" ? value : {}) as Partial<OverviewSummary>;
    const shops = Array.isArray(result.shops) ? result.shops : [];
    const routers = Array.isArray(result.routers) ? result.routers : [];
    return { ...result, shops, routers, router_count: routers.length, site_count: shops.length } as LegacyOverview;
  },
});
