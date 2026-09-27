import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { watchScrollIdle } from "./scrollIdle";

describe("floating scrollbar idle rule (PLAN 15.4.5)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows while scrolling and fades 800 ms after the last scroll", () => {
    const el = document.createElement("div");
    watchScrollIdle(el);
    expect(el.hasAttribute("data-scrolling")).toBe(false);
    el.dispatchEvent(new Event("scroll"));
    expect(el.hasAttribute("data-scrolling")).toBe(true);
    vi.advanceTimersByTime(500);
    el.dispatchEvent(new Event("scroll"));
    vi.advanceTimersByTime(799);
    expect(el.hasAttribute("data-scrolling")).toBe(true);
    vi.advanceTimersByTime(1);
    expect(el.hasAttribute("data-scrolling")).toBe(false);
  });

  it("stops watching after cleanup", () => {
    const el = document.createElement("div");
    const stop = watchScrollIdle(el);
    stop();
    el.dispatchEvent(new Event("scroll"));
    expect(el.hasAttribute("data-scrolling")).toBe(false);
  });
});
