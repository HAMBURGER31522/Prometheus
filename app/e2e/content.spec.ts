// E12 ② (PLAN 15.4.9): the content additions, end to end.
import { expect, test } from "@playwright/test";

import { API, AUTH, openFirstItem, openTab, report, seed, sidebar } from "./helpers";

/** In fake mode a YouTube link becomes an English item from fixtures/segments.en.json. */
const ENGLISH = "https://www.youtube.com/watch?v=M7lc1UVf-VE";

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

test("② 英文条目的字幕每段下方显示中文，工具栏可以关掉译文", async ({ page, request }) => {
  const created = await request.post(`${API}/api/items`, { headers: AUTH, data: { url: ENGLISH, figures: false } });
  const id = (await created.json()).id;
  await expect
    .poll(async () => (await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json()).status, {
      timeout: 20_000,
    })
    .toBe("done");
  await page.goto("/");
  await openTab(page, "字幕");
  await page.getByRole("list", { name: "分类" }).getByRole("button").first().click();
  await page.getByRole("list", { name: "条目" }).getByRole("button", { name: /English Sample Channel/ }).click();
  const first = page.getByRole("list", { name: "字幕" }).getByRole("listitem").first();
  await expect(first).toContainText("Imagine the money a country earns");
  await expect(first.getByTestId("subtitle-zh")).toHaveText("想象一个国家挣到的钱放在三个口袋里");
  await page.getByRole("switch", { name: "译文" }).click();
  await expect(first.getByTestId("subtitle-zh")).toHaveCount(0);
});

test("③ 悬停英文单词出现查词浮窗：首次下载离线词典，显示原形和释义，可以打开在线词典", async ({ page, request }) => {
  const created = await request.post(`${API}/api/items`, { headers: AUTH, data: { url: ENGLISH, figures: false } });
  const id = (await created.json()).id;
  await expect
    .poll(async () => (await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json()).status, {
      timeout: 20_000,
    })
    .toBe("done");
  await page.goto("/");
  await openTab(page, "字幕");
  await page.getByRole("list", { name: "分类" }).getByRole("button").first().click();
  await page.getByRole("list", { name: "条目" }).getByRole("button", { name: /English Sample Channel/ }).click();
  const word = page.getByRole("list", { name: "字幕" }).getByText("sitting", { exact: true });
  await expect(word).toBeVisible();
  await word.hover();
  const popup = page.getByRole("dialog", { name: "查词" });
  await popup.getByRole("button", { name: /下载离线词典/ }).click();
  await expect(popup).toContainText("现在分词");
  await expect(popup).toContainText("vi. 坐");
  await expect(popup.getByTestId("lookup-headword")).toHaveText("sit");
  await popup.getByRole("button", { name: "有道" }).click();
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __lastOpenedExternal?: string }).__lastOpenedExternal))
    .toContain("youdao.com");
  await page.keyboard.press("Escape");
  await expect(popup).toHaveCount(0);
});

test("④ 设置里可选「自定义（OpenAI 兼容）」转写：填好接口地址、Key 和模型名后保存，Key 只以掩码返回", async ({ page, request }) => {
  await page.goto("/");
  await openTab(page, "设置");
  const custom = page.getByRole("radio", { name: /自定义（OpenAI 兼容）/ });
  await expect(custom).toBeVisible();
  await custom.check();
  const box = page.getByRole("group", { name: "自定义转写接口" });
  await box.getByLabel("接口地址").fill("https://asr.example/v1");
  await box.getByLabel("API Key", { exact: true }).fill("sk-asr-9876");
  await box.getByLabel("模型名").fill("whisper-1");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
  const settings = await (await request.get(`${API}/api/settings`, { headers: AUTH })).json();
  expect(settings.asr).toEqual({
    backend: "custom",
    custom: { base_url: "https://asr.example/v1", api_key: "****9876", model: "whisper-1" },
  });
  // Leave the shared backend on local transcription for the other tests.
  await request.put(`${API}/api/settings`, { headers: AUTH, data: { ...settings, asr: { ...settings.asr, backend: "local" } } });
});

