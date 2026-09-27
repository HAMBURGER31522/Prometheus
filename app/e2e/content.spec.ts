// E12 ② (PLAN 15.4.9): the content additions, end to end.
import { expect, test } from "@playwright/test";

import { openFirstItem, openTab, report, seed, sidebar } from "./helpers";

test.beforeAll(async ({ request }) => {
  await seed(request);
});

test("① 导图要点卡片显示详解，面板有全文，「在精读中查看」跳到该要点所在的章节", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "思维导图");
  await openFirstItem(page);
  // 14:52 is where s5 starts (and the last second of s4).
  const card = page.locator(".react-flow__node", { hasText: "为什么是现在" });
  const detail = card.locator(".mind-detail");
  await expect(detail).not.toBeEmpty();
  await card.click();
  const panel = page.getByRole("complementary", { name: "节点摘要" });
  await expect(panel.getByTestId("mind-detail")).toHaveText((await detail.textContent()) ?? "");
  await panel.getByRole("button", { name: "在精读中查看" }).click();
  await expect(sidebar(page).getByRole("button", { name: "知识库", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(report(page).locator("#s5 h2")).toBeInViewport();
  await expect(report(page).locator("#s4 h2")).not.toBeInViewport();
});
