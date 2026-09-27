import { describe, expect, it } from "vitest";

import { DICTIONARIES, isForeign, tokenize } from "./words";

describe("hover lookup words (PLAN 15.4.9)", () => {
  it("splits a line into words and the text between them, keeping every character", () => {
    const tokens = tokenize("It's a well-known fact, 100%.");
    expect(tokens.filter((token) => token.word).map((token) => token.word)).toEqual(["It's", "a", "well-known", "fact"]);
    expect(tokens.map((token) => token.text).join("")).toBe("It's a well-known fact, 100%.");
  });

  it("looks words up only in lines that are mostly Latin letters", () => {
    expect(isForeign("Imagine the money a country earns")).toBe(true);
    expect(isForeign("我们用 LLM 做字幕")).toBe(false);
    expect(isForeign("")).toBe(false);
  });

  it("offers 有道、剑桥、柯林斯、必应、韦氏 with the word in the address", () => {
    expect(DICTIONARIES.map((dictionary) => dictionary.name)).toEqual(["有道", "剑桥", "柯林斯", "必应", "韦氏"]);
    for (const dictionary of DICTIONARIES) {
      const url = new URL(dictionary.url("well-known"));
      expect(url.protocol).toBe("https:");
      expect(decodeURIComponent(url.href)).toContain("well-known");
    }
  });
});
