// @ts-nocheck
// Engine data layer for the copied Lovable screen: calls go to /v1/owner/* or report coming soon.
import { engineFn } from "@/engine";
export const getMe = engineFn("getMe", { method: "GET", path: "/v1/me", map: (m: any) => m && ({ id: m.id, email: null, profile: { display_name: m.username }, roles: m.role === "agent" ? ["agent"] : m.role === "sme" ? (m.staff_profile ? ["client"] : ["client", "primary"]) : [], features: [], client_expires_at: null, has_active_plus: false, account: { restricted: Boolean(m.subscription_restricted) }, isPlatformAdmin: m.role === "platform" && m.platform_owner === true }) });
