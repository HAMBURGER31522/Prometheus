// E11 (PLAN 15.3): reading and settings after the first E7 review.
import { expect, test } from "@playwright/test";

import { API, AUTH, inReport, openFirstItem, openTab, report, seed, sidebar } from "./helpers";

test.beforeAll(async ({ request }) => {
  await seed(request);
});

test("① 阅读工具栏的「目录」列出各章，点击后报告滚动到该章", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  await page.getByRole("toolbar", { name: "阅读" }).getByRole("button", { name: "目录" }).click();
  const menu = page.getByRole("menu", { name: "报告目录" });
  await expect(menu.getByRole("menuitem")).toHaveCount(9);
  await menu.getByRole("menuitem").nth(2).click();
  await expect(report(page).locator("#s3")).toBeInViewport();
});

test("② 点击报告图片放大，滚轮缩放，Esc 关闭", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  await report(page).locator("figure img").click();
  const box = report(page).locator(".pz-lightbox");
  await expect(box).toBeVisible();
  const before = await inReport(page, () => (document.querySelector(".pz-image") as HTMLElement).style.transform);
  await box.hover();
  await page.mouse.wheel(0, -400);
  await expect
    .poll(() => inReport(page, () => (document.querySelector(".pz-image") as HTMLElement).style.transform))
    .not.toBe(before);
  await page.keyboard.press("Escape");
  await expect(box).toHaveCount(0);
});

test("③ 侧栏收成图标窄条，仍能切页签，重新打开后保持", async ({ page }) => {
  await page.goto("/");
  await sidebar(page).getByRole("button", { name: "收起侧栏" }).click();
  await expect(page.locator(".app")).toHaveAttribute("data-rail", "collapsed");
  await sidebar(page).getByRole("button", { name: "字幕", exact: true }).click();
  await expect(sidebar(page).getByRole("button", { name: "字幕", exact: true })).toHaveAttribute("aria-current", "page");
  await page.reload();
  await expect(page.locator(".app")).toHaveAttribute("data-rail", "collapsed");
  await page.keyboard.press("Control+b");
  await expect(page.locator(".app")).toHaveAttribute("data-rail", "expanded");
});

test("④ 正文放大缩小，重新打开后保持", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  const bar = page.getByRole("toolbar", { name: "阅读" });
  await bar.getByRole("button", { name: "放大正文" }).click();
  await expect(bar.getByTestId("zoom-level")).toHaveText("110%");
  await expect.poll(() => inReport(page, () => document.documentElement.style.zoom)).toBe("1.1");
  await page.reload();
  await openTab(page, "知识库");
  await openFirstItem(page);
  await expect(page.getByRole("toolbar", { name: "阅读" }).getByTestId("zoom-level")).toHaveText("110%");
  await expect.poll(() => inReport(page, () => document.documentElement.style.zoom)).toBe("1.1");
});

test("⑤ 两份模型配置可以切换；Key 可显示；能获取模型列表；思考强度默认中", async ({ page, request }) => {
  await page.goto("/");
  await openTab(page, "设置");
  for (const [name, model] of [
    ["测试中转 A", "fake-model-a"],
    ["测试中转 B", "fake-model-b"],
  ]) {
    await page.getByRole("button", { name: "新增配置" }).click();
    const editor = page.getByRole("region", { name: "编辑模型配置" });
    await editor.getByLabel("名称").fill(name);
    await editor.getByRole("combobox", { name: "类型" }).click();
    await page.getByRole("option", { name: "自定义" }).click();
    await editor.getByLabel("接口地址").fill(`${API}/fake-llm/v1`);
    await editor.getByLabel("API Key", { exact: true }).fill("e2e");
    await expect(editor.getByLabel("API Key", { exact: true })).toHaveAttribute("type", "password");
    await editor.getByRole("button", { name: "显示 API Key" }).click();
    await expect(editor.getByLabel("API Key", { exact: true })).toHaveAttribute("type", "text");
    await expect(editor.getByRole("combobox", { name: "思考强度" })).toHaveText("中");
    await editor.getByRole("button", { name: "获取模型列表" }).click();
    await page.getByRole("listbox", { name: "模型列表" }).getByRole("option", { name: model }).click();
    await expect(editor.getByRole("combobox", { name: "模型" })).toHaveValue(model);
    await editor.getByRole("button", { name: "保存配置" }).click();
  }
  const cards = page.getByRole("list", { name: "模型配置" }).getByRole("listitem");
  await cards.filter({ hasText: "测试中转 B" }).getByRole("button", { name: "设为当前" }).click();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
  const settings = await (await request.get(`${API}/api/settings`, { headers: AUTH })).json();
  const active = settings.llm_profiles.items.find((p: { id: string }) => p.id === settings.llm_profiles.active);
  expect(active.name).toBe("测试中转 B");
  expect(settings.llm.model).toBe("fake-model-b");
  expect(settings.llm.thinking).toBe("medium");
});
