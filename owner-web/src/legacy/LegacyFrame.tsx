// @ts-nocheck
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate } from "@tanstack/react-router";
import { InAppNoticeProvider } from "@/components/InAppNotice";
import { LanguageProvider } from "@/lib/i18n/LanguageProvider";
import { useSession } from "../lib/session";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

export type Audience = "sme" | "owner" | "platform" | "agent";

/** Wraps a copied Lovable screen with the providers it expects and the screen-decision role gate. */
export function LegacyFrame({ audience = "sme", children }: { audience?: Audience; children: ReactNode }) {
  const { me } = useSession() as { me: any };
  const allowed = audience === "platform" ? me?.role === "platform" && me?.platform_owner === true
    : audience === "agent" ? me?.role === "agent"
    : audience === "owner" ? me?.role === "sme" && !me?.staff_profile
    : me?.role === "sme";
  if (me && !allowed) return <Navigate to="/app" replace />;
  return <QueryClientProvider client={queryClient}><LanguageProvider><InAppNoticeProvider><div className="legacy-screen">{children}</div></InAppNoticeProvider></LanguageProvider></QueryClientProvider>;
}
