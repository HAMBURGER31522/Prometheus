import { describe, expect, it } from "vitest";

import { stepZoom } from "./zoom";

describe("reading zoom (PLAN 15.4.7)", () => {
  it("steps by 10% between 80% and 160%", () => {
    expect(stepZoom(1, 1)).toBe(1.1);
    expect(stepZoom(1.1, -1)).toBe(1);
    expect(stepZoom(1.6, 1)).toBe(1.6);
    expect(stepZoom(0.8, -1)).toBe(0.8);
  });

  it("does not drift after many steps", () => {
    let zoom = 1;
    for (let i = 0; i < 5; i++) zoom = stepZoom(zoom, 1);
    expect(zoom).toBe(1.5);
  });

  it("resets to 100%", () => {
    expect(stepZoom(1.4, 0)).toBe(1);
  });
});
