// Backend client (PLAN 8.2). All requests go to http://127.0.0.1:<port> with the
// bearer token from platform.backendInfo(); content GETs also accept ?token=.

import { backendInfo } from "./platform";

let cachedBase: string | null = null;
let cachedToken: string | null = null;

async function endpoint(): Promise<{ base: string; token: string }> {
  if (cachedBase && cachedToken) return { base: cachedBase, token: cachedToken };
  const info = await backendInfo();
  cachedBase = `http://127.0.0.1:${info.port}`;
  cachedToken = info.token;
  return { base: cachedBase, token: cachedToken };
}

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, code?: string) {
    super(code ?? `HTTP ${status}`);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const { base, token } = await endpoint();
  const response = await fetch(`${base}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let code: string | undefined;
    try {
      code = (await response.json()).code;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, code);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  getSettings: () => request<Settings>("GET", "/api/settings"),
  putSettings: (settings: Settings) => request<Settings>("PUT", "/api/settings", settings),
  testModel: () => request<{ ok: boolean; detail: string }>("POST", "/api/settings/test-model"),
  installAsr: () => request<{ started: boolean }>("POST", "/api/asr-components/install"),
  asrStatus: () =>
    request<{ state: string; detail: string }>("GET", "/api/asr-components"),
  getDataDir: () => request<{ data_dir: string | null }>("GET", "/api/app/data-dir"),
  setDataDir: (data_dir: string) =>
    request<{ data_dir: string }>("PUT", "/api/app/data-dir", { data_dir }),
  postItem: (url: string, figures: boolean) =>
    request<{ id: string }>("POST", "/api/items", { url, figures }),
  getItems: (status?: string) =>
    request<ItemRow[]>("GET", `/api/items${status ? `?status=${status}` : ""}`),
  getItem: (id: string) => request<ItemRow>("GET", `/api/items/${id}`),
  deleteItem: (id: string) => request<void>("DELETE", `/api/items/${id}`),
  cancelItem: (id: string) => request<{ cancelled: boolean }>("POST", `/api/items/${id}/cancel`),
  retryItem: (id: string) => request<{ queued: boolean }>("POST", `/api/items/${id}/retry`),
  regenerate: (id: string, figures?: boolean) =>
    request<{ queued: boolean }>("POST", `/api/items/${id}/regenerate`, { figures }),
  getQueue: () => request<ItemRow[]>("GET", "/api/queue"),
  getCategories: () => request<CategoryRow[]>("GET", "/api/categories"),
  renameCategory: (id: number, name: string) =>
    request<{ renamed: boolean }>("PATCH", `/api/categories/${id}`, { name }),
  deleteCategory: (id: number) => request<void>("DELETE", `/api/categories/${id}`),
  mergeCategory: (id: number, into_id: number) =>
    request<{ merged: boolean }>("POST", `/api/categories/${id}/merge`, { into_id }),
};

export interface ItemRow {
  id: string;
  platform: string;
  video_id: string;
  source_url: string;
  source_title: string | null;
  uploader: string | null;
  duration_s: number | null;
  report_title: string | null;
  category_id: number | null;
  status: string;
  stage: string | null;
  mindmap_status: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface CategoryRow {
  id: number;
  name: string;
  count: number;
}

export interface Settings {
  llm: {
    provider: string;
    model: string;
    api_key: string;
    thinking: string;
    custom: { base_url: string; supports_images: boolean };
  };
  asr: { backend: string; dashscope_api_key: string; cloud_model: string };
  network: { proxy: string; youtube_cookies_file: string };
  figures_default: boolean;
}

export async function contentUrl(id: string, kind: "report" | "mindmap" | "subtitle", format?: string): Promise<string> {
  const { base, token } = await endpoint();
  const suffix = format ? `&format=${format}` : "";
  return `${base}/api/items/${id}/${kind}?token=${token}${suffix}`;
}
