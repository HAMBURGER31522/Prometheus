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

  it("offers 有道、剑桥、柯林斯、必应、韦氏、牛津、欧路 with the word in the address", () => {
    expect(DICTIONARIES.map((dictionary) => dictionary.name)).toEqual(["有道", "剑桥", "柯林斯", "必应", "韦氏", "牛津", "欧路"]);
    for (const dictionary of DICTIONARIES) {
      const url = new URL(dictionary.url("well-known"));
      expect(url.protocol).toBe("https:");
      expect(decodeURIComponent(url.href)).toContain("well-known");
    }
  });

  it("opens 牛津 through its search (which finds went, Sitting, well-known) and 欧路 at the word's page", () => {
    // Both checked on the live sites on 2026-09-27 (PLAN 15.4.10).
    const address = (name: string) => DICTIONARIES.find((dictionary) => dictionary.name === name)?.url("sitting");
    expect(address("牛津")).toBe("https://www.oxfordlearnersdictionaries.com/search/english/?q=sitting");
    expect(address("欧路")).toBe("https://dict.eudic.net/dicts/en/sitting");
  });
});
