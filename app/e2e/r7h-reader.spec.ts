// E17 ② (PLAN 15.4.15-5): a part this video was submitted without says 「没有生成」 and can be made now,
// on the fake pipeline: the report with its map (at the chosen depth, with or without figures), the map
// alone once there is a report, and the correction of subtitles shown as they were transcribed.
import { type APIRequestContext, type Page, expect, test } from "@playwright/test";

import { API, AUTH } from "./helpers";

type Outputs = { report: boolean; subtitles: boolean; mindmap: boolean };
const SUBTITLES: Outputs = { report: false, subtitles: true, mindmap: false };

/** A finished item made of `outputs`; each test has its own video. */
async function made(request: APIRequestContext, video: string, outputs: Outputs): Promise<string> {
  const created = await request.post(`${API}/api/items`, {
    headers: AUTH,
    data: { url: `https://www.bilibili.com/video/${video}/`, figures: false, outputs, depth: "full" },
  });
  const id = (await created.json()).id as string;
  await expect
    .poll(async () => (await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json()).status, {
      timeout: 20_000,
    })
    .toBe("done");
  return id;
}

/** Open the item from the console's 「最近完成」, then the view. */
async function open(page: Page, video: string, view: "精读" | "导图" | "字幕") {
  await page.goto("/");
  await page.locator(".queue-row", { hasText: video }).getByRole("button", { name: "打开" }).click();
  await expect(page.getByRole("toolbar", { name: "阅读" })).toBeVisible();
  await page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name: view }).click();
}

const fillRequest = (page: Page) =>
  page.waitForRequest((request) => request.method() === "POST" && request.url().endsWith("/regenerate"));
const reportFrame = (page: Page) => page.locator('iframe[title="精读报告"]');
const mapNodes = (page: Page) => page.locator(".react-flow__node");

test("只要字幕的视频：精读页「没有生成」，选标准、关掉配图后「现在生成」，精读和导图一起出来", async ({ page, request }) => {
  await made(request, "BV1R7hRep001", SUBTITLES);
  await open(page, "BV1R7hRep001", "精读");
  await expect(page.getByText("这个视频没有生成精读。")).toBeVisible();
  await expect(reportFrame(page)).toHaveCount(0);
  const depth = page.getByRole("radiogroup", { name: "精读详细程度" });
  await expect(depth.getByRole("radio", { name: "完整" })).toHaveAttribute("aria-checked", "true"); // the settings'
  await expect(page.getByRole("switch", { name: "配图" })).toHaveAttribute("aria-checked", "true");

  await depth.getByRole("radio", { name: "标准" }).click();
  await page.getByRole("switch", { name: "配图" }).click();
  const sent = fillRequest(page);
  await page.getByRole("button", { name: "现在生成" }).click();
  expect((await sent).postDataJSON()).toEqual({ only: "report", depth: "standard", figures: false });

  await expect(reportFrame(page)).toBeVisible({ timeout: 20_000 });
  await page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name: "导图" }).click();
  await expect(mapNodes(page).first()).toBeVisible({ timeout: 10_000 });
});

test("只要字幕的视频：导图页也说没有生成，「现在生成」连精读一起补", async ({ page, request }) => {
  await made(request, "BV1R7hMap001", SUBTITLES);
  await open(page, "BV1R7hMap001", "导图");
  await expect(page.getByText("这个视频没有生成导图。导图从精读生成，会和精读一起生成。")).toBeVisible();
  const sent = fillRequest(page);
  await page.getByRole("button", { name: "现在生成" }).click();
  expect((await sent).postDataJSON()).toEqual({ only: "report", depth: "full", figures: true });
  await expect(mapNodes(page).first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name: "精读" }).click();
  await expect(reportFrame(page)).toBeVisible();
});

test("有精读、没要导图：导图页「现在生成」只补导图，不问详细程度", async ({ page, request }) => {
  await made(request, "BV1R7hMap002", { report: true, subtitles: true, mindmap: false });
  await open(page, "BV1R7hMap002", "导图");
  await expect(page.getByText("这个视频没有生成导图。", { exact: true })).toBeVisible();
  await expect(page.getByRole("radiogroup", { name: "精读详细程度" })).toHaveCount(0);
  const sent = fillRequest(page);
  await page.getByRole("button", { name: "现在生成" }).click();
  expect((await sent).postDataJSON()).toEqual({ only: "mindmap" });
  await expect(mapNodes(page).first()).toBeVisible({ timeout: 20_000 });
});

test("没要字幕：字幕页照样显示原文，顶上「字幕没有纠错」和「现在生成」，点了只纠错", async ({ page, request }) => {
  await made(request, "BV1R7hSub001", { report: true, subtitles: false, mindmap: true });
  await open(page, "BV1R7hSub001", "字幕");
  await expect(page.getByText("字幕没有纠错")).toBeVisible();
  await expect(page.locator(".subtitle-row").first()).toBeVisible();
  const sent = fillRequest(page);
  await page.getByRole("button", { name: "现在生成" }).click();
  expect((await sent).postDataJSON()).toEqual({ only: "subtitles" });
  await expect(page.getByText("已纠错")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("字幕没有纠错")).toHaveCount(0);
});

test("补精读没成功：精读页写明上次为什么没成，还能再点", async ({ page, request }) => {
  const id = await made(request, "BV1R7hFail01", SUBTITLES);
  await page.route(`${API}/api/items`, async (route) => {
    try {
      const response = await route.fetch();
      const rows = (await response.json()) as Record<string, unknown>[];
      const failed = rows.map((row) =>
        row.id === id ? { ...row, error_code: "MODEL_TIMEOUT", error_reason: "模型没有回应", error_message: "x" } : row,
      );
      await route.fulfill({ response, json: failed });
    } catch {
      // The page dropped this poll: there is nobody left to answer.
    }
  });
  await open(page, "BV1R7hFail01", "精读");
  await expect(page.getByText("上次没有生成成功：模型没有回应")).toBeVisible();
  await expect(page.getByRole("button", { name: "现在生成" })).toBeEnabled();
});
