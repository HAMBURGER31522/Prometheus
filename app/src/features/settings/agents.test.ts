// PLAN 15.4.13: what each Agent takes — protocol, presets, access, thinking levels.
import { describe, expect, it } from "vitest";

import type { ModelProfile } from "../../shared/api";
import { AGENTS, agentProblem, agentThinking, presetAllowed } from "./agents";
import { PRESETS } from "./presets";

const profile = (fields: Partial<ModelProfile>): ModelProfile => ({
  id: "p", name: "", kind: "custom", base_url: "https://relay.example/v1", protocol: "openai", api_key: "", model: "m",
  supports_images: false, thinking: "medium", context_window: null, max_tokens: null, agent: "pi", access: "key",
  ...fields,
});

describe("agents", () => {
  it("lists Pi, Codex CLI and Claude Code", () => {
    expect(AGENTS.map((agent) => agent.label)).toEqual(["Pi", "Codex CLI", "Claude Code"]);
    expect(AGENTS.map((agent) => agent.value)).toEqual(["pi", "codex", "claude"]);
  });

  it("names the mismatch the backend would refuse", () => {
    expect(agentProblem(profile({ agent: "claude", protocol: "openai" }))).toBe("Claude Code 只接 Anthropic 协议");
    expect(agentProblem(profile({ agent: "codex", protocol: "anthropic" }))).toBe("Codex CLI 只接 OpenAI 协议");
    expect(agentProblem(profile({ agent: "claude", kind: "deepseek", protocol: "anthropic" }))).toBe(
      "Claude Code 要填自己的接口地址：选下面列出的平台或「自定义」",
    );
    expect(agentProblem(profile({ agent: "pi", access: "login" }))).toBe("只有 Codex CLI 能用官方登录");
    expect(agentProblem(profile({ agent: "claude", protocol: "anthropic" }))).toBeNull();
    expect(agentProblem(profile({ agent: "codex", access: "login", base_url: "", protocol: "anthropic" }))).toBeNull();
    expect(agentProblem(profile({ agent: "pi", kind: "deepseek" }))).toBeNull();
  });

  it("keeps the platforms whose protocol the Agent takes", () => {
    const allowed = (agent: ModelProfile["agent"]) =>
      PRESETS.filter((preset) => presetAllowed(preset, agent)).map((preset) => preset.label);
    expect(allowed("pi")).toEqual(PRESETS.map((preset) => preset.label));
    expect(allowed("claude")).toEqual(["MiniMax", "Anthropic", "自定义"]);
    expect(allowed("codex")).toEqual(["Kimi", "通义千问", "豆包（火山方舟）", "硅基流动", "OpenRouter", "OpenAI", "自定义"]);
  });

  it("greys out the thinking levels an Agent cannot send, and says why", () => {
    expect(agentThinking("claude")).toEqual({ unavailable: ["off"], note: "Claude Code 没有「关」这一档，最低是「低」" });
    expect(agentThinking("codex")).toEqual({ unavailable: [], note: null });
    expect(agentThinking("pi")).toEqual({ unavailable: [], note: null });
  });
});
