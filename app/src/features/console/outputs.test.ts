// PLAN 15.4.15: which parts a video gets — the report, the subtitles, the mind map (bound to the report).
import { describe, expect, it } from "vitest";

import { ALL, loadOutputs, saveOutputs, toggleOutput } from "./outputs";

const memory = () => {
  const store = new Map<string, string>();
  return { getItem: (key: string) => store.get(key) ?? null, setItem: (key: string, value: string) => store.set(key, value) };
};

describe("the three circles", () => {
  it("start with all three", () => {
    expect(ALL).toEqual({ report: true, subtitles: true, mindmap: true });
  });

  it("tie the mind map to the report", () => {
    const none = { report: false, subtitles: true, mindmap: false };
    expect(toggleOutput(none, "mindmap")).toEqual({ report: true, subtitles: true, mindmap: true });
    expect(toggleOutput(ALL, "report")).toEqual({ report: false, subtitles: true, mindmap: false });
    expect(toggleOutput(ALL, "mindmap")).toEqual({ report: true, subtitles: true, mindmap: false });
  });

  it("never leave nothing to make", () => {
    expect(toggleOutput(ALL, "subtitles")).toEqual({ report: true, subtitles: false, mindmap: true });
    const only = { report: false, subtitles: true, mindmap: false };
    expect(toggleOutput(only, "subtitles")).toEqual(only);
    const reportOnly = { report: true, subtitles: false, mindmap: false };
    expect(toggleOutput(reportOnly, "report")).toEqual(reportOnly);
  });

  it("remember the last choice, all three the first time", () => {
    const storage = memory();
    expect(loadOutputs(storage)).toEqual(ALL);
    saveOutputs(storage, { report: false, subtitles: true, mindmap: false });
    expect(loadOutputs(storage)).toEqual({ report: false, subtitles: true, mindmap: false });
    storage.setItem("prometheus.outputs", "{broken");
    expect(loadOutputs(storage)).toEqual(ALL);
  });
});
