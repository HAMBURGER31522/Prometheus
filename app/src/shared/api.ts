// Backend client (PLAN 8.2): http://127.0.0.1:<port> with the bearer token from the shell.

import { backendInfo } from "./platform";

let endpointPromise: Promise<{ base: string; token: string }> | null = null;

function endpoint() {
  endpointPromise ??= backendInfo().then((info) => ({ base: `http://127.0.0.1:${info.port}`, token: info.token }));
  return endpointPromise;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  /** The JSON error body, e.g. 「获取模型列表」's status and reason (PLAN 15.4.10). */
  body?: Record<string, unknown>;
  constructor(status: number, code?: string, body?: Record<string, unknown>) {
    super(code ?? `HTTP ${status}`);
    this.status = status;
    this.code = code;
    this.body = body;
  }
}

async function send(method: string, path: string, body?: unknown): Promise<Response> {
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
    let detail: Record<string, unknown> | undefined;
    try {
      detail = await response.json();
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail?.code as string | undefined, detail);
  }
  return response;
}

async function json<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await send(method, path, body);
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const text = async (path: string) => (await send("GET", path)).text();

export const api = {
  settings: () => json<Settings>("GET", "/api/settings"),
  saveSettings: (settings: Settings) => json<Settings>("PUT", "/api/settings", settings),
  testModel: () => json<{ ok: boolean; detail: string }>("POST", "/api/settings/test-model"),
  /** The eye on a key field (PLAN 15.4.10): a profile's saved key, or the custom transcription key. */
  revealKey: async (target: { profile_id: string } | { target: "asr" }) =>
    (await json<{ api_key: string }>("POST", "/api/settings/reveal-key", target)).api_key,
  listModels: async (profile: ModelProfile) =>
    (await json<{ models: string[] }>("POST", "/api/settings/models", { profile })).models,
  /** The model catalogue fetched from pi.dev (PLAN 15.4.12): when, and 「更新模型目录」. */
  modelCatalogue: () => json<{ updated_at: string | null }>("GET", "/api/settings/model-catalogue"),
  refreshModelCatalogue: () =>
    json<{ updated_at: string | null; providers: number; failed: string[] }>("POST", "/api/settings/model-catalogue/refresh"),
  modelInfo: (profile: Pick<ModelProfile, "kind" | "model" | "protocol" | "base_url">) =>
    json<ModelInfo>("POST", "/api/settings/model-info", { profile }),
  installAsr: () => json<{ started: boolean }>("POST", "/api/asr-components/install"),
  lookupWord: (word: string) => json<LookupEntry>("GET", `/api/dictionary/lookup?word=${encodeURIComponent(word)}`),
  dictionaryStatus: () => json<ComponentStatus>("GET", "/api/dictionary"),
  installDictionary: () => json<{ started: boolean }>("POST", "/api/dictionary/install"),
  asrStatus: () => json<{ state: string; detail: string }>("GET", "/api/asr-components"),
  dataDir: () => json<{ data_dir: string | null }>("GET", "/api/app/data-dir"),
  setDataDir: (dataDir: string) => json<{ data_dir: string }>("PUT", "/api/app/data-dir", { data_dir: dataDir }),

  addItem: (url: string, figures: boolean) => json<{ id: string }>("POST", "/api/items", { url, figures }),
  items: () => json<ItemRow[]>("GET", "/api/items"),
  item: (id: string) => json<ItemRow>("GET", `/api/items/${id}`),
  moveItem: (id: string, categoryId: number) => json<ItemRow>("PATCH", `/api/items/${id}`, { category_id: categoryId }),
  deleteItem: (id: string) => json<void>("DELETE", `/api/items/${id}`),
  cancelItem: (id: string) => json<{ cancelled: boolean }>("POST", `/api/items/${id}/cancel`),
  retryItem: (id: string) => json<{ queued: boolean }>("POST", `/api/items/${id}/retry`),
  regenerate: (id: string, figures?: boolean) =>
    json<{ queued: boolean }>("POST", `/api/items/${id}/regenerate`, figures === undefined ? {} : { figures }),
  regenerateMindmap: (id: string) =>
    json<{ queued: boolean }>("POST", `/api/items/${id}/regenerate`, { only: "mindmap" }),
  /** 「补全标签和摘要」(PLAN 15.4.10): classify + publish again, the category stays. */
  fillTags: (id: string) => json<{ queued: boolean }>("POST", `/api/items/${id}/regenerate`, { only: "tags" }),
  queue: () => json<ItemRow[]>("GET", "/api/queue"),

  categories: () => json<CategoryRow[]>("GET", "/api/categories"),
  renameCategory: (id: number, name: string) => json<unknown>("PATCH", `/api/categories/${id}`, { name }),
  createCategory: (name: string) => json<CategoryRow>("POST", "/api/categories", { name }),
  deleteCategory: (id: number, moveItems = false) =>
    json<void>("DELETE", `/api/categories/${id}${moveItems ? "?move_items=1" : ""}`),
  mergeCategory: (id: number, intoId: number) =>
    json<unknown>("POST", `/api/categories/${id}/merge`, { into_id: intoId }),

  reportHtml: (id: string) => text(`/api/items/${id}/report`),
  coverage: (id: string) => json<Coverage>("GET", `/api/items/${id}/coverage`),
  mindmapTree: (id: string) => json<MindmapTree>("GET", `/api/items/${id}/mindmap?format=json`),
  mindmapMarkdown: (id: string) => text(`/api/items/${id}/mindmap`),
  subtitle: (id: string, variant: "fixed" | "raw") =>
    json<Segment[]>("GET", `/api/items/${id}/subtitle?variant=${variant}`),
  subtitleText: (id: string, format: "srt" | "txt", variant: "fixed" | "raw") =>
    text(`/api/items/${id}/subtitle?format=${format}&variant=${variant}`),
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
  figures: number;
  status: "queued" | "running" | "done" | "failed" | "cancelled" | "interrupted";
  stage: string | null;
  /** Where a long stage is, e.g. 「写作（第 3/10 章）」 (PLAN 15.4.11). */
  stage_detail: string | null;
  mindmap_status: "ok" | "failed" | null;
  subtitle_status: "ok" | "failed" | null;
  error_code: string | null;
  error_message: string | null;
  /** Why it failed and what to do (PLAN 15.4.10); null for rows that failed before that. */
  error_reason: string | null;
  error_action: string | null;
  created_at: string;
  finished_at: string | null;
  library_path: string | null;
  tags: string | null;
  description: string | null;
  transcript_source: string | null;
  notice: string | null;
  files_missing: boolean;
}

