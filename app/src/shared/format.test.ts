import { describe, expect, it } from "vitest";

import { clock, duration, momentLink, sourceLabel } from "./format";

describe("formatting", () => {
  it("subtitle clocks are always HH:MM:SS", () => {
    expect(clock(0)).toBe("00:00:00");
    expect(clock(83.9)).toBe("00:01:23");
    expect(clock(3 * 3600 + 5)).toBe("03:00:05");
  });

  it("durations drop the hour when there is none", () => {
    expect(duration(777.9)).toBe("12:57");
    expect(duration(6240)).toBe("1:44:00");
    expect(duration(null)).toBe("");
  });

  it("moment links match the backend's (mindmap/markdown.py)", () => {
    expect(momentLink("bilibili", "BV1yPb46xExH", 125.7)).toBe("https://www.bilibili.com/video/BV1yPb46xExH/?p=1&t=125");
    expect(momentLink("bilibili", "BV1yPb46xExH?p=3", 10)).toBe("https://www.bilibili.com/video/BV1yPb46xExH/?p=3&t=10");
    expect(momentLink("youtube", "BHY0FxzoKZE", 61)).toBe("https://www.youtube.com/watch?v=BHY0FxzoKZE&t=61s");
  });

  it("names where the transcript came from", () => {
    expect(sourceLabel("youtube-subtitles")).toBe("YouTube 人工字幕");
    expect(sourceLabel("bcut")).toBe("必剪");
    expect(sourceLabel("funasr-onnx")).toBe("FunASR");
    expect(sourceLabel("faster-whisper")).toBe("Whisper");
    expect(sourceLabel(null)).toBe("");
  });
});
