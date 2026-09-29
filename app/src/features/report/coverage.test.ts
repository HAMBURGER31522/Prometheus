import { describe, expect, it } from "vitest";

import { type Coverage } from "../../shared/api";
import { coverageLabel } from "./coverage";

const COVERAGE: Coverage = {
  points_total: 12,
  written: 10,
  skipped: [{ id: "K012", reason: "广告推广", text: "课程优惠", start_ms: 600_000, end_ms: 610_000 }],
  uncovered: [{ id: "K005", text: "第二次注水的时机", start_ms: 125_000, end_ms: 130_000 }],
};

describe("要点覆盖 (PLAN 15.4.11)", () => {
  it("counts the written points against those not legally skipped", () => {
    expect(coverageLabel(COVERAGE)).toBe("要点 10/11");
  });

  it("everything written reads as full", () => {
    expect(coverageLabel({ ...COVERAGE, written: 11, uncovered: [] })).toBe("要点 11/11");
  });
});