export interface CategoryRow {
  id: number;
  name: string;
  count: number;
}

/** An offline dictionary entry (PLAN 15.4.9): `headword` is the lemma when `query` is inflected. */
export interface LookupEntry {
  query: string;
  headword: string;
  phonetic: string;
  translation: string[];
  inflection: string | null;
  /** Up to three English definitions (PLAN 15.4.10). */
  definition: string[];
  /** The installed dictionary predates English definitions: 「更新词库」 downloads it again. */
  needs_update: boolean;
}

export interface ComponentStatus {
  state: "idle" | "installing" | "ready" | "failed";
  detail: string;
  progress: number | null;
}

export interface Segment {
  start: number;
  end: number;
  text: string;
  /** Chinese translation of a non-Chinese transcript (PLAN 15.4.9). */
  zh?: string;
}

export interface MindmapTree {
  title: string;
  root: import("../features/mindmap/layout").TreeNode;
}

export interface ModelProfile {
  id: string;
  name: string;
  kind: "deepseek" | "zhipu" | "custom";
  base_url: string;
  protocol: "openai" | "anthropic";
  api_key: string;
  model: string;
  supports_images: boolean;
  thinking: string;
  /** 「高级」 (PLAN 15.4.10): the user's own numbers; null = what the catalogues say. */
  context_window: number | null;
  max_tokens: number | null;
}

/** What Pi's bundled catalogue (source "pi") or the models.dev snapshot knows about a profile's model (PLAN 15.4.10). */
export interface ModelInfo {
  source: "pi" | "models.dev" | null;
  context_window: number | null;
  max_tokens: number | null;
  thinking_level_map: Record<string, string | null> | null;
}

export interface Settings {
  /** The saved model profiles (PLAN 15.4.8); `llm` is the active one, derived by the backend. */
  llm_profiles: { active: string; items: ModelProfile[] };
  llm: {
    provider: string;
    model: string;
    api_key: string;
    thinking: string;
    custom: { base_url: string; supports_images: boolean; protocol: "openai" | "anthropic" };
  };
  /** 本地 / 云端（必剪）/ 自定义（OpenAI 兼容，PLAN 15.4.9）. */
  asr: { backend: "local" | "cloud" | "custom"; custom: { base_url: string; api_key: string; model: string } };
  network: { proxy: string; youtube_cookies_file: string };
  figures_default: boolean;
  /** 精读详细程度 (PLAN 15.4.11): full = 完整, standard = VRA as it was; review = 讲清楚审校 in 完整. */
  report: { depth: "full" | "standard"; review: boolean };
}

/** coverage.json of a 完整 report (PLAN 15.4.11): what was written, skipped with a reason, or left out. */
export interface CoveragePoint {
  id: string;
  text: string;
  start_ms: number;
  end_ms: number;
}
export interface Coverage {
  points_total: number;
  written: number;
  skipped: (CoveragePoint & { reason: string; duplicate_of?: string })[];
  uncovered: CoveragePoint[];
}

export const itemTitle = (item: ItemRow) => item.report_title || item.source_title || item.video_id;

export const itemTags = (item: ItemRow): string[] => {
  try {
    return item.tags ? (JSON.parse(item.tags) as string[]) : [];
  } catch {
    return [];
  }
};
