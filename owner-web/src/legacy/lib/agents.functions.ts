// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const TIER_PASS_POINTS = { monthly: 15, annual: 150, plus: 0 } as const;
export const agentCreateUser = engineFn("agentCreateUser");
export const listMyReferrals = engineFn("listMyReferrals");
export const listAgentPoints = engineFn("listAgentPoints", { method: "GET", path: "/v1/agent/coins", map: (r: any) => { const ledger = Array.isArray(r?.ledger) ? r.ledger : []; return { total_points: Object.values(r?.balances ?? {}).reduce((a: number, b: any) => a + Number(b || 0), 0), month_points: 0, purchase_count: ledger.length, by_agent: [], events: ledger.map((e: any) => ({ id: e.id, points: e.amount, created_at: e.created, agent_name: "", referred_name: "" })) }; } });
export const agentCommissionReport = engineFn("agentCommissionReport");
