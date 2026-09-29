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

test("「讲清楚审校」在完整模式下默认开、可以关；标准模式下不显示", async ({ page }) => {
  const review = page.getByRole("switch", { name: "讲清楚审校" });
  const save = async () => {
    await page.getByRole("button", { name: "保存", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("已保存");
  };
  await page.goto("/");
  await openTab(page, "设置");
  await expect(review).toHaveAttribute("aria-checked", "true");
  await review.click();
  await save();
  await page.reload();
  await openTab(page, "设置");
  await expect(review).toHaveAttribute("aria-checked", "false");
  await review.click();
  await save();
  await depth(page).getByRole("radio", { name: /标准/ }).check();
  await expect(review).toHaveCount(0);
  await depth(page).getByRole("radio", { name: /完整/ }).check();
  await expect(review).toHaveAttribute("aria-checked", "true");
});

test("「更新模型目录」：点了以后显示目录日期", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "设置");
  const catalogue = page.getByTestId("model-catalogue");
  await expect(catalogue).toContainText("模型目录");
  await page.getByRole("button", { name: "更新模型目录" }).click();
  await expect(catalogue).toContainText(/已更新.*\d{4}-\d{2}-\d{2}/);
});

test("目录里没有的模型选了「最高」，设置页说明会原样发给接口", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "设置");
  await page.getByRole("button", { name: "新增配置" }).click();
  const editor = page.getByRole("region", { name: "编辑模型配置" });
  await editor.getByRole("button", { name: "自定义", exact: true }).click();
  await editor.getByRole("combobox", { name: "模型" }).fill("fake-model-a");
  await expect(editor.getByText("会把所选档位原样发给接口")).toHaveCount(0);
  await editor.getByRole("combobox", { name: "思考强度" }).click();
  await page.getByRole("listbox", { name: "思考强度" }).getByRole("option", { name: "最高" }).click();
  await expect(
    editor.getByText("这个模型不在模型目录里：会把所选档位原样发给接口，接口不支持时任务会失败并写明原因"),
  ).toBeVisible();
});
