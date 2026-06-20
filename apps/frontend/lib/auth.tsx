"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, tokens, type UserProfile } from "@/lib/api";

interface AuthState {
  user: UserProfile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const pair = await api.login(email, password);
    tokens.set(pair.access_token, pair.refresh_token);
    setUser(await api.me());
  }

  async function register(email: string, password: string, displayName?: string) {
    const pair = await api.register(email, password, displayName);
    tokens.set(pair.access_token, pair.refresh_token);
    setUser(await api.me());
  }

  function logout() {
    const refresh = tokens.refresh();
    if (refresh) api.logout(refresh).catch(() => undefined);
    tokens.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
