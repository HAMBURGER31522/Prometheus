// 常用供应商 (PLAN 15.4.10): the buttons at the top of the profile editor.
import type { ModelProfile } from "../../shared/api";

export interface Preset {
  label: string;
  kind: ModelProfile["kind"];
  base_url?: string;
  protocol?: ModelProfile["protocol"];
  model?: string;
  key_url?: string;
}

export const PRESETS: Preset[] = [
  { label: "DeepSeek", kind: "deepseek" },
  { label: "智谱", kind: "zhipu" },
  { label: "自定义", kind: "custom" },
];

export function presetOf(profile: Pick<ModelProfile, "kind" | "base_url">): Preset {
  return PRESETS.find((preset) => preset.kind === profile.kind) ?? PRESETS[PRESETS.length - 1];
}

export function presetFields(preset: Preset): Partial<ModelProfile> {
  return { kind: preset.kind };
}
