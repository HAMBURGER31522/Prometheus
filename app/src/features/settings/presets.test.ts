import { describe, expect, it } from "vitest";

import { PRESETS, presetFields, presetOf } from "./presets";

const byLabel = (label: string) => PRESETS.find((preset) => preset.label === label) ?? PRESETS[0];

describe("常用供应商 (PLAN 15.4.10)", () => {
  it("offers the eleven buttons in order", () => {
    expect(PRESETS.map((preset) => preset.label)).toEqual([
      "DeepSeek", "智谱", "Kimi", "通义千问", "MiniMax", "豆包（火山方舟）", "硅基流动", "OpenRouter", "Anthropic", "OpenAI", "自定义",
    ]);
  });

  it("fills a platform's address, protocol and recommended model; DeepSeek and 智谱 stay built in", () => {
    expect(presetFields(byLabel("Kimi"))).toEqual({
      kind: "custom", base_url: "https://api.moonshot.cn/v1", protocol: "openai", model: "kimi-k3",
      context_window: null, max_tokens: null,
    });
    expect(presetFields(byLabel("MiniMax"))).toMatchObject({ base_url: "https://api.minimax.cn/anthropic", protocol: "anthropic" });
    expect(presetFields(byLabel("DeepSeek"))).toEqual({ kind: "deepseek" });
    expect(presetFields(byLabel("自定义"))).toEqual({ kind: "custom" });
  });

  it("gives every platform an https address, a model and its official key page, never a referral link", () => {
    const platforms = PRESETS.filter((preset) => preset.base_url);
    expect(platforms).toHaveLength(8);
    for (const preset of platforms) {
      expect(preset.base_url).toMatch(/^https:\/\/[^/]+/);
      expect(preset.key_url).toMatch(/^https:\/\/[^/]+/);
      expect(preset.model).toBeTruthy();
      expect(`${preset.base_url} ${preset.key_url}`).not.toMatch(/aff=|invite|utm_|[?&]ref=|\/i\//i);
    }
  });

  it("recognises a saved profile's platform by its address", () => {
    expect(presetOf({ kind: "custom", base_url: "https://api.moonshot.cn/v1/" }).label).toBe("Kimi");
    expect(presetOf({ kind: "custom", base_url: "https://api.justwoker.icu/v1" }).label).toBe("自定义");
    expect(presetOf({ kind: "zhipu", base_url: "" }).label).toBe("智谱");
  });
});
