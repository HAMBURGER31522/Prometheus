// E13 ② (PLAN 15.4.10): the report paper follows the window instead of the template's 860px.
import { expect, test } from "@playwright/test";

import { inReport, openFirstItem, openTab, report, seed } from "./helpers";

test.beforeAll(async ({ request }) => {
  await seed(request);
});

test("窗口 1600px 宽时报告纸面宽于 1000px，报告自带目录不显示", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  await expect(report(page).locator("h1")).toBeVisible();
  const paper = await inReport(page, () => (document.querySelector(".paper") as HTMLElement).getBoundingClientRect().width);
  expect(paper).toBeGreaterThan(1000);
  await expect(report(page).locator(".report-nav")).toBeHidden();
  await expect(report(page).locator(".report-nav")).toHaveCount(1);
});

test("纸面两侧各留 40px，图片不放大到超过原尺寸", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  await expect(report(page).locator("figure img")).toBeVisible();
  const sizes = await inReport(page, () => {
    const paper = (document.querySelector(".paper") as HTMLElement).getBoundingClientRect();
    const img = document.querySelector("figure img") as HTMLImageElement;
    return { paper: paper.width, left: paper.left, page: document.documentElement.clientWidth, img: img.getBoundingClientRect().width, natural: img.naturalWidth };
  });
  expect(sizes.paper).toBeGreaterThan(sizes.page - 80 - 2);
  expect(sizes.paper).toBeLessThanOrEqual(sizes.page - 80 + 2);
  expect(sizes.left).toBeGreaterThan(38);
  expect(sizes.img).toBeGreaterThan(0);
  expect(sizes.img).toBeLessThanOrEqual(sizes.natural + 1);
});
