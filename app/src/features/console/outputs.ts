// Which parts a video gets (PLAN 15.4.15): the report, the subtitles, the mind map. The mind map is drawn from
// the report's chapters, so it comes with the report; at least one part is always made.
import type { Outputs } from "../../shared/api";

export type { Outputs };
type Storage = { getItem(key: string): string | null; setItem(key: string, value: string): void };

export const ALL: Outputs = { report: true, subtitles: true, mindmap: true };
const KEY = "prometheus.outputs";

export function toggleOutput(outputs: Outputs, key: keyof Outputs): Outputs {
  const next = { ...outputs, [key]: !outputs[key] };
  if (key === "mindmap" && next.mindmap) next.report = true;
  if (key === "report" && !next.report) next.mindmap = false;
  return next.report || next.subtitles || next.mindmap ? next : outputs;
}

export function loadOutputs(storage: Storage): Outputs {
  try {
    const saved = JSON.parse(storage.getItem(KEY) ?? "null") as Partial<Outputs> | null;
    if (!saved || typeof saved !== "object") return ALL;
    const outputs = { report: saved.report === true, subtitles: saved.subtitles === true, mindmap: saved.mindmap === true };
    if (outputs.mindmap) outputs.report = true;
    return outputs.report || outputs.subtitles ? outputs : ALL;
  } catch {
    return ALL;
  }
}

export function saveOutputs(storage: Storage, outputs: Outputs): void {
  storage.setItem(KEY, JSON.stringify(outputs));
}
