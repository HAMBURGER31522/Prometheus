// E13 ② (PLAN 15.4.10): categories are managed by hand and one change shows everywhere.
import { type APIRequestContext, type Page, expect, test } from "@playwright/test";

import { API, AUTH, openTab, seed } from "./helpers";

const UNCATEGORIZED = "未分类";
let itemIds: string[] = [];

async function categoriesByName(request: APIRequestContext) {
  const rows = (await (await request.get(`${API}/api/categories`, { headers: AUTH })).json()) as { id: number; name: string }[];
  return new Map(rows.map((row) => [row.name, row.id]));
}

async function itemTitle(request: APIRequestContext, id: string) {
  const row = await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json();
  return (row.report_title || row.source_title) as string;
}

/** Finished items in a category, read from the backend (a list still rendering would undercount). */
async function countIn(request: APIRequestContext, name: string) {
  const id = (await categoriesByName(request)).get(name);
  const rows = (await (await request.get(`${API}/api/items`, { headers: AUTH })).json()) as { category_id: number; status: string }[];
  return rows.filter((row) => row.status === "done" && row.category_id === id).length;
}

const categoryList = (page: Page) => page.getByRole("list", { name: "分类" });
const categoryButton = (page: Page, name: string) =>
  categoryList(page).getByRole("button", { name: new RegExp(`^${name}\\s*\\d*$`) });
const itemTitles = (page: Page) => page.getByRole("list", { name: "条目" }).getByTestId("item-title");

test.beforeAll(async ({ request }) => {
  itemIds = await seed(request);
});

// Leave the shared fake backend as the other spec files expect it: every item in 未分类, no extra category.
test.afterEach(async ({ request }) => {
  const names = await categoriesByName(request);
  const home = names.get(UNCATEGORIZED);
  if (home === undefined) return;
  for (const id of itemIds) {
    await request.patch(`${API}/api/items/${id}`, { headers: AUTH, data: { category_id: home } });
  }
  for (const [name, id] of names) {
    if (name !== UNCATEGORIZED) await request.delete(`${API}/api/categories/${id}?move_items=1`, { headers: AUTH });
  }
});

test("「+」新建分类，拖进去的文章在导图和字幕页签里也在新分类下", async ({ page, request }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await page.getByRole("button", { name: "新建分类" }).click();
  const input = page.getByRole("textbox", { name: "新分类名称" });
  await input.fill("我的分类");
  await input.press("Enter");
  await expect(categoryButton(page, "我的分类")).toBeVisible();

  await categoryButton(page, UNCATEGORIZED).click();
  const before = await countIn(request, UNCATEGORIZED);
  await expect(itemTitles(page)).toHaveCount(before);
  const title = await itemTitles(page).first().innerText();
  await page.getByRole("list", { name: "条目" }).getByRole("button").first().dragTo(categoryButton(page, "我的分类"));

  for (const tab of ["知识库", "思维导图", "字幕"]) {
    await openTab(page, tab);
    await categoryButton(page, "我的分类").click();
    await expect(itemTitles(page)).toHaveText([title]);
    await categoryButton(page, UNCATEGORIZED).click();
    await expect(itemTitles(page)).toHaveCount(before - 1);
  }
});

test("新建重名分类时提示已有", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await page.getByRole("button", { name: "新建分类" }).click();
  const input = page.getByRole("textbox", { name: "新分类名称" });
  await input.fill(UNCATEGORIZED);
  await input.press("Enter");
  await expect(page.getByText("已有这个分类")).toBeVisible();
  await expect(categoryButton(page, UNCATEGORIZED)).toHaveCount(1);
});

test("✎ 改名后三个页签和阅读页面包屑都显示新名", async ({ page, request }) => {
  await request.post(`${API}/api/categories`, { headers: AUTH, data: { name: "旧名字" } });
  const target = (await categoriesByName(request)).get("旧名字")!;
  await request.patch(`${API}/api/items/${itemIds[0]}`, { headers: AUTH, data: { category_id: target } });
  const title = await itemTitle(request, itemIds[0]);

  await page.goto("/");
  await openTab(page, "思维导图");
  await categoryButton(page, "旧名字").click();
  await categoryList(page).getByRole("button", { name: "改名「旧名字」" }).click();
  const input = page.getByRole("textbox", { name: "分类名称" });
  await input.fill("新名字");
  await input.press("Enter");

  for (const tab of ["知识库", "思维导图", "字幕"]) {
    await openTab(page, tab);
    await expect(categoryButton(page, "新名字")).toBeVisible();
    await expect(categoryButton(page, "旧名字")).toHaveCount(0);
  }
  await categoryButton(page, "新名字").click();
  await page.getByRole("list", { name: "条目" }).getByRole("button").first().click();
  await expect(page.getByRole("toolbar", { name: "阅读" })).toContainText("新名字");
  await expect(page.getByRole("toolbar", { name: "阅读" }).getByTestId("reader-title")).toHaveText(title);
});

