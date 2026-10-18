/**
 * Axios instance for the Django API.
 *
 * - `withCredentials`: the browser sends the HTTP-only auth cookies; JavaScript never sees the tokens.
 * - CSRF: unsafe requests carry X-CSRFToken (fetched once from /auth/csrf/).
 * - 401 handling: one shared refresh call, then the original request is retried once.
 */
import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 45_000, // AI endpoints can take a while
  headers: { "Content-Type": "application/json" },
});

let csrfToken: string | null = null;
let csrfPromise: Promise<string> | null = null;

export async function ensureCsrfToken(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  if (!csrfPromise || force) {
    csrfPromise = axios
      .get<{ csrfToken: string }>(`${API_BASE_URL}/auth/csrf/`, { withCredentials: true })
      .then((res) => {
        csrfToken = res.data.csrfToken;
        return csrfToken;
      })
      .finally(() => {
        csrfPromise = null;
      });
  }
  return csrfPromise;
}

const SAFE_METHODS = ["get", "head", "options"];

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const method = (config.method || "get").toLowerCase();
  if (!SAFE_METHODS.includes(method)) {
    const token = await ensureCsrfToken();
    config.headers.set("X-CSRFToken", token);
  }
  return config;
});

// --- automatic refresh on 401 -------------------------------------------------
let refreshPromise: Promise<void> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

async function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const token = await ensureCsrfToken();
      await axios.post(`${API_BASE_URL}/auth/refresh/`, null, {
        withCredentials: true,
        headers: { "X-CSRFToken": token },
      });
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

const NO_REFRESH_PATHS = ["/auth/login/", "/auth/register/", "/auth/refresh/", "/auth/logout/", "/auth/csrf/"];

type RetryConfig = AxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined;
    const status = error.response?.status;
    const url = config?.url || "";

    // CSRF token rotated (e.g. after login): fetch a new one and retry once.
    if (status === 403 && config && !config._retried && String((error.response?.data as { detail?: string })?.detail || "").startsWith("CSRF")) {
      config._retried = true;
      await ensureCsrfToken(true);
      return api(config);
    }

    if (status === 401 && config && !config._retried && !NO_REFRESH_PATHS.some((p) => url.includes(p))) {
      config._retried = true;
      try {
        await refreshSession();
        return api(config);
      } catch {
        onSessionExpired?.();
      }
    }
    return Promise.reject(error);
  },
);

/** Turns any API error into a readable message (DRF field errors included). */
export function getErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return error.code === "ECONNABORTED"
        ? "The request timed out. Please try again."
        : "Cannot reach the server. Check your connection.";
    }
    const data = error.response.data as unknown;
    if (data && typeof data === "object") {
      const record = data as Record<string, unknown>;
      if (typeof record.detail === "string") return record.detail;
      const first = Object.entries(record)[0];
      if (first) {
        const [field, value] = first;
        const text = Array.isArray(value) ? String(value[0]) : typeof value === "string" ? value : "";
        if (text) return field === "non_field_errors" || field === "detail" ? text : `${humanize(field)}: ${text}`;
      }
    }
    if (error.response.status === 429) return "Too many requests. Please wait a moment and try again.";
    if (error.response.status >= 500) return "The server had a problem. Please try again later.";
  }
  return fallback;
}

/** Field-level errors from a DRF 400 response, for react-hook-form. */
export function getFieldErrors(error: unknown): Record<string, string> {
  if (!axios.isAxiosError(error) || error.response?.status !== 400) return {};
  const data = error.response.data as Record<string, unknown>;
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(data || {})) {
    if (Array.isArray(value) && value.length) out[key] = String(value[0]);
    else if (typeof value === "string") out[key] = value;
  }
  return out;
}

function humanize(field: string) {
  return field.replace(/_id$/, "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
