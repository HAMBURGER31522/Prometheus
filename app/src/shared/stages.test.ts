import { describe, expect, it } from "vitest";

import { STAGES, stageText, stepOf } from "./stages";

describe("console stages (PLAN 15.4.11)", () => {
  it("提取要点 and 规划 come right before the report", () => {
    const ids = STAGES.map(([id]) => id);
    const at = ids.indexOf("report");
    expect(ids.slice(at - 2, at)).toEqual(["keypoints", "plan"]);
    expect(STAGES[at - 2][1]).toBe("提取要点");
    expect(STAGES[at - 1][1]).toBe("规划");
  });

  it("a long stage says where it is, e.g. which chapter is being written", () => {
    expect(stageText({ stage: "report", stage_detail: "写作（第 3/10 章）" })).toBe("写作（第 3/10 章）");
    expect(stageText({ stage: "report", stage_detail: null })).toBe("写精读报告");
    expect(stageText({ stage: null, stage_detail: null })).toBe("准备中");
  });
});

describe("the steps a video runs (PLAN 15.4.15)", () => {
  const SUBTITLES_ONLY = ["resolve", "download", "transcribe", "transcript", "subtitle_fix", "classify", "publish"];

  it("the console counts only the steps this video runs", () => {
    expect(stepOf({ stage: "subtitle_fix", stages: SUBTITLES_ONLY })).toEqual({ index: 4, total: 7 });
    expect(stepOf({ stage: "report", stages: undefined })).toEqual({ index: 7, total: 13 }); // a row that does not say
  });

  it("「现在生成」 with figures first downloads only the picture", () => {
    expect(stageText({ stage: "video", stage_detail: null })).toBe("下载画面");
    expect(stageText({ stage: "subtitle_fix", stage_detail: "排队中" })).toBe("排队中");
  });
});
