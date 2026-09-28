// E13 ② (PLAN 15.4.10): subtitles read as 10–15 s paragraphs, and the lookup popup shows English
// definitions. The fake backend groups fixtures/segments.json (short fragments and one 30 s
// whisper window) like a real transcription, and installs fixtures/ecdict.sample.csv as the dictionary.
import { type APIRequestContext, type Page, expect, test } from "@playwright/test";

import { API, AUTH, openTab, seed } from "./helpers";

type Paragraph = { start: number; end: number; text: string; zh?: string };

/** In fake mode a YouTube link becomes an English item from fixtures/segments.en.json. */
const ENGLISH = "https://www.youtube.com/watch?v=M7lc1UVf-VE";
const SIT = ["v. be seated", "v. be around, often idly or without specific purpose", "v. take a seat"];

async function englishItem(request: APIRequestContext): Promise<string> {
  const created = await request.post(`${API}/api/items`, { headers: AUTH, data: { url: ENGLISH, figures: false } });
  const id = (await created.json()).id;
  await expect
    .poll(async () => (await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json()).status, {
      timeout: 20_000,
    })
    .toBe("done");
  return id;
}

/** Install the sample dictionary (again) and wait until it is ready. */
async function dictionaryReady(request: APIRequestContext) {
  await request.post(`${API}/api/dictionary/install`, { headers: AUTH });
  await expect
    .poll(async () => (await (await request.get(`${API}/api/dictionary`, { headers: AUTH })).json()).state, {
      timeout: 20_000,
    })
    .toBe("ready");
}

const lastOpened = (page: Page) =>
  page.evaluate(() => (window as unknown as { __lastOpenedExternal?: string }).__lastOpenedExternal);

test.beforeAll(async ({ request }) => {
  await seed(request);
});

/** Open an item in the current tab, whatever category the other specs moved it to. */
async function openItem(page: Page, request: APIRequestContext, id: string, card?: RegExp) {
  const item = await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json();
  const categories: { id: number; name: string }[] = await (await request.get(`${API}/api/categories`, { headers: AUTH })).json();
  const category = categories.find((row) => row.id === item.category_id);
  if (!category) throw new Error(`no category for item ${id}`);
  await page
    .getByRole("list", { name: "分类" })
    .locator("button.category")
    .filter({ has: page.getByText(category.name, { exact: true }) })
    .click();
  const items = page.getByRole("list", { name: "条目" }).getByRole("button");
  await (card ? items.filter({ hasText: card }) : items.filter({ hasNotText: "English Sample Channel" })).first().click();
  await expect(page.getByRole("toolbar", { name: "阅读" })).toBeVisible();
}

test("字幕页按段落显示：细碎的分段合并成段落，没有超过 15 秒的段落", async ({ page, request }) => {
  const [id] = await seed(request);
  const paragraphs: Paragraph[] = await (await request.get(`${API}/api/items/${id}/subtitle`, { headers: AUTH })).json();
  for (const paragraph of paragraphs) expect(paragraph.end - paragraph.start).toBeLessThanOrEqual(15);
  expect(paragraphs).toHaveLength(5); // 17 fragments in the fixture
  await page.goto("/");
  await openTab(page, "字幕");
  await openItem(page, request, id);
  const rows = page.getByRole("list", { name: "字幕" }).getByRole("listitem");
  await expect(rows).toHaveCount(paragraphs.length);
  await expect(rows.first()).toContainText(
    "大家好，今天我们聊一聊钱在经济里是怎么流动的。对吧，一个国家挣到的钱大致分成三个口袋，家庭、企业和政府。",
  );
  await expect(rows.nth(1)).toContainText("00:00:12");
});

test("悬停英文单词：浮窗在中文释义下方显示英英释义，可以打开牛津和欧路", async ({ page, request }) => {
  const id = await englishItem(request);
  await dictionaryReady(request);
  await page.goto("/");
  await openTab(page, "字幕");
  await openItem(page, request, id, /English Sample Channel/);
  await page.getByRole("list", { name: "字幕" }).getByText("sitting", { exact: true }).hover();
  const popup = page.getByRole("dialog", { name: "查词" });
  await expect(popup.getByTestId("lookup-headword")).toHaveText("sit");
  const english = popup.getByRole("region", { name: "英英释义" });
  await expect(english).toContainText("英英释义");
  await expect(english.getByRole("listitem")).toHaveText(SIT);
  const chinese = popup.getByText("vi. 坐；位于；栖息", { exact: true });
  expect((await chinese.boundingBox())!.y).toBeLessThan((await english.boundingBox())!.y);
  await expect(popup).not.toContainText("更新词库");
  await popup.getByRole("button", { name: "牛津" }).click();
  await expect.poll(() => lastOpened(page)).toBe("https://www.oxfordlearnersdictionaries.com/search/english/?q=sitting");
  await popup.getByRole("button", { name: "欧路" }).click();
  await expect.poll(() => lastOpened(page)).toBe("https://dict.eudic.net/dicts/en/sitting");
});

test("旧词库：浮窗照常显示中文释义并提示更新词库，更新后显示英英释义", async ({ page, request }) => {
  const id = await englishItem(request);
  await dictionaryReady(request);
  // The sample dictionary has definitions: answer the first lookup like a dictionary built before them.
  let old = true;
  await page.route(
    (url) => url.pathname === "/api/dictionary/lookup",
    async (route) => {
      if (!old || route.request().method() !== "GET") return route.fallback();
      old = false;
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...(await response.json()), definition: [], needs_update: true } });
    },
  );
  await page.goto("/");
  await openTab(page, "字幕");
  await openItem(page, request, id, /English Sample Channel/);
  await page.getByRole("list", { name: "字幕" }).getByText("sitting", { exact: true }).hover();
  const popup = page.getByRole("dialog", { name: "查词" });
  await expect(popup.getByText("vi. 坐；位于；栖息", { exact: true })).toBeVisible();
  await expect(popup).toContainText("更新词库可显示英英释义（约 23MB）");
  await expect(popup.getByRole("region", { name: "英英释义" })).toHaveCount(0);
  const update = page.waitForRequest((r) => r.url().endsWith("/api/dictionary/install") && r.method() === "POST");
  await popup.getByRole("button", { name: "更新词库" }).click();
  await update;
  await expect(popup.getByRole("region", { name: "英英释义" }).getByRole("listitem")).toHaveText(SIT);
  await expect(popup).not.toContainText("更新词库可显示英英释义");
});
