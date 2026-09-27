// R7c screenshots for the user: rich mind map leaves, 在精读中查看, bilingual subtitles, lookup.
//   node scripts/screenshots-r7c.mjs <app url with ?port=&token=> <out dir> <english title regex>
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [url, out, english] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const shot = async (name) => {
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(out, `${name}.png`) });
  console.log("saved", name);
};
const tab = (label) => page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: label, exact: true }).click();
const openItem = async (title) => {
  const reader = page.getByRole("toolbar", { name: "阅读" });
  if (await reader.isVisible()) await reader.locator(".crumbs button").first().click();
  await page.getByRole("list", { name: "分类" }).getByRole("button").first().waitFor();
  for (const category of await page.getByRole("list", { name: "分类" }).getByRole("button").all()) {
    await category.click();
    const item = page.getByRole("list", { name: "条目" }).getByRole("button", { name: new RegExp(title) });
    // The list swaps in after the view transition: give each category a moment.
    if (await item.first().waitFor({ timeout: 2500 }).then(() => true, () => false)) {
      await item.first().click();
      return;
    }
  }
  throw new Error(`item not found: ${title}`);
};

await page.goto(url);
await tab("思维导图");
await openItem("罗素");
await shot("1-mindmap-rich-leaves");
const leaf = page.locator(".mind-node[data-rich]").nth(2);
await leaf.click();
await shot("2-mindmap-panel");
await page.getByRole("complementary", { name: "节点摘要" }).getByRole("button", { name: "在精读中查看" }).click();
await shot("3-report-at-chapter");

await tab("思维导图");
await openItem("卡巴拉");
await page.locator(".mind-fold").first().click();
await shot("4-mindmap-kabbalah-branch");

await tab("字幕");
await openItem(english);
await shot("5-subtitles-bilingual");
const word = page.locator(".word").nth(5);
await word.hover();
await page.waitForTimeout(700);
const download = page.getByRole("dialog", { name: "查词" }).getByRole("button", { name: /下载离线词典/ });
if (await download.isVisible()) {
  await download.click();
  await page.getByRole("dialog", { name: "查词" }).getByTestId("lookup-headword").waitFor({ timeout: 600_000 });
}
await shot("6-lookup");

await tab("设置");
await page.getByRole("radio", { name: /自定义（OpenAI 兼容）/ }).check();
await page.getByRole("group", { name: "自定义转写接口" }).scrollIntoViewIfNeeded();
await shot("7-settings-custom-asr");
await browser.close();
