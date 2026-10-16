import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, clearSession, get, login, logout, type Me } from "./api";

type SessionState = {
  me: Me | null;
  loading: boolean;
  signIn: (username: string, password: string, mfaCode?: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await get<Me>("/v1/me"));
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      setMe(null);
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const value = useMemo<SessionState>(() => ({
    me,
    loading,
    async signIn(username, password, mfaCode) {
      setMe(await login(username, password, mfaCode));
    },
    async signOut() {
      try { await logout(); } finally { clearSession(); setMe(null); }
    },
    refresh,
  }), [loading, me, refresh]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const session = useContext(SessionContext);
  if (!session) throw new Error("SessionProvider is missing");
  return session;
}
