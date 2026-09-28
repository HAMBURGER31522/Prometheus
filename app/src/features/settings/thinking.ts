// 思考强度 (PLAN 15.4.10): Pi's six levels, and which of them a model supports by Pi's own rule
// (getSupportedThinkingLevels / clampThinkingLevel in pi-ai, models.md 「Thinking Level Map」).
import type { ModelInfo } from "../../shared/api";
import type { Option } from "../../shared/Select";

export const THINKING: Option<string>[] = [
  { value: "off", label: "关" },
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "xhigh", label: "超高" },
  { value: "max", label: "最高" },
];

export const THINKING_HINT = "超高、最高只有部分模型支持";

const ORDER = THINKING.map((option) => option.value);

/** The levels Pi runs a model it knows with; null when its catalogue does not know the model.
 *  Levels up to 高 count unless mapped to null; 超高 and 最高 only when the map names them. */
export function thinkingLevels(info: ModelInfo | null): string[] | null {
  if (info?.source !== "pi") return null;
  const map = info.thinking_level_map ?? {};
  return ORDER.filter((level) => {
    const mapped = map[level];
    if (mapped === null) return false;
    return level === "xhigh" || level === "max" ? typeof mapped === "string" : true;
  });
}

export const thinkingOptions = (levels: string[] | null) =>
  levels ? THINKING.filter((option) => levels.includes(option.value)) : THINKING;

/** A level the model lacks becomes the one Pi would use: the next higher one, else the next lower. */
export function clampThinking(level: string, levels: string[] | null): string {
  if (!levels?.length || levels.includes(level)) return level;
  const at = Math.max(0, ORDER.indexOf(level));
  const higher = ORDER.slice(at).find((candidate) => levels.includes(candidate));
  return higher ?? ORDER.slice(0, at).reverse().find((candidate) => levels.includes(candidate)) ?? levels[0];
}
