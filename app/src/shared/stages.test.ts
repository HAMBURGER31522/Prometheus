import { describe, expect, it } from "vitest";

import { STAGES, stageText } from "./stages";

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
