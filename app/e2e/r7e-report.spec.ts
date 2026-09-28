// E14 (PLAN 15.4.11): the reader shows 「要点 10/11」; the list names what was skipped and why and what
// was left out, with times, and a line opens the video at that moment.
import { expect, test } from "@playwright/test";

import { openFirstItem, openTab, report, seed } from "./helpers";

const lastOpened = (page: import("@playwright/test").Page) =>
  page.evaluate(() => (window as unknown as { __lastOpenedExternal?: string }).__lastOpenedExternal);

test.beforeAll(async ({ request }) => {
  await seed(request);
});

test("精读工具栏显示要点覆盖，点开是跳过和未写到的清单，点一条跳到视频的那一刻", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  await expect(report(page).locator("h1")).toBeVisible();
  await page.getByRole("button", { name: "要点 10/11" }).click();
  const list = page.getByRole("dialog", { name: "要点覆盖" });
  await expect(list).toContainText("跳过 1 条");
  await expect(list).toContainText("广告推广");
  await expect(list).toContainText("未写到 1 条");
  await expect(list).toContainText("第二次注水的时机");
  await list.getByRole("button", { name: /02:05/ }).click();
  await expect.poll(() => lastOpened(page)).toContain("t=125");
});
