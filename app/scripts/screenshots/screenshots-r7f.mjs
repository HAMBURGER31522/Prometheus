// R7f screenshots for the user (PLAN 15.4.13) on the fake backend (node scripts/e2e-backend.mjs on
// 8765): the Agent in a model profile, the Codex login and the update window. Nothing reaches a
// model or npm; every key on screen is empty.
//   node scripts/screenshots/screenshots-r7f.mjs <app url> <out dir>
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [url, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const settle = () => page.waitForFunction(() => document.getAnimations().length === 0);
const editor = () => page.getByRole("region", { name: "编辑模型配置" });
const shootEditor = async (name) => {
  await settle();
  await editor().scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  await editor().screenshot({ path: join(out, `${name}.png`) });
  console.log("saved", name);
};
const shootPage = async (name) => {
  await settle();
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(out, `${name}.png`) });
  console.log("saved", name);
};
const pick = async (box, option) => {
  await editor().getByRole("combobox", { name: box }).click();
  await page.getByRole("listbox", { name: box }).getByRole("option", { name: option, exact: true }).click();
};
const newProfile = async () => {
  await page.goto(url);
  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "新增配置" }).click();
  await editor().waitFor();
};

await newProfile();
await shootEditor("01-editor-pi");

await pick("Agent", "Claude Code");
await shootEditor("02-claude-code-not-installed");

await editor().getByRole("combobox", { name: "思考强度" }).click();
await page.waitForTimeout(300);
await editor().scrollIntoViewIfNeeded();
await shootPage("03-claude-code-thinking-no-off");
await page.keyboard.press("Escape");

await pick("接口协议", "OpenAI 兼容");
await shootEditor("04-claude-code-wrong-protocol");

await newProfile();
await pick("Agent", "Codex CLI");
await editor().getByRole("radio", { name: "官方登录" }).check();
await shootEditor("05-codex-official-login");

await newProfile();
await editor().getByRole("button", { name: "自定义", exact: true }).click();
await editor().getByRole("combobox", { name: "模型" }).fill("some-new-model");
await pick("思考强度", "超高");
await shootEditor("06-unknown-model-max-output-hint");

await page.goto(url);
await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "设置", exact: true }).click();
await page.getByRole("button", { name: "检查更新" }).click();
const window = page.getByRole("dialog", { name: "Agent 更新" });
await window.getByRole("listitem").nth(2).waitFor();
await shootPage("07-updates");
await window.getByRole("listitem", { name: "Codex CLI" }).getByRole("button", { name: "检查" }).click();
await window.getByText(/最新 \d/).first().waitFor();
await shootPage("08-updates-checked");
await window.getByRole("button", { name: "全部更新" }).click();
await window.getByText("已是最新").nth(2).waitFor();
await shootPage("09-updates-all-done");

await browser.close();
