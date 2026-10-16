// @ts-nocheck
// Data layer for the copied Lovable screens. Every call goes to the
// Hostinger engine's owner-scoped API (/v1/owner/*). When the engine has no
// endpoint yet, reads return an empty value and writes report "coming soon".
import { request, logout as apiLogout } from "../lib/api";

export class ComingSoonError extends Error {
  capability: string;
  constructor(capability: string) {
    super("Coming soon — MikroMagic's engine does not support this yet. Nothing was changed.");
    this.name = "ComingSoonError";
    this.capability = capability;
  }
}

type Spec = { method?: "GET" | "POST"; path?: string; map?: (r: any) => any };
const READ = /^(get|list|load|fetch|read|search|count|has|is|check|preview|explain|describe|summar|resolve|lookup|find|export|query|watch|poll|probe|verify)/i;

export function engineFn(name: string, spec: Spec = {}) {
  const fn = async (input?: { data?: unknown }) => {
    if (spec.path) {
      const method = spec.method ?? "GET";
      const r = await request<any>(spec.path, method === "GET" ? {} : { method, body: JSON.stringify(input?.data ?? {}) });
      if (r && typeof r === "object" && !Array.isArray(r) && r.status === "coming_soon") return emptyFor(name);
      return spec.map ? spec.map(r) : r;
    }
    if (READ.test(name)) return spec.map ? spec.map(null) : emptyFor(name);
    throw new ComingSoonError(name);
  };
  return Object.assign(fn, { engineName: name, comingSoon: !spec.path });
}

function emptyFor(name: string): any {
  return /^list/i.test(name) ? [] : null;
}

export async function logout() {
  await apiLogout();
}
