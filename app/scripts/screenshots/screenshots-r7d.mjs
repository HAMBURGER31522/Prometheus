// R7d screenshots for the user (PLAN 15.4.10) on the real preview data. Never clicks
// 「获取模型列表」 or 「测试模型」 and never saves settings: no request reaches a model relay.
//   node scripts/screenshots/screenshots-r7d.mjs <app url with ?port=&token=> <out dir> <english title regex>
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [url, out, english] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const shot = async (name, wait = 1200) => {
  await page.waitForTimeout(wait);
  await page.screenshot({ path: join(out, `${name}.png`) });
  console.log("saved", name);
};
const tab = (label) => page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: label, exact: true }).click();
const categories = () => page.getByRole("list", { name: "分类" });
const category = (name) => categories().getByRole("button", { name: new RegExp(`^${name}\\s*\\d*$`) });
const card = (title) => page.getByRole("list", { name: "条目" }).getByRole("button", { name: new RegExp(title) });
/** Click a category and wait until the list shows it (the lists swap after a view transition). */
const showCategory = async (name) => {
  await category(name).click();
  await page.locator(".items-head h1").filter({ hasText: name }).waitFor();
  await page.waitForTimeout(700);
};
const closeReader = async () => {
  const reader = page.getByRole("toolbar", { name: "阅读" });
  if (await reader.isVisible()) await reader.locator(".crumbs button").first().click();
};
const openItem = async (title) => {
  await closeReader();
  await categories().getByRole("button").first().waitFor();
  for (const name of await categories().locator(".category > span:first-child").allInnerTexts()) {
    await showCategory(name);
    if (await card(title).count()) {
      await card(title).first().click();
      return;
    }
  }
  throw new Error(`item not found: ${title}`);
};
const settle = () => page.waitForFunction(() => document.getAnimations().length === 0);
/** Drag a card onto a category with the pointer, optionally stopping halfway for a screenshot;
 *  `cancel` presses Esc before releasing, so nothing moves. */
const drag = async (title, target, shotName, cancel = false) => {
  await settle();
  const from = await card(title).first().boundingBox();
  const to = await category(target).boundingBox();
  await page.mouse.move(from.x + 60, from.y + 20);
  await page.mouse.down();
  await page.mouse.move(from.x + 40, from.y + 30, { steps: 4 });
  await page.mouse.move(to.x + 60, to.y + to.height / 2, { steps: 12 });
  if (shotName) await shot(shotName, 400);
  if (cancel) await page.keyboard.press("Escape");
  await page.mouse.up();
  await page.waitForTimeout(1500);
};

await page.goto(url);
await tab("知识库");
// The three items all went to 学习方法 through the old dropdown: put two back by dragging
// (each only while it is still there, so a rerun skips what is done).
await showCategory("学习方法");
await shot("1-categories");
if (await card("卡巴拉").count()) {
  await drag("卡巴拉", "神秘学", "2-drag-to-category");
  await showCategory("学习方法");
}
if (await card("罗素").count()) await drag("罗素", "战争伦理", "2-drag-to-category");
else await drag("我如何用", "战争伦理", "2-drag-to-category", true);
await showCategory("战争伦理");
await shot("3-after-drag");

await openItem("卡巴拉");
await page.getByRole("toolbar", { name: "阅读" }).getByRole("button", { name: "条目操作" }).click();
await shot("4-reader-menu");
await page.keyboard.press("Escape");
await page.getByRole("toolbar", { name: "阅读" }).getByTestId("reader-title").click();
await shot("5-report-wide-1440");
await page.setViewportSize({ width: 1920, height: 1080 });
await shot("6-report-wide-1920");
await page.setViewportSize({ width: 1440, height: 900 });

await tab("字幕");
await openItem("卡巴拉");
await shot("7-subtitles-paragraphs");
await openItem(english);
await shot("8-subtitles-english");
const word = page.locator(".word").nth(12);
await word.hover();
const lookup = page.getByRole("dialog", { name: "查词" });
await lookup.waitFor();
await shot("9-lookup-before-update", 800);
const update = lookup.getByRole("button", { name: /更新词库|下载离线词典/ });
if (await update.isVisible()) {
  await update.click();
  await lookup.getByRole("region", { name: "英英释义" }).waitFor({ timeout: 900_000 });
}
await word.hover();
await shot("10-lookup-english-definitions", 800);

await tab("设置");
await page.setViewportSize({ width: 1440, height: 1500 });
// The saved key's last four characters never go into a committed screenshot.
const hideKeyTail = () => page.evaluate(() => {
  for (const input of document.querySelectorAll("input[placeholder*='末 4 位']")) {
    input.placeholder = input.placeholder.replace(/末 4 位 [^）)]+/, "末 4 位 ····");
  }
});
const profiles = page.getByRole("list", { name: "模型配置" });
await profiles.getByRole("button", { name: "编辑" }).first().click();
const editor = page.getByRole("region", { name: "编辑模型配置" });
await editor.locator("details").evaluate((node) => { node.open = true; });
await hideKeyTail();
await shot("11-settings-editor");
await editor.getByRole("combobox", { name: "思考强度" }).scrollIntoViewIfNeeded();
await page.mouse.wheel(0, 300);
await editor.getByRole("combobox", { name: "思考强度" }).click();
await hideKeyTail();
await shot("12-settings-thinking-levels", 600);
await page.keyboard.press("Escape");
await editor.getByRole("button", { name: "取消" }).click();
await page.getByRole("button", { name: "新增配置" }).click();
await page.getByRole("region", { name: "编辑模型配置" }).getByRole("group", { name: "常用供应商" }).getByRole("button", { name: "Kimi" }).click();
await shot("13-settings-preset-kimi");
await page.getByRole("region", { name: "编辑模型配置" }).getByRole("button", { name: "取消" }).click();
await browser.close();
