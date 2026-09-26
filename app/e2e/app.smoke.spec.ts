// M7 smoke E2E: the app opens, imports a link, the fake pipeline completes,
// and the report is viewable (D3 subset; full coverage lands with M7 finish).

import { expect, test } from "@playwright/test";

const SAMPLE_URL = "https://www.bilibili.com/video/BV1xJYT6EEYc/";

test("app opens, imports a video and shows the finished report", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("Prometheus");

  // Sidebar order is fixed by the plan (D3 ①).
  const tabs = page.locator(".sidebar .tab");
  await expect(tabs).toHaveText(["控制台", "知识库", "思维导图", "字幕", "设置"]);

  // Console: import a link and watch the fake pipeline finish (D3 ⑤).
  await page.getByPlaceholder("粘贴 B 站或 YouTube 链接，每行一个").fill(SAMPLE_URL);
  await page.getByRole("button", { name: "导入", exact: true }).click();
  await expect(page.locator(".queue")).toContainText("完成", { timeout: 30_000 });

  // Knowledge base: category -> item -> report iframe (D3 ②③).
  await page.locator('.sidebar .tab', { hasText: "知识库" }).click();
  await page.locator(".category-list .row-main").first().click();
  await page.locator(".item-list .row-main").first().click();
  const frame = page.frameLocator("iframe.report-frame");
  await expect(frame.locator("h1").first()).toBeVisible({ timeout: 15_000 });

  await page.screenshot({ path: "../docs/screenshots/report.png", fullPage: true });

  // Back to the console for the overview screenshot.
  await page.locator('.sidebar .tab', { hasText: "控制台" }).click();
  await expect(page.locator(".queue")).toContainText("完成", { timeout: 10_000 });
  await page.screenshot({ path: "../docs/screenshots/console.png", fullPage: true });
});
