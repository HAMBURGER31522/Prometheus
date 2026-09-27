// Screenshots for the E7 review (PLAN 15.3): every page of the running dev app.
//   node scripts/screenshots.mjs <app url with ?port=&token=> <out dir>
// The backend and Vite must already be running.
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [url, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const shot = async (name) => {
  await page.waitForTimeout(900); // let transitions and the lens settle
  await page.screenshot({ path: join(out, `${name}.png`) });
  console.log("saved", name);
};
const tab = (label) => page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: label, exact: true }).click();
const openItem = async (category, title) => {
  const reader = page.getByRole("toolbar", { name: "阅读" });
  if (await reader.isVisible()) await reader.locator(".crumbs button").first().click();
  await page.getByRole("list", { name: "分类" }).getByRole("button", { name: new RegExp(category) }).click();
  await page.getByRole("list", { name: "条目" }).getByRole("button", { name: new RegExp(title) }).click();
};

await page.goto(url);
await shot("1-console");
await tab("知识库");
await page.getByRole("list", { name: "分类" }).getByRole("button").first().click();
await shot("2-library");
await openItem("战争伦理", "罗素");
await page.waitForTimeout(1500);
await shot("3-report");
await tab("思维导图");
await openItem("神秘学", "卡巴拉");
await page.waitForTimeout(1200);
await shot("4-mindmap");
await page.locator(".react-flow__node", { hasText: "72神名的推导" }).click();
await shot("5-mindmap-panel");
await page.getByRole("button", { name: "展开 72神名的推导" }).click();
await page.waitForTimeout(600);
await shot("5b-mindmap-branch");
await page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name: "字幕" }).click();
await shot("6-subtitle");
await tab("设置");
await shot("7-settings");
await browser.close();
