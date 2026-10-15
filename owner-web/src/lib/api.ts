export type ApiValue = null | boolean | number | string | ApiValue[] | { [key: string]: ApiValue };

export type Me = {
  id: string;
  username: string;
  role: string;
  tenant_id: string | null;
  must_change_password: boolean;
  staff_profile: string | null;
  subscription_restricted: boolean;
};

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

let accessToken = "";

function messageFrom(data: unknown): { message: string; code?: string } {
  if (!data || typeof data !== "object") return { message: "MikroMagic could not complete that request." };
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return { message: detail };
  if (Array.isArray(detail)) {
    return { message: detail.map((item) => typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)).join("; ") };
  }
  if (detail && typeof detail === "object") {
    const record = detail as { message?: unknown; code?: unknown };
    return {
      message: typeof record.message === "string" ? record.message : "MikroMagic could not complete that request.",
      code: typeof record.code === "string" ? record.code : undefined,
    };
  }
  return { message: "MikroMagic could not complete that request." };
}

export async function request<T = ApiValue>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(path.startsWith("/v1/") ? path : `/v1/${path.replace(/^\/+/, "")}`, {
    ...init,
    credentials: "include",
    headers,
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const error = messageFrom(data);
    if (response.status === 401 && !path.endsWith("/auth/login")) accessToken = "";
    throw new ApiError(error.message, response.status, error.code);
  }
  return data as T;
}

export function get<T = ApiValue>(path: string): Promise<T> {
  return request<T>(path);
}

export function post<T = ApiValue>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export async function login(username: string, password: string, mfaCode?: string): Promise<Me> {
  const payload: { username: string; password: string; mfa_code?: string } = { username, password };
  if (mfaCode?.trim()) payload.mfa_code = mfaCode.trim();
  const result = await post<{ access_token: string }>("/v1/auth/login", payload);
  accessToken = result.access_token;
  return get<Me>("/v1/me");
}

export async function logout(): Promise<void> {
  await post("/v1/auth/logout");
  accessToken = "";
}

export function clearSession(): void {
  accessToken = "";
}
