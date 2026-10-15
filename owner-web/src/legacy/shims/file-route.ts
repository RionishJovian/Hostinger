// @ts-nocheck
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { createFileRoute, createLazyFileRoute } from "@/shims/file-route";
// Lets copied Lovable route files keep `createFileRoute(...)({ component })`
// while owner-web registers them in its own code-based router.
export function createFileRoute(_path: string) {
  return (options: any) => ({
    options,
    useSearch: () => { const s = useSearch({ strict: false }) as any; try { return options.validateSearch ? options.validateSearch(s ?? {}) : s; } catch { return s ?? {}; } },
    useParams: () => useParams({ strict: false }) as any,
    useNavigate: () => useNavigate(),
    useLoaderData: () => undefined,
    useRouteContext: () => ({}),
  });
}
export function createLazyFileRoute(path: string) { return createFileRoute(path); }
