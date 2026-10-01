// R7h screenshots for the user (PLAN 15.4.15) on the real preview data. Only toggles the console's
// circles and switches; never presses 「开始」, so nothing is submitted and no model is called.
//   node scripts/screenshots/screenshots-r7h.mjs <app url with ?port=&token=> <out dir>
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [url, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const settle = () => page.waitForFunction(() => document.getAnimations().length === 0);
const shot = async (name) => {
  await page.mouse.move(0, 0);
  await settle();
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(out, `${name}.png`) });
  await page.locator(".importer").screenshot({ path: join(out, `${name}-close.png`) });
  console.log("saved", name);
};
const circle = (name) => page.getByRole("group", { name: "生成哪些" }).getByRole("button", { name, exact: true });
const depth = (name) => page.getByRole("radiogroup", { name: "精读详细程度" }).getByRole("radio", { name, exact: true });

await page.goto(url);
await circle("精读").waitFor();
await page.getByRole("textbox", { name: "视频链接" }).fill("https://www.bilibili.com/video/BV1EJ4m1t7Zs");
await shot("01-first-time-all-three");

await circle("精读").click();
await shot("02-only-subtitles-grey");

await circle("精读").click();
await depth("标准").click();
await shot("03-report-and-subtitles-standard");

await circle("导图").click();
await circle("字幕").click();
await shot("04-report-and-mindmap-no-subtitles");

await browser.close();
