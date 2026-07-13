const LOCAL_API_BASE = "http://localhost:8000";
const DEPLOYED_API_BASE = "https://twinbiz-ai.onrender.com";

function getApiBase() {
  if (typeof window === "undefined") {
    return (process.env.NEXT_PUBLIC_API_URL ?? LOCAL_API_BASE).replace(/\/api\/?$/, "");
  }

  const hostname = window.location.hostname;
  const isLocal =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "0.0.0.0" ||
    hostname.endsWith(".local");

  return isLocal ? LOCAL_API_BASE : DEPLOYED_API_BASE;
}

const API_BASE = getApiBase();

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("twinbiz_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("twinbiz_token", token);
  else localStorage.removeItem("twinbiz_token");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (res.status === 401 && typeof window !== "undefined") {
    setToken(null);
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {}
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

async function upload<T>(path: string, form: FormData): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form, // browser sets multipart boundary
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {}
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  upload,
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  csvUrl: (path: string) => `${API_BASE}${path}`,
};

export { API_BASE };
