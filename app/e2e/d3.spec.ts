// D3 acceptance coverage: ② cross-tab consistency, ③ content views,
// ④ settings persistence, ⑥ transcription toggle rules, ⑦ external links.

import { expect, test } from "@playwright/test";

const TAB_NAMES = ["控制台", "知识库", "思维导图", "字幕", "设置"];

async function openTab(page: import("@playwright/test").Page, name: string) {
  await page.locator(".sidebar .tab", { hasText: name }).click();
}

test.describe("D3 acceptance", () => {
  test("① sidebar order", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".sidebar .tab")).toHaveText(TAB_NAMES);
  });

  test("② 三页签共用同一套分类与条目标题", async ({ page }) => {
    await page.goto("/");
    const seen: string[] = [];
    for (const tab of ["知识库", "思维导图", "字幕"]) {
      await openTab(page, tab);
      await expect(page.locator(".category-list .row-main").first()).toBeVisible();
      seen.push(await page.locator(".category-list .row-main").first().innerText());
      await page.locator(".category-list .row-main").first().click();
      await expect(page.locator(".item-list .row-main").first()).toBeVisible();
      seen.push(await page.locator(".item-list .row-main").first().innerText());
      // back to category level for the next tab
      await page.locator(".breadcrumb button").first().click();
    }
    // 知识库 and 思维导图 saw the same category+item; 字幕 repeats them.
    expect(seen[0]).toEqual(seen[2]);
    expect(seen[1]).toEqual(seen[3]);
    expect(seen[4]).toEqual(seen[0]);
    expect(seen[5]).toEqual(seen[1]);
  });

  test("③ 条目内容：报告 iframe、导图 SVG、字幕行", async ({ page }) => {
    await page.goto("/");
    await openTab(page, "知识库");
    await page.locator(".category-list .row-main").first().click();
    await page.locator(".item-list .row-main").first().click();
    const frame = page.frameLocator("iframe.report-frame");
    await expect(frame.locator("h1").first()).toBeVisible({ timeout: 15_000 });

    // Shared selection (PLAN 9.3): switching tabs keeps the same item open.
    await openTab(page, "思维导图");
    await expect(page.locator(".markmap-container svg")).toBeVisible({ timeout: 15_000 });

    await openTab(page, "字幕");
    await expect(page.locator(".subtitle-list li").first()).toContainText("[", {
      timeout: 15_000,
    });
  });

  test("④ 设置保存后刷新仍保留", async ({ page }) => {
    await page.goto("/");
    await openTab(page, "设置");
    const proxy = page.locator('fieldset:has-text("网络") input').first();
    await proxy.fill("http://127.0.0.1:7897");
    await page.getByRole("button", { name: "保存" }).click();
    await expect(page.locator(".notice")).toContainText("已保存");
    await page.reload();
    await openTab(page, "设置");
    await expect(page.locator('fieldset:has-text("网络") input').first()).toHaveValue(
      "http://127.0.0.1:7897",
    );
  });

  test("⑥ 转写方式切换：禁用规则、内容保留、空 Key 保存失败", async ({ page }) => {
    await page.goto("/");
    await openTab(page, "设置");
    const fieldset = page.locator('fieldset:has-text("转写")');
    const keyInput = fieldset.locator('input[type="password"]');
    const cloudModel = fieldset.locator('input:not([type="radio"]):not([type="checkbox"])').nth(1);
    const enableLocal = fieldset.getByRole("button", { name: "启用本地转写" });

    // 默认本地：云端输入框禁用，启用按钮可用
    await expect(keyInput).toBeDisabled();
    await expect(enableLocal).toBeEnabled();

    // 切云端：输入框恢复，启用按钮置灰
    await fieldset.locator('input[type="radio"]').nth(1).check();
    await expect(keyInput).toBeEnabled();
    await expect(cloudModel).toBeEnabled();
    await expect(enableLocal).toBeDisabled();

    // 填 Key 后来回切换，内容保留
    await keyInput.fill("dashscope-key-1234");
    await fieldset.locator('input[type="radio"]').nth(0).check();
    await fieldset.locator('input[type="radio"]').nth(1).check();
    await expect(keyInput).toHaveValue("dashscope-key-1234");

    // 清空 Key 保存：不提交并显示提示
    await keyInput.fill("");
    await page.getByRole("button", { name: "保存" }).click();
    await expect(page.locator(".notice")).toContainText("请填写 DashScope API Key");

    // 恢复本地后端，避免影响其它用例
    await fieldset.locator('input[type="radio"]').nth(0).check();
    await page.getByRole("button", { name: "保存" }).click();
    await expect(page.locator(".notice")).toContainText("已保存");
  });

  test("⑦ 报告外链交给系统浏览器，页面与 iframe 都不跳转", async ({ page }) => {
    await page.goto("/");
    await openTab(page, "知识库");
    await page.locator(".category-list .row-main").first().click();
    await page.locator(".item-list .row-main").first().click();
    const frame = page.frameLocator("iframe.report-frame");
    await expect(frame.locator("h1").first()).toBeVisible({ timeout: 15_000 });

    // The iframe is sandboxed (opaque origin): trigger the click in JS so the
    // injected capture listener fires regardless of hit-testing.
    await frame.locator('a[href^="http"]').first().evaluate((el) => el.click());
    await expect.poll(() =>
      page.evaluate(() => (window as unknown as { __lastOpenedExternal?: string }).__lastOpenedExternal ?? ""),
    ).toContain("bilibili.com");
    expect(page.url()).toBe("http://localhost:1420/");
    await expect(page.locator("iframe.report-frame")).toBeVisible();
  });
});
