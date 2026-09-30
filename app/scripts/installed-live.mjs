// E8 / E3 (PLAN 15.4.16): drive the INSTALLED app's own window through WebView2's debugging port.
// Submits a real video from the console (所有三样, the settings' depth and figures), waits for it, then
// screenshots the reader's three tabs. Started by scripts/acceptance/installed-live.ps1.
//   node scripts/installed-live.mjs <cdp url> <api base> <token> <video url> <shots dir>
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [cdp, api, token, video, shots] = process.argv.slice(2);
mkdirSync(shots, { recursive: true });
const videoId = video.match(/BV[0-9A-Za-z]{10}/)[0];
const auth = { Authorization: `Bearer ${token}` };
const log = (...parts) => console.log(new Date().toISOString().slice(11, 19), ...parts);

const browser = await chromium.connectOverCDP(cdp);
const context = browser.contexts()[0];
let page = context.pages()[0];
for (let i = 0; !page && i < 60; i += 1) {
  await new Promise((resolve) => setTimeout(resolve, 1000));
  page = context.pages()[0];
}
if (!page) throw new Error("the app window never showed a page");
await page.setViewportSize({ width: 1440, height: 900 }).catch(() => undefined);
const shot = async (name) => {
  await page.mouse.move(0, 0);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(shots, `${name}.png`) });
  log("saved", name);
};
const circle = (name) => page.getByRole("group", { name: "生成哪些" }).getByRole("button", { name, exact: true });

await circle("精读").waitFor({ timeout: 60_000 });
const state = {};
for (const name of ["精读", "字幕", "导图"]) state[name] = await circle(name).getAttribute("aria-pressed");
state.depth = await page.getByRole("radiogroup", { name: "精读详细程度" }).getByRole("radio", { checked: true }).innerText();
state.figures = await page.getByRole("switch", { name: "配图" }).getAttribute("aria-checked");
log("console as it opened:", JSON.stringify(state));
if (!(state.精读 === "true" && state.字幕 === "true" && state.导图 === "true")) throw new Error("not all three ticked");
await page.getByRole("textbox", { name: "视频链接" }).fill(video);
await shot("01-console-before-start");
await page.getByRole("button", { name: "开始" }).click();
await page.locator(".queue-row", { hasText: videoId }).waitFor({ timeout: 30_000 });
await page.waitForTimeout(5000);
await shot("02-console-running");

let row = null;
let seen = "";
const deadline = Date.now() + 120 * 60_000;
while (Date.now() < deadline) {
  const rows = await (await fetch(`${api}/api/queue`, { headers: auth })).json();
  row = rows.find((candidate) => candidate.video_id.startsWith(videoId)) ?? null;
  const now = row ? `${row.status} ${row.stage ?? ""} ${row.stage_detail ?? ""}` : "missing";
  if (now !== seen) log(now);
  seen = now;
  if (row && ["done", "failed", "cancelled"].includes(row.status)) break;
  await new Promise((resolve) => setTimeout(resolve, 5000));
}
if (!row || row.status !== "done") {
  await shot("03-console-ended");
  writeFileSync(join(shots, "result.json"), JSON.stringify(row, null, 2));
  throw new Error(`the video did not finish: ${row && row.status} ${row && row.error_message}`);
}
await page.reload();
await page.locator(".queue-row", { hasText: videoId }).getByRole("button", { name: "打开" }).click();
await page.getByRole("toolbar", { name: "阅读" }).waitFor();
for (const [index, name] of ["精读", "导图", "字幕"].entries()) {
  await page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name }).click();
  await page.waitForTimeout(3500);
  await shot(`${String(index + 4).padStart(2, "0")}-reader-${name}`);
}
writeFileSync(join(shots, "result.json"), JSON.stringify(row, null, 2));
log("done", row.id);
process.exit(0); // leave the app's window open: the script closes it properly, as a user would
