import { describe, expect, it } from "vitest";

import { chapterAt } from "./chapters";

// backend/tests/fixtures/report.html: chapters overlap by a second.
const FIXTURE: Array<[number, number]> = [
  [0, 147], [146, 405], [404, 619], [618, 892], [891, 1131], [1130, 1484], [1483, 1548], [1547, 1788], [1787, 1877],
];

describe("the chapter of a moment (PLAN 15.4.9)", () => {
  it("a moment at a chapter's start belongs to that chapter, not the tail of the one before", () => {
    expect(chapterAt(FIXTURE, 147)).toBe(1);
    expect(chapterAt(FIXTURE, 892)).toBe(4);
    expect(chapterAt(FIXTURE, 0)).toBe(0);
  });

  it("an overview chapter does not take the moments of the chapters it spans", () => {
    const ranges: Array<[number, number] | null> = [[135, 520], [20, 180], [180, 301], null];
    expect(chapterAt(ranges, 160)).toBe(1);
    expect(chapterAt(ranges, 200)).toBe(2);
    expect(chapterAt(ranges, 400)).toBe(0);
  });

  it("outside every chapter: the one that started last, or the first one just ahead", () => {
    expect(chapterAt(FIXTURE, 5000)).toBe(8);
    expect(chapterAt([[10, 20]], 7)).toBe(0);
    expect(chapterAt([[10, 20]], 1)).toBeNull();
  });
});
