import React, { createContext, useContext, useEffect, useState } from "react";
import { apiBaseUrl, apiHeaders, getStoredToken, setStoredToken } from "../config";

export interface User {
  id: string;
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  status: "idle" | "loading" | "authenticated" | "unauthenticated";
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, name: string, password: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(getStoredToken());
  const [status, setStatus] = useState<"idle" | "loading" | "authenticated" | "unauthenticated">("loading");
  const [error, setError] = useState<string | null>(null);

  const fetchUser = async (authToken: string) => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/auth/me`, {
        headers: apiHeaders(),
      });
      if (res.ok) {
        const userData: User = await res.json();
        setUser(userData);
        setStatus("authenticated");
      } else {
        setStoredToken(null);
        setTokenState(null);
        setUser(null);
        setStatus("unauthenticated");
      }
    } catch {
      setStoredToken(null);
      setTokenState(null);
      setUser(null);
      setStatus("unauthenticated");
    }
  };

  useEffect(() => {
    const storedToken = getStoredToken();
    if (storedToken) {
      setTokenState(storedToken);
      fetchUser(storedToken);
    } else {
      setStatus("unauthenticated");
    }
  }, []);

  const login = async (email: string, password: string) => {
    setError(null);
    setStatus("loading");
    try {
      const res = await fetch(`${apiBaseUrl}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Login failed. Please check your credentials.");
      }
      setStoredToken(data.access_token);
      setTokenState(data.access_token);
      setUser(data.user);
      setStatus("authenticated");
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
      setStatus("unauthenticated");
      throw err;
    }
  };

  const signup = async (email: string, name: string, password: string) => {
    setError(null);
    setStatus("loading");
    try {
      const res = await fetch(`${apiBaseUrl}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, name, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Signup failed. Please try again.");
      }
      setStoredToken(data.access_token);
      setTokenState(data.access_token);
      setUser(data.user);
      setStatus("authenticated");
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
      setStatus("unauthenticated");
      throw err;
    }
  };

  const logout = () => {
    setStoredToken(null);
    setTokenState(null);
    setUser(null);
    setError(null);
    setStatus("unauthenticated");
  };

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        status,
        error,
        login,
        signup,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
