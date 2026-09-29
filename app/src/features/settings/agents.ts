import type { ModelProfile } from "../../shared/api";
import type { Option } from "../../shared/Select";
import type { Preset } from "./presets";

export const AGENTS: Option<ModelProfile["agent"]>[] = [];

export function agentProblem(_profile: ModelProfile): string | null {
  return null;
}

export function presetAllowed(_preset: Preset, _agent: ModelProfile["agent"]): boolean {
  return true;
}

export function agentThinking(_agent: ModelProfile["agent"]): { unavailable: string[]; note: string | null } {
  return { unavailable: [], note: null };
}
