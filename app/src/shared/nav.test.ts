import { describe, expect, it } from "vitest";

import { TABS, initialNav, navReducer } from "./nav";

describe("navigation (PLAN 15.4.5)", () => {
  it("lists the five tabs in order", () => {
    expect(TABS.map((tab) => tab.label)).toEqual(["控制台", "知识库", "思维导图", "字幕", "设置"]);
  });

  it("opening an item keeps the tab it was opened from", () => {
    const inMindmap = navReducer(initialNav, { type: "tab", tab: "mindmap" });
    const opened = navReducer(navReducer(inMindmap, { type: "category", categoryId: 3 }), {
      type: "item",
      itemId: "abc",
    });
    expect(opened).toEqual({ tab: "mindmap", categoryId: 3, itemId: "abc" });
  });

  it("switching 精读 / 导图 / 字幕 keeps the same item", () => {
    const reading = { tab: "library" as const, categoryId: 3, itemId: "abc" };
    expect(navReducer(reading, { type: "tab", tab: "subtitle" })).toEqual({ ...reading, tab: "subtitle" });
  });

  it("choosing another category closes the item", () => {
    const reading = { tab: "library" as const, categoryId: 3, itemId: "abc" };
    expect(navReducer(reading, { type: "category", categoryId: 4 })).toEqual({
      tab: "library",
      categoryId: 4,
      itemId: null,
    });
  });

  it("closing the reader goes back to the item list of the same category", () => {
    const reading = { tab: "subtitle" as const, categoryId: 3, itemId: "abc" };
    expect(navReducer(reading, { type: "close" })).toEqual({ tab: "subtitle", categoryId: 3, itemId: null });
  });

  it("「在精读中查看」 opens 精读 on the same item at a moment, and only once", () => {
    const map = { tab: "mindmap" as const, categoryId: 3, itemId: "abc" };
    const jumped = navReducer(map, { type: "tab", tab: "library", at: 892 });
    expect(jumped).toEqual({ ...map, tab: "library", at: 892 });
    expect(navReducer(jumped, { type: "tab", tab: "subtitle" }).at).toBeUndefined();
    expect(navReducer(jumped, { type: "close" }).at).toBeUndefined();
  });
});
