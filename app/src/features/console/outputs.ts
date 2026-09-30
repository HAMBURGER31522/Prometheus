// Which parts a video gets (PLAN 15.4.15): the report, the subtitles, the mind map.
export type Outputs = { report: boolean; subtitles: boolean; mindmap: boolean };
type Storage = { getItem(key: string): string | null; setItem(key: string, value: string): void };

export const ALL: Outputs = { report: true, subtitles: true, mindmap: true };

export function toggleOutput(outputs: Outputs, _key: keyof Outputs): Outputs {
  return outputs;
}

export function loadOutputs(_storage: Storage): Outputs {
  return ALL;
}

export function saveOutputs(_storage: Storage, _outputs: Outputs): void {}
