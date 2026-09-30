// 设置 · 模型 · Agent (PLAN 15.4.13): which Agent runs a profile and what it takes. The backend
// refuses the same combinations (backend/src/prometheus/agents/rules.py); the page says why first.
import type { AgentId, ModelInfo, ModelProfile } from "../../shared/api";
import type { Option } from "../../shared/Select";
import type { Preset } from "./presets";

export const AGENTS: Option<AgentId>[] = [
  { value: "pi", label: "Pi" },
  { value: "codex", label: "Codex CLI" },
  { value: "claude", label: "Claude Code" },
];

const NAMES: Record<AgentId, string> = { pi: "Pi", codex: "Codex CLI", claude: "Claude Code" };

/** The one protocol an Agent speaks; Pi speaks both. */
export const AGENT_PROTOCOL: Record<AgentId, ModelProfile["protocol"] | null> = {
  pi: null, codex: "openai", claude: "anthropic",
};

const PROTOCOL_NAMES: Record<ModelProfile["protocol"], string> = { openai: "OpenAI", anthropic: "Anthropic" };

/** Why the backend would refuse this profile, in words; null when it can be saved. */
export function agentProblem(profile: ModelProfile): string | null {
  const { agent, access } = profile;
  if (access === "login" && agent !== "codex") return "只有 Codex CLI 能用官方登录";
  if (agent === "pi" || access === "login") return null;
  if (profile.kind !== "custom") return `${NAMES[agent]} 要填自己的接口地址：选下面列出的平台或「自定义」`;
  const protocol = AGENT_PROTOCOL[agent];
  if (protocol && profile.protocol !== protocol) return `${NAMES[agent]} 只接 ${PROTOCOL_NAMES[protocol]} 协议`;
  return null;
}

/** A platform button stays clickable when the Agent can reach it: Pi's built-in kinds only on Pi. */
export function presetAllowed(preset: Preset, agent: AgentId): boolean {
  if (agent === "pi") return true;
  if (preset.kind !== "custom") return false;
  return !preset.base_url || preset.protocol === AGENT_PROTOCOL[agent];
}

/** Levels an Agent cannot send at all: Claude Code's --effort starts at low. */
export function agentThinking(agent: AgentId): { unavailable: string[]; note: string | null } {
  if (agent === "claude") return { unavailable: ["off"], note: "Claude Code 没有「关」这一档，最低是「低」" };
  return { unavailable: [], note: null };
}

/** What the 「高级」 boxes hold, or what an empty box means, for each Agent (PLAN 15.4.13). */
export function limitHint(info: ModelInfo | null, agent: AgentId): string {
  if (info?.source === "pi") return "按随包 Pi 的模型目录预填，可以手动改。";
  if (info?.source === "models.dev") return "按 models.dev 的数据预填，可以手动改。";
  if (info?.source === "codex" && info.context_window) return "按模型目录预填，可以手动改；思考档位按 Codex 自己的列表。";
  if (agent === "codex") return "目录里没有这个模型：留空时 Codex CLI 用它自己的默认；接口的上限更小时请填上。";
  if (agent === "claude") {
    return "目录里查不到这个模型名，应用不知道它的上限。留空时 Claude Code 按 200k 跑；如果它是 1M 的，在这里填 1000000，应用会自动加上「[1m]」。";
  }
  return "目录里没有这个模型：留空就按 Pi 的默认（上下文 128000，输出 16384）。";
}
