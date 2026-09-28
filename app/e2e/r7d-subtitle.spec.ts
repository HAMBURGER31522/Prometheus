// E13 ② (PLAN 15.4.10): subtitles read as 10–15 s paragraphs. The fake backend groups
// fixtures/segments.json (short fragments and one 30 s whisper window) like a real transcription.
import { type APIRequestContext, type Page, expect, test } from "@playwright/test";

import { API, AUTH, openTab, seed } from "./helpers";

type Paragraph = { start: number; end: number; text: string; zh?: string };

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
