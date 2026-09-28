import { describe, expect, it } from "vitest";

import type { ModelInfo } from "../../shared/api";
import { THINKING, THINKING_HINT, clampThinking, thinkingLevels, thinkingOptions } from "./thinking";

const pi = (map: ModelInfo["thinking_level_map"]): ModelInfo => ({
  source: "pi",
  context_window: 1000000,
  max_tokens: 128000,
  thinking_level_map: map,
});

describe("思考强度 (PLAN 15.4.10)", () => {
  it("offers Pi's six levels, 超高 and 最高 included", () => {
    expect(THINKING.map((option) => option.label)).toEqual(["关", "低", "中", "高", "超高", "最高"]);
    expect(THINKING.map((option) => option.value)).toEqual(["off", "low", "medium", "high", "xhigh", "max"]);
  });

  it("lists all six for claude-opus-4-8, whose catalogue entry names xhigh and max", () => {
    expect(thinkingLevels(pi({ xhigh: "xhigh", max: "max" }))).toEqual(["off", "low", "medium", "high", "xhigh", "max"]);
  });

  it("leaves out the levels a model maps to null (deepseek-v4-pro)", () => {
    const levels = thinkingLevels(pi({ minimal: null, low: null, medium: null, high: "high", max: "max" }));
    expect(levels).toEqual(["off", "high", "max"]);
    expect(thinkingOptions(levels).map((option) => option.label)).toEqual(["关", "高", "最高"]);
  });

  it("offers 超高 and 最高 only when the model's map names them", () => {
    expect(thinkingLevels(pi(null))).toEqual(["off", "low", "medium", "high"]);
    expect(thinkingLevels(pi({ off: null, xhigh: null, max: "max" }))).toEqual(["low", "medium", "high", "max"]);
  });

  it("lists every level, with a hint, when Pi's catalogue does not know the model", () => {
    const fromModelsDev: ModelInfo = { source: "models.dev", context_window: 256000, max_tokens: 256000, thinking_level_map: null };
    expect(thinkingLevels(fromModelsDev)).toBeNull();
    expect(thinkingLevels(null)).toBeNull();
    expect(thinkingOptions(null).map((option) => option.label)).toEqual(["关", "低", "中", "高", "超高", "最高"]);
    expect(THINKING_HINT).toBe("超高、最高只有部分模型支持");
  });

  it("moves a level the model lacks to the one Pi would use, trying higher levels first", () => {
    expect(clampThinking("medium", ["off", "high", "max"])).toBe("high");
    expect(clampThinking("max", ["off", "low", "medium", "high"])).toBe("high");
    expect(clampThinking("off", ["low", "high", "max"])).toBe("low");
    expect(clampThinking("medium", ["off", "low", "medium", "high"])).toBe("medium");
    expect(clampThinking("xhigh", null)).toBe("xhigh");
  });
});
