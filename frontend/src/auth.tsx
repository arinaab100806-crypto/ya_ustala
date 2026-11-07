import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import type { TokenResponse, User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: { username: string; email: string; password: string }) => Promise<void>;
  registerOrganization: (payload: {
    username: string;
    email: string;
    password: string;
    organization_name: string;
    organization_description: string;
  }) => Promise<void>;
  updateProfile: (payload: { full_name: string; birth_date: string | null }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function storeSession(data: TokenResponse, setUser: (user: User) => void) {
  localStorage.setItem("token", data.access_token);
  setUser(data.user);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => localStorage.removeItem("token"))
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async login(email, password) {
        const data = await api<TokenResponse>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        storeSession(data, setUser);
      },
      async register(payload) {
        const data = await api<TokenResponse>("/auth/register", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        storeSession(data, setUser);
      },
      async registerOrganization(payload) {
        const data = await api<TokenResponse>("/auth/register-organization", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        storeSession(data, setUser);
      },
      async updateProfile(payload) {
        const data = await api<User>("/auth/profile", { method: "PATCH", body: JSON.stringify(payload) });
        setUser(data);
      },
      logout() {
        localStorage.removeItem("token");
        setUser(null);
      },
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider отсутствует");
  return value;
}
