// E17 ③ (PLAN 15.4.15) on the real preview data, through the app's own pages. THIS STARTS REAL RUNS on the
// active model profile (the user chose Codex official login, gpt-6-luna 超高, 2026-09-30). One step per call:
//   node scripts/acceptance/r7h-live.mjs <app url with ?port=&token=> <out dir> <step> [video]
//   steps: subtitles  — submit the video with only 「字幕」 ticked
//          fill       — open it, 精读 tab: 「标准」, figures on, 「现在生成」 (the report and its map)
//          reportmap  — submit the video with 「精读」「导图」 (「标准」, figures off), no 「字幕」
//          shots      — screenshots of the reader's three tabs as they are now (never starts anything)
// Screenshots never show a key: none of these pages has one.
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [url, out, step, video = "BV1EJ4m1t7Zs"] = process.argv.slice(2);
const link = `https://www.bilibili.com/video/${video}`;
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const settle = () => page.waitForFunction(() => document.getAnimations().length === 0);
const shot = async (name) => {
  await page.mouse.move(0, 0);
  await settle();
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(out, `${name}.png`) });
  console.log("saved", name);
};
const circle = (name) => page.getByRole("group", { name: "生成哪些" }).getByRole("button", { name, exact: true });
const pressed = async (name) => (await circle(name).getAttribute("aria-pressed")) === "true";
const tab = (name) => page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name });

/** Tick exactly these circles (clicks follow the console's own rules: 导图 brings 精读). */
async function choose(wanted) {
  for (const name of ["导图", "精读", "字幕"]) {
    if (!wanted.includes(name) && (await pressed(name))) await circle(name).click();
  }
  for (const name of ["精读", "字幕", "导图"]) {
    if (wanted.includes(name) && !(await pressed(name))) await circle(name).click();
  }
  for (const name of ["精读", "字幕", "导图"]) {
    if ((await pressed(name)) !== wanted.includes(name)) throw new Error(`could not set ${name}`);
  }
}

async function submit(wanted, depth, figures, name) {
  await page.goto(url);
  await circle("精读").waitFor();
  await choose(wanted);
  if (wanted.includes("精读")) {
    await page.getByRole("radiogroup", { name: "精读详细程度" }).getByRole("radio", { name: depth }).click();
    const on = (await page.getByRole("switch", { name: "配图" }).getAttribute("aria-checked")) === "true";
    if (on !== figures) await page.getByRole("switch", { name: "配图" }).click();
  }
  await page.getByRole("textbox", { name: "视频链接" }).fill(link);
  await shot(`${name}-before-start`);
  await page.getByRole("button", { name: "开始" }).click();
  await page.locator(".queue-row", { hasText: video }).waitFor();
  await page.waitForTimeout(4000);
  await shot(`${name}-running`);
}

async function openItem() {
  await page.goto(url);
  await page.locator(".queue-row", { hasText: video }).getByRole("button", { name: "打开" }).click();
  await page.getByRole("toolbar", { name: "阅读" }).waitFor();
}

if (step === "subtitles") {
  await submit(["字幕"], "标准", false, "20-subtitles");
} else if (step === "reportmap") {
  await submit(["精读", "导图"], "标准", false, "40-report-map");
} else if (step === "fill") {
  await openItem();
  await tab("精读").click();
  await page.getByText("这个视频没有生成精读。").waitFor();
  await page.getByRole("radiogroup", { name: "精读详细程度" }).getByRole("radio", { name: "标准" }).click();
  if ((await page.getByRole("switch", { name: "配图" }).getAttribute("aria-checked")) !== "true") {
    await page.getByRole("switch", { name: "配图" }).click();
  }
  await shot("30-fill-before");
  await page.getByRole("button", { name: "现在生成" }).click();
  await page.getByText("正在生成：").waitFor();
  await shot("31-fill-running");
} else if (step === "shots") {
  const prefix = process.argv[6] ?? "50";
  await openItem();
  for (const [index, name] of ["精读", "导图", "字幕"].entries()) {
    await tab(name).click();
    await page.waitForTimeout(2500);
    await shot(`${prefix}-${index + 1}-${name}`);
  }
} else {
  throw new Error(`unknown step: ${step}`);
}
await browser.close();
