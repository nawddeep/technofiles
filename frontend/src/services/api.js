const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";

function getSessionId() {
  return localStorage.getItem("session_id");
}

function authHeaders() {
  const sid = getSessionId();
  return {
    "Content-Type": "application/json",
    ...(sid ? { "X-Session-Id": sid } : {}),
  };
}

async function handleResponse(res) {
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error("Server returned an unexpected response. Please try again.");
  }
  if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again.");
  return data;
}

async function safeFetch(url, options) {
  try {
    const res = await fetch(url, options);
    return await handleResponse(res);
  } catch (err) {
    // Network error (backend offline / no internet)
    if (err instanceof TypeError && err.message.includes("fetch")) {
      throw new Error("Cannot connect to the server. Please make sure the backend is running.");
    }
    throw err;
  }
}

export async function apiSignup({ fullName, email, password }) {
  const data = await safeFetch(`${BASE_URL}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fullName, email, password }),
  });
  localStorage.setItem("session_id", data.session_id);
  localStorage.setItem("user", JSON.stringify(data.user));
  return data;
}

export async function apiLogin({ email, password }) {
  const data = await safeFetch(`${BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("session_id", data.session_id);
  localStorage.setItem("user", JSON.stringify(data.user));
  return data;
}

export async function apiLogout() {
  try {
    await fetch(`${BASE_URL}/api/auth/logout`, {
      method: "POST",
      headers: authHeaders(),
    });
  } catch {
    // Even if logout request fails, clear local session
  }
  localStorage.removeItem("session_id");
  localStorage.removeItem("user");
}

export async function apiGetMe() {
  return await safeFetch(`${BASE_URL}/api/auth/me`, {
    headers: authHeaders(),
  });
}

export async function apiOnboarding(data) {
  const res = await safeFetch(`${BASE_URL}/api/auth/onboarding`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  localStorage.setItem("user", JSON.stringify(res.user));
  return res;
}

