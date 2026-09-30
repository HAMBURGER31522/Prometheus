// 「获取模型列表」 (PLAN 15.4.8): an endpoint that answers with no models says so (user 2026-09-30:
// justwoker's list showed nothing and looked like a failure).
import { describe, expect, it } from "vitest";

import { listNote } from "./modelList";

describe("listNote", () => {
  it("tells the user an empty list is the endpoint's, and that the name can be typed", () => {
    expect(listNote([])).toBe("接口没有返回任何模型（有的中转不提供模型列表），可以直接填写模型名。");
    expect(listNote(["claude-opus-4-8"])).toBe("");
  });
});
