// E14 (PLAN 15.4.11): 「精读详细程度」 in 设置 — 完整 by default, 标准 is VRA as it was.
import { type Page, expect, test } from "@playwright/test";

import { openTab } from "./helpers";

const depth = (page: Page) => page.getByRole("radiogroup", { name: "精读详细程度" });

async function choose(page: Page, label: RegExp) {
  await depth(page).getByRole("radio", { name: label }).check();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
}

test("精读详细程度默认「完整」，改成「标准」保存后刷新仍然保留", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "设置");
  await expect(depth(page).getByRole("radio", { name: /完整/ })).toBeChecked();
  await expect(depth(page).getByRole("radio", { name: /标准/ })).not.toBeChecked();
  await choose(page, /标准/);
  await page.reload();
  await openTab(page, "设置");
  await expect(depth(page).getByRole("radio", { name: /标准/ })).toBeChecked();
  // Leave the shared fake backend as the other spec files expect it.
  await choose(page, /完整/);
});
