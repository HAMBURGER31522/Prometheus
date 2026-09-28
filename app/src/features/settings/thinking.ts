// 思考强度 (PLAN 15.4.10): Pi's levels and which of them a model supports.
import type { ModelInfo } from "../../shared/api";
import type { Option } from "../../shared/Select";

export const THINKING: Option<string>[] = [
  { value: "off", label: "关" },
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
];

export const THINKING_HINT = "";

export function thinkingLevels(_info: ModelInfo | null): string[] | null {
  return null;
}

export function thinkingOptions(_levels: string[] | null): Option<string>[] {
  return THINKING;
}

export function clampThinking(level: string, _levels: string[] | null): string {
  return level;
}
