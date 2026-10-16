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

type JsonRecord = Record<string, unknown>;
type Spec<T = unknown> = { method?: "GET" | "POST"; path?: string; map?: (r: unknown) => T };
const READ = /^(get|list|load|fetch|read|search|count|has|is|check|preview|explain|describe|summar|resolve|lookup|find|export|query|watch|poll|probe|verify)/i;

export function engineFn<T = unknown>(name: string, spec: Spec<T> = {}) {
  const fn = async (input?: { data?: unknown }): Promise<T> => {
    if (spec.path) {
      const method = spec.method ?? "GET";
      const r = await request<unknown>(spec.path, method === "GET" ? {} : { method, body: JSON.stringify(input?.data ?? {}) });
      if (r && typeof r === "object" && !Array.isArray(r) && (r as JsonRecord).status === "coming_soon") return emptyFor(name) as T;
      return spec.map ? spec.map(r) : r as T;
    }
    if (READ.test(name)) return spec.map ? spec.map(null) : emptyFor(name) as T;
    throw new ComingSoonError(name);
  };
  return Object.assign(fn, { engineName: name, comingSoon: !spec.path });
}

function emptyFor(name: string): unknown {
  return /^list/i.test(name) ? [] : null;
}

export async function logout() {
  await apiLogout();
}
