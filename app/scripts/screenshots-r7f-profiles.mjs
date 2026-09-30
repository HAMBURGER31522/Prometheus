// R7f: a record of the two model profiles the live runs used (PLAN 15.4.13), taken from the preview
// on the real data. Opens each profile's editor with 「高级」 expanded; the key box's 「末 4 位」 hint
// is blanked before the picture. Never saves, never clicks anything that calls a model.
//   node scripts/screenshots-r7f-profiles.mjs <app url with ?port=&token=> <out dir>
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [url, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1.5 });
const shots = [
  ["anyrouter · Codex CLI", "10-profile-codex-anyrouter-gpt-6-astra"],
  ["justwoker · Claude Code", "11-profile-claude-code-justwoker-opus-4-8"],
];
for (const [name, file] of shots) {
  await page.goto(url);
  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "设置", exact: true }).click();
  const card = page.getByRole("list", { name: "模型配置" }).getByRole("listitem").filter({ hasText: name });
  await card.getByRole("button", { name: "编辑" }).click();
  const editor = page.getByRole("region", { name: "编辑模型配置" });
  await editor.locator("details.advanced summary").click();
  await page.evaluate(() => {
    for (const input of document.querySelectorAll("input")) {
      if ((input.placeholder || "").includes("末 4 位")) input.placeholder = "已保存（Key 不显示）";
      if (input.type === "password" && input.value) input.value = "";
    }
  });
  await page.waitForTimeout(700);
  await editor.scrollIntoViewIfNeeded();
  await editor.screenshot({ path: join(out, `${file}.png`) });
  console.log("saved", file);
}
await browser.close();
