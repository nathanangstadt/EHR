const RAW_API_BASE = (import.meta as any)?.env?.VITE_API_BASE ?? "";
export const API_BASE = typeof RAW_API_BASE === "string" ? RAW_API_BASE.replace(/\/$/, "") : "";

export async function apiFetch(
  path: string,
  opts: RequestInit & { correlationId?: string } = {},
) {
  const headers = new Headers(opts.headers);
  if (!headers.has("Content-Type") && opts.body) headers.set("Content-Type", "application/json");
  if (opts.correlationId) headers.set("X-Correlation-Id", opts.correlationId);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  } catch (e: any) {
    throw new Error(`Network error calling ${API_BASE || "(same-origin)"}${path}: ${e?.message ?? String(e)}`);
  }
  const text = await res.text();
  let json: any = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { raw: text };
  }
  if (!res.ok) {
    const msg = json?.detail ? JSON.stringify(json.detail) : JSON.stringify(json);
    throw new Error(`${res.status} ${res.statusText}: ${msg}`);
  }
  return json;
}
