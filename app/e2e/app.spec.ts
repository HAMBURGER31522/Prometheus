// E6 (PLAN 15.3): the rewritten front end against the fake-pipeline backend.
import { expect, test } from "@playwright/test";

import { API, AUTH, VIDEOS, inReport, openFirstItem, openTab, report, seed, sidebar } from "./helpers";

let itemIds: string[] = [];

test.beforeAll(async ({ request }) => {
  itemIds = await seed(request);
});

test("① 侧栏五项，顺序固定", async ({ page }) => {
  await page.goto("/");
  await expect(sidebar(page).getByRole("button", { name: /^(控制台|知识库|思维导图|字幕|设置)$/ })).toHaveText([
    "控制台",
    "知识库",
    "思维导图",
    "字幕",
    "设置",
  ]);
});

test("② 在导图页签打开条目，侧栏高亮停在导图", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "思维导图");
  await openFirstItem(page);
  await expect(sidebar(page).getByRole("button", { name: "思维导图", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  // 精读 / 导图 / 字幕 switches the tab and keeps the item.
  const title = await page.getByRole("toolbar", { name: "阅读" }).getByTestId("reader-title").innerText();
  await page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name: "字幕" }).click();
  await expect(sidebar(page).getByRole("button", { name: "字幕", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("toolbar", { name: "阅读" }).getByTestId("reader-title")).toHaveText(title);
});

test("③ 知识库、导图、字幕三个页签的分类与条目完全一致", async ({ page }) => {
  await page.goto("/");
  const seen: string[][] = [];
  for (const tab of ["知识库", "思维导图", "字幕"]) {
    await openTab(page, tab);
    const categories = page.getByRole("list", { name: "分类" }).getByRole("button");
    await expect(categories.first()).toBeVisible();
    await categories.first().click();
    const titles = page.getByRole("list", { name: "条目" }).getByTestId("item-title");
    await expect(titles).toHaveCount(VIDEOS.length);
    seen.push([...(await categories.allInnerTexts()), ...(await titles.allInnerTexts())]);
  }
  expect(seen[1]).toEqual(seen[0]);
  expect(seen[2]).toEqual(seen[0]);
});

test("④ 导图画布渲染节点，点节点出现摘要面板", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "思维导图");
  await openFirstItem(page);
  await expect(page.locator(".react-flow__node")).not.toHaveCount(0);
  await page.locator(".react-flow__node", { hasText: "分配的困境" }).click();
  await expect(page.getByRole("complementary", { name: "节点摘要" })).toContainText("消费不足");
});

test("⑤ 字幕页按时间顺序列出全部分段，默认纠错版，可切换原始识别", async ({ page, request }) => {
  const segments = await (await request.get(`${API}/api/items/${itemIds[0]}/subtitle`, { headers: AUTH })).json();
  await page.goto("/");
  await openTab(page, "字幕");
  await openFirstItem(page);
  const rows = page.getByRole("list", { name: "字幕" }).getByRole("listitem");
  await expect(rows).toHaveCount(segments.length);
  await expect(rows.first()).toContainText("00:00:00");
  const raw = page.waitForRequest((r) => r.url().includes("/subtitle") && r.url().includes("variant=raw"));
  await page.getByRole("switch", { name: "原始识别" }).click();
  await raw;
});

test("⑥ 外链交给 openExternal", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "字幕");
  await openFirstItem(page);
  await page.getByRole("list", { name: "字幕" }).getByRole("button", { name: "00:00:00" }).first().click();
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __lastOpenedExternal?: string }).__lastOpenedExternal))
    .toMatch(/^https:\/\/www\.bilibili\.com\/video\/BV[\w]+\/\?p=1&t=0$/);
});

test("⑦ 设置里选「云端」无需任何 Key 即可保存", async ({ page, request }) => {
  await page.goto("/");
  await openTab(page, "设置");
  await page.getByRole("radio", { name: /云端/ }).check();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
  const settings = await (await request.get(`${API}/api/settings`, { headers: AUTH })).json();
  expect(settings.asr.backend).toBe("cloud");
});

test("⑧ 自定义提供商可选 OpenAI / Anthropic 协议", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "设置");
  await page.getByRole("button", { name: "新增配置" }).click();
  const editor = page.getByRole("region", { name: "编辑模型配置" });
  await editor.getByRole("button", { name: "自定义", exact: true }).click();
  await editor.getByRole("combobox", { name: "接口协议" }).click();
  await expect(page.getByRole("listbox", { name: "接口协议" }).getByRole("option")).toHaveText(["OpenAI 兼容", "Anthropic"]);
});

test("报告里的章节链接在报告内跳转，不会变成白页；自带目录隐藏，由工具栏「目录」承担", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await openFirstItem(page);
  // Since 15.4.10 the template's left nav is hidden; a link into the report's chapters in the body
  // must still jump inside the report (a srcdoc page would resolve "#s3" against the app: a blank page).
  await expect(report(page).locator(".report-nav")).toBeHidden();
  await inReport(page, () => {
    const link = document.createElement("a");
    link.href = "#s3";
    link.id = "e2e-jump";
    link.textContent = "跳到第三章";
    document.querySelector(".paper")!.prepend(link);
  });
  await report(page).locator("#e2e-jump").click();
  await expect(report(page).locator("#s3")).toBeInViewport();
  await expect(report(page).locator("h1")).toBeVisible();
});