test("🗑 删除非空分类后，其中的文章出现在未分类", async ({ page, request }) => {
  await request.post(`${API}/api/categories`, { headers: AUTH, data: { name: "要删的" } });
  const target = (await categoriesByName(request)).get("要删的")!;
  await request.patch(`${API}/api/items/${itemIds[1]}`, { headers: AUTH, data: { category_id: target } });

  await page.goto("/");
  await openTab(page, "字幕");
  await categoryButton(page, UNCATEGORIZED).click();
  const before = await countIn(request, UNCATEGORIZED);
  await expect(itemTitles(page)).toHaveCount(before);
  await expect(categoryList(page).getByRole("button", { name: `删除「${UNCATEGORIZED}」` })).toHaveCount(0);
  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("1 篇会移到「未分类」");
    await dialog.accept();
  });
  await categoryList(page).getByRole("button", { name: "删除「要删的」" }).click();
  await expect(categoryButton(page, "要删的")).toHaveCount(0);
  await categoryButton(page, UNCATEGORIZED).click();
  await expect(itemTitles(page)).toHaveCount(before + 1);
});

test("移空的分类仍然留在列表里，可以再移回去", async ({ page, request }) => {
  await request.post(`${API}/api/categories`, { headers: AUTH, data: { name: "暂时空" } });
  await page.goto("/");
  await openTab(page, "知识库");
  await expect(categoryButton(page, "暂时空")).toBeVisible();
  await expect(categoryButton(page, "暂时空")).toContainText("0");
  await expect(categoryButton(page, UNCATEGORIZED)).toBeVisible();
});

test("阅读页用「⋯ → 移到」移动文章，原来的分类下拉框不存在", async ({ page, request }) => {
  await request.post(`${API}/api/categories`, { headers: AUTH, data: { name: "目的地" } });
  await page.goto("/");
  await openTab(page, "知识库");
  await categoryButton(page, UNCATEGORIZED).click();
  const title = await itemTitles(page).first().innerText();
  await page.getByRole("list", { name: "条目" }).getByRole("button").first().click();
  const bar = page.getByRole("toolbar", { name: "阅读" });
  await expect(bar.getByTestId("reader-title")).toHaveText(title);
  await expect(bar.getByRole("combobox", { name: "移到分类" })).toHaveCount(0);
  await bar.getByRole("button", { name: "条目操作" }).click();
  await page.getByRole("menuitem", { name: "移到「目的地」" }).click();
  await expect(bar).toContainText("目的地");
  await expect(bar.getByTestId("reader-title")).toHaveText(title);
});

test("没有标签的文章，阅读页「⋯」里有「补全标签和摘要」，点了只补这两样", async ({ page }) => {
  // Items finished before tags existed: strip the tags of every item as the app sees them.
  await page.route(`${API}/api/items`, async (route) => {
    const response = await route.fetch();
    const rows = (await response.json()) as Record<string, unknown>[];
    await route.fulfill({ response, json: rows.map((row) => ({ ...row, tags: null, description: null })) });
  });
  const sent: unknown[] = [];
  await page.route(/\/api\/items\/[0-9a-f]+\/regenerate$/, async (route) => {
    sent.push(route.request().postDataJSON());
    await route.fulfill({ json: { queued: true } });
  });
  await page.goto("/");
  await openTab(page, "知识库");
  await categoryButton(page, UNCATEGORIZED).click();
  await page.getByRole("list", { name: "条目" }).getByRole("button").first().click();
  const bar = page.getByRole("toolbar", { name: "阅读" });
  await bar.getByRole("button", { name: "条目操作" }).click();
  await page.getByRole("menuitem", { name: "补全标签和摘要" }).click();
  await expect.poll(() => sent).toEqual([{ only: "tags" }]);
});

test("已有标签的文章不显示「补全标签和摘要」", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "知识库");
  await categoryButton(page, UNCATEGORIZED).click();
  await page.getByRole("list", { name: "条目" }).getByRole("button").first().click();
  await page.getByRole("toolbar", { name: "阅读" }).getByRole("button", { name: "条目操作" }).click();
  await expect(page.getByRole("menuitem", { name: "删除" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "补全标签和摘要" })).toHaveCount(0);
});

test("拖完一篇以后，点另一篇照常打开", async ({ page, request }) => {
  await request.post(`${API}/api/categories`, { headers: AUTH, data: { name: "拖进来" } });
  await page.goto("/");
  await openTab(page, "知识库");
  await categoryButton(page, UNCATEGORIZED).click();
  const cards = page.getByRole("list", { name: "条目" }).getByRole("button");
  await expect(cards).toHaveCount(await countIn(request, UNCATEGORIZED));
  await cards.first().dragTo(categoryButton(page, "拖进来"));
  await expect(categoryButton(page, "拖进来")).toContainText("1");
  const title = await itemTitles(page).first().innerText();
  await cards.first().click();
  await expect(page.getByRole("toolbar", { name: "阅读" }).getByTestId("reader-title")).toHaveText(title);
});
