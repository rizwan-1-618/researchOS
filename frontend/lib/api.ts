export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let refresh: Promise<boolean> | null = null;

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (response.status === 401 && !path.startsWith("/api/auth/")) {
    refresh ??= fetch("/api/auth/refresh", { method: "POST", credentials: "include" })
      .then((result) => result.ok)
      .finally(() => {
        refresh = null;
      });
    if (await refresh) return api<T>(path, init);
    throw new ApiError(401, "Sign in required");
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "Request failed";
    throw new ApiError(response.status, detail);
  }
  return payload as T;
}
