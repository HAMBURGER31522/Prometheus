// E17 ② (PLAN 15.4.15): the console picks what a video gets — 精读 / 字幕 / 导图, and how detailed the report is.
import { type Page, expect, test } from "@playwright/test";

import { API } from "./helpers";

const URL = "https://www.bilibili.com/video/BV1EJ4m1t7Zs/";

const circles = (page: Page) => page.getByRole("group", { name: "生成哪些" });
const circle = (page: Page, name: string) => circles(page).getByRole("button", { name, exact: true });
const depth = (page: Page, name: string) =>
  page.getByRole("radiogroup", { name: "精读详细程度" }).getByRole("radio", { name, exact: true });
const figures = (page: Page) => page.getByRole("switch", { name: "配图" });

async function expectPressed(page: Page, pressed: { 精读: boolean; 字幕: boolean; 导图: boolean }) {
  for (const [name, on] of Object.entries(pressed)) {
    await expect(circle(page, name)).toHaveAttribute("aria-pressed", String(on));
  }
}

/** Catch what the console submits; the fake pipeline never sees it. */
async function catchSubmits(page: Page): Promise<unknown[]> {
  const sent: unknown[] = [];
  await page.route(`${API}/api/items`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    sent.push(route.request().postDataJSON());
    await route.fulfill({ status: 201, json: { id: "0123456789abcdef" } });
  });
  return sent;
}

/** The settings say 标准, so a console that follows them shows 标准 (the fake backend's own default is 完整). */
async function settingsSayStandard(page: Page) {
  await page.route(`${API}/api/settings`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const response = await route.fetch();
    const settings = await response.json();
    await route.fulfill({ response, json: { ...settings, report: { ...settings.report, depth: "standard" } } });
  });
}

test("三个圆圈：第一次三个都勾；勾导图带上精读，取消精读带走导图，至少留一样", async ({ page }) => {
  await page.goto("/");
  await expectPressed(page, { 精读: true, 字幕: true, 导图: true });

  await circle(page, "精读").click();
  await expectPressed(page, { 精读: false, 字幕: true, 导图: false });
  await circle(page, "字幕").click();
  await expectPressed(page, { 精读: false, 字幕: true, 导图: false });

  await circle(page, "导图").click();
  await expectPressed(page, { 精读: true, 字幕: true, 导图: true });
  await circle(page, "导图").click();
  await expectPressed(page, { 精读: true, 字幕: true, 导图: false });
});

test("没勾精读时，详细程度和配图变灰；勾回来就能选", async ({ page }) => {
  await page.goto("/");
  await expect(depth(page, "标准")).toBeEnabled();
  await expect(figures(page)).toBeEnabled();

  await circle(page, "精读").click();
  await expect(depth(page, "标准")).toBeDisabled();
  await expect(depth(page, "完整")).toBeDisabled();
  await expect(figures(page)).toBeDisabled();

  await circle(page, "精读").click();
  await expect(depth(page, "完整")).toBeEnabled();
  await expect(figures(page)).toBeEnabled();
});

test("详细程度默认沿用设置；提交带上勾选、档位和配图", async ({ page }) => {
  await settingsSayStandard(page);
  const sent = await catchSubmits(page);
  await page.goto("/");
  await expect(depth(page, "标准")).toHaveAttribute("aria-checked", "true");

  await page.getByRole("textbox", { name: "视频链接" }).fill(URL);
  await page.getByRole("button", { name: "开始" }).click();
  await expect
    .poll(() => sent)
    .toEqual([{ url: URL, figures: true, outputs: { report: true, subtitles: true, mindmap: true }, depth: "standard" }]);

  // Only the subtitles: nothing to draw figures for.
  await circle(page, "精读").click();
  await page.getByRole("textbox", { name: "视频链接" }).fill(URL);
  await page.getByRole("button", { name: "开始" }).click();
  await expect.poll(() => sent.length).toBe(2);
  expect(sent[1]).toEqual({
    url: URL,
    figures: false,
    outputs: { report: false, subtitles: true, mindmap: false },
    depth: "standard",
  });

  // 完整, no mind map.
  await circle(page, "精读").click();
  await depth(page, "完整").click();
  await page.getByRole("textbox", { name: "视频链接" }).fill(URL);
  await page.getByRole("button", { name: "开始" }).click();
  await expect.poll(() => sent.length).toBe(3);
  expect(sent[2]).toEqual({
    url: URL,
    figures: true,
    outputs: { report: true, subtitles: true, mindmap: false },
    depth: "full",
  });
});

test("记住上次提交时的选择；只点不提交不算", async ({ page }) => {
  await catchSubmits(page);
  await page.goto("/");
  await circle(page, "精读").click();
  await page.reload();
  await expectPressed(page, { 精读: true, 字幕: true, 导图: true });

  await circle(page, "精读").click();
  await page.getByRole("textbox", { name: "视频链接" }).fill(URL);
  await page.getByRole("button", { name: "开始" }).click();
  await expect(page.getByRole("textbox", { name: "视频链接" })).toHaveValue("");
  await page.reload();
  await expectPressed(page, { 精读: false, 字幕: true, 导图: false });
});
