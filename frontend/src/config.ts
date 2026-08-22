const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() && envUrl !== "http://localhost:8000" && envUrl !== "http://127.0.0.1:8000") {
    return envUrl.trim().replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.location && window.location.hostname) {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:8000`;
  }
  return "http://localhost:8000";
};

export const apiBaseUrl = getApiBaseUrl();
export const wsBaseUrl = apiBaseUrl.replace(/^http/, "ws");
const API_KEY = import.meta.env.VITE_API_KEY || "";
const TOKEN_STORAGE_KEY = "researchswarm_token";

export const getStoredToken = (): string | null => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
};

export const setStoredToken = (token: string | null): void => {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
};

export const apiHeaders = (headers: HeadersInit = {}): HeadersInit => {
  const token = getStoredToken();
  return {
    ...headers,
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  };
};

export const apiMultipartHeaders = (headers: HeadersInit = {}): HeadersInit => {
  const token = getStoredToken();
  return {
    ...headers,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  };
};

export const apiAuthQuery = (): string => {
  const token = getStoredToken();
  if (token) {
    return `token=${encodeURIComponent(token)}`;
  }
  if (!API_KEY) return "";
  return `api_key=${encodeURIComponent(API_KEY)}`;
};
