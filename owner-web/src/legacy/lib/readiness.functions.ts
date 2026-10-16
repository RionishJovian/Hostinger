import { engineFn } from "@/engine";

export type OwnerReadiness = {
  ready: boolean;
  items: Array<{
    router_id: string;
    router_name: string;
    hub: boolean;
    management: boolean;
    connected: boolean;
    fix_path: string | null;
  }>;
};

export const getOwnerReadiness = engineFn<OwnerReadiness>("getOwnerReadiness", {
  method: "GET",
  path: "/v1/owner/readiness",
});
