// FIX 2.17: API Versioning - supports both /api/ (legacy) and /api/v1/ (current)
// All endpoints are available at both routes for backward compatibility
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:5000";
const API_VERSION = "v1";  // Current API version

// FIX 2.11: Only CSRF token in localStorage
// Access/refresh tokens are httpOnly cookies from server (XSS-safe, sent automatically)
let csrfToken = localStorage.getItem("csrf_token") || "";
let refreshPromise = null;  // FIX 2.14: Prevent concurrent refresh race conditions

// Only store CSRF token (must be readable by JS for headers)
export function setTokens(access, refresh, csrf) {
  // NOTE: access and refresh tokens come from server as httpOnly cookies
  // We don't store them in memory - browser sends them automatically
  if (csrf) {
    csrfToken = csrf;
    localStorage.setItem("csrf_token", csrf);
  }
}

export function clearTokens() {
  csrfToken = "";
  localStorage.removeItem("csrf_token");
  // HTTP-only cookies are cleared server-side via logout endpoint
}

export function getCsrfToken() { return csrfToken; }

// FIX 2.14: Single refresh promise prevents concurrent refresh race conditions
async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;  // Reuse existing refresh request
  
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",  // Browser sends httpOnly cookies automatically
      });
      if (!res.ok) {
        clearTokens();
        return false;
      }
      const data = await res.json();
      setTokens(null, null, data.csrf_token);  // Update CSRF token only
      return true;
    } catch {
      return false;
    }
  })();
  
  const result = await refreshPromise;
  refreshPromise = null;
  return result;
}

export async function apiFetch(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  
  // Add CSRF token for state-changing requests
  if (csrfToken && options.method && !["GET", "HEAD", "OPTIONS"].includes(options.method.toUpperCase())) {
    headers["X-CSRF-Token"] = csrfToken;
  }
  
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: "include",  // Browser automatically sends httpOnly cookie tokens
  });
  
  // If 401, try refreshing token once
  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const retryRes = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
        credentials: "include",
      });
      if (retryRes.status === 401) {
        window.dispatchEvent(new Event("auth:logout"));
      }
      return retryRes;
    }
    window.dispatchEvent(new Event("auth:logout"));
  }
  return res;
}

// Auth API
export const authAPI = {
  getCsrfToken: () => fetch(`${API_BASE}/api/auth/csrf-token`, { credentials: "include" }).then(r => r.json()).then(d => { setTokens(null, null, d.csrf_token); return d; }),
  signup: (data) => apiFetch("/api/auth/signup", { method: "POST", body: JSON.stringify(data) }),
  login: (data) => apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify(data) }),
  logout: () => apiFetch("/api/auth/logout", { method: "POST" }),
  me: () => apiFetch("/api/auth/me"),
  onboarding: (data) => apiFetch("/api/auth/onboarding", { method: "POST", body: JSON.stringify(data) }),
  changePassword: (data) => apiFetch("/api/auth/change-password", { method: "POST", body: JSON.stringify(data) }),
  forgotPassword: (data) => apiFetch("/api/auth/forgot-password", { method: "POST", body: JSON.stringify(data) }),
  resetPassword: (data) => apiFetch("/api/auth/reset-password", { method: "POST", body: JSON.stringify(data) }),
  verifyEmail: (data) => apiFetch("/api/auth/verify-email", { method: "POST", body: JSON.stringify(data) }),
  resendVerification: (data) => apiFetch("/api/auth/resend-verification", { method: "POST", body: JSON.stringify(data) }),
  sessions: () => apiFetch("/api/auth/sessions"),
  revokeSession: (sid) => apiFetch(`/api/auth/sessions/${sid}/revoke`, { method: "POST" }),
};

// Chat API
export const chatAPI = {
  sendMessage: (data, sessionId) => apiFetch("/api/chat/message", {
    method: "POST",
    body: JSON.stringify(data),
    headers: sessionId ? { "X-Session-Id": sessionId } : {},
  }),
  getHistory: () => apiFetch("/api/chat/history"),
  clearChat: (sessionId) => apiFetch("/api/chat/clear", {
    method: "POST",
    headers: sessionId ? { "X-Session-Id": sessionId } : {},
  }),
};
