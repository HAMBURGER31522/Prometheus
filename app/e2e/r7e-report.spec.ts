// E14 (PLAN 15.4.11): the reader shows 「要点 10/11」; the list names what was skipped and why and what
// was left out, with times, and a line opens the video at that moment.
import { expect, test } from "@playwright/test";

import { inReport, openFirstItem, openTab, report, seed } from "./helpers";

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

test("大图可以左右切换（按钮和 ← → 键），显示「第几张 / 共几张」和图注，到头不循环；模型画的图示也能点开", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  await expect(report(page).locator("figure img")).toBeVisible();
  // The sample report has one picture: add a second one and a drawn diagram after it.
  await inReport(page, () => {
    const figure = document.querySelector("figure") as HTMLElement;
    const second = figure.cloneNode(true) as HTMLElement;
    (second.querySelector("figcaption") as HTMLElement).textContent = "第二张图注";
    figure.after(second);
    const diagram = document.createElement("figure");
    diagram.innerHTML =
      '<svg viewBox="0 0 400 200" width="400" height="200"><rect x="10" y="10" width="380" height="180" fill="none" stroke="currentColor"/><text x="200" y="100">关系图</text></svg><figcaption>三者的关系</figcaption>';
    second.after(diagram);
  });
  const viewer = report(page).locator(".pz-lightbox");
  await report(page).locator("figure img").first().click();
  await expect(viewer).toContainText("1 / 3");
  await expect(report(page).getByRole("button", { name: "上一张" })).toBeDisabled();
  await page.keyboard.press("ArrowRight");
  await expect(viewer).toContainText("2 / 3");
  await expect(viewer).toContainText("第二张图注");
  await report(page).getByRole("button", { name: "下一张" }).click();
  await expect(viewer).toContainText("3 / 3");
  await expect(viewer).toContainText("三者的关系");
  await expect(viewer.locator("svg")).toHaveCount(1);
  await expect(report(page).getByRole("button", { name: "下一张" })).toBeDisabled();
  await page.keyboard.press("ArrowRight");
  await expect(viewer).toContainText("3 / 3");
  await page.keyboard.press("ArrowLeft");
  await expect(viewer).toContainText("2 / 3");
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
  await report(page).locator("figure svg").click();
  await expect(viewer).toContainText("3 / 3");
  await page.keyboard.press("Escape");
});
