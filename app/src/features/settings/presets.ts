// 常用供应商 (PLAN 15.4.10, after CC Switch's presets): the buttons at the top of the profile
// editor. Official platforms only, no referral links. Addresses, protocols, models and key pages
// were checked against each platform's own docs (and models.dev) on 2026-09-27.
import type { ModelProfile } from "../../shared/api";

export interface Preset {
  label: string;
  kind: ModelProfile["kind"];
  base_url?: string;
  protocol?: ModelProfile["protocol"];
  model?: string;
  /** The platform's API key page, opened from 「获取 API Key ↗」. */
  key_url?: string;
}

export const PRESETS: Preset[] = [
  { label: "DeepSeek", kind: "deepseek", key_url: "https://platform.deepseek.com/api_keys" },
  { label: "智谱", kind: "zhipu", key_url: "https://bigmodel.cn/usercenter/proj-mgmt/apikeys" },
  {
    label: "Kimi", kind: "custom", base_url: "https://api.moonshot.cn/v1", protocol: "openai", model: "kimi-k3",
    key_url: "https://platform.kimi.com/console/api-keys",
  },
  {
    label: "通义千问", kind: "custom", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", protocol: "openai",
    model: "qwen3.8-max", key_url: "https://bailian.console.aliyun.com/cn-beijing/model/settings/api-key",
  },
  {
    label: "MiniMax", kind: "custom", base_url: "https://api.minimax.cn/anthropic", protocol: "anthropic", model: "MiniMax-M3",
    key_url: "https://platform.minimax.cn/user-center/basic-information/interface-key",
  },
  {
    label: "豆包（火山方舟）", kind: "custom", base_url: "https://ark.cn-beijing.volces.com/api/v3", protocol: "openai",
    model: "doubao-seed-2-1-pro-260628", key_url: "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey",
  },
  {
    label: "硅基流动", kind: "custom", base_url: "https://api.siliconflow.cn/v1", protocol: "openai",
    model: "deepseek-ai/DeepSeek-V4-Flash", key_url: "https://cloud.siliconflow.cn/account/ak",
  },
  {
    label: "OpenRouter", kind: "custom", base_url: "https://openrouter.ai/api/v1", protocol: "openai",
    model: "anthropic/claude-sonnet-5", key_url: "https://openrouter.ai/settings/keys",
  },
  {
    // Anthropic suggests claude-opus-5-5, but the bundled Pi does not know it yet and would send it
    // budget thinking, which it refuses; claude-sonnet-5 is in Pi's catalogue with adaptive thinking.
    label: "Anthropic", kind: "custom", base_url: "https://api.anthropic.com", protocol: "anthropic", model: "claude-sonnet-5",
    key_url: "https://platform.claude.com/settings/keys",
  },
  {
    label: "OpenAI", kind: "custom", base_url: "https://api.openai.com/v1", protocol: "openai", model: "gpt-6-astra",
    key_url: "https://platform.openai.com/api-keys",
  },
  { label: "自定义", kind: "custom" },
];

const CUSTOM = PRESETS[PRESETS.length - 1];
const address = (url = "") => url.trim().replace(/\/+$/, "").toLowerCase();

/** The button a saved profile belongs to: its built-in kind, else the platform at its address. */
export function presetOf(profile: Pick<ModelProfile, "kind" | "base_url">): Preset {
  if (profile.kind !== "custom") return PRESETS.find((preset) => preset.kind === profile.kind) ?? CUSTOM;
  return PRESETS.find((preset) => preset.base_url && address(preset.base_url) === address(profile.base_url)) ?? CUSTOM;
}

/** What a button changes; a platform brings its own model, so the 「高级」 numbers start over. */
export function presetFields(preset: Preset): Partial<ModelProfile> {
  if (!preset.base_url) return { kind: preset.kind };
  return {
    kind: preset.kind, base_url: preset.base_url, protocol: preset.protocol, model: preset.model,
    context_window: null, max_tokens: null,
  };
}
