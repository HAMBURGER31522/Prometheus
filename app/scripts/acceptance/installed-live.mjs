// E8 / E3 (PLAN 15.4.16): drive the INSTALLED app's own window through WebView2's debugging port.
// Submits a real video from the console (所有三样, the settings' depth and figures), waits for it, then
// screenshots the reader's three tabs. Started by scripts/acceptance/installed-live.ps1.
//   node scripts/acceptance/installed-live.mjs <cdp url> <api base> <token> <video url> <shots dir>
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
// Evidence when something goes wrong (installed run 2026-09-30: the submit went nowhere).
page.on("console", (message) => message.type() !== "debug" && log("page console", message.type(), message.text()));
page.on("requestfailed", (request) => log("request failed", request.method(), request.url(), request.failure()?.errorText));
page.on("response", (response) => {
  if (response.request().method() !== "GET") log("response", response.request().method(), response.url(), response.status());
});
log("page url", page.url());
log("fetch from the page:", await page.evaluate(async (base) => {
  try {
    return String((await fetch(`${base}/api/health`)).status);
  } catch (error) {
    return `failed: ${error}`;
  }
}, api));
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
await page.waitForTimeout(3000);
await shot("02-console-after-start");
await page.locator(".queue-row", { hasText: videoId }).waitFor({ timeout: 30_000 });
await page.waitForTimeout(5000);
await shot("03-console-running");

let row = null;
let seen = "";
const stages = [];
const deadline = Date.now() + 120 * 60_000;
while (Date.now() < deadline) {
  const rows = await (await fetch(`${api}/api/queue`, { headers: auth })).json();
  row = rows.find((candidate) => candidate.video_id.startsWith(videoId)) ?? null;
  const now = row ? `${row.status} ${row.stage ?? ""} ${row.stage_detail ?? ""}` : "missing";
  if (now !== seen) log(now);
  seen = now;
  if (row?.status === "running" && row.stage && !stages.includes(row.stage)) {
    // the console at each new step, for the README and the promo (PLAN 15.4.17)
    stages.push(row.stage);
    await shot(`03-step-${String(stages.length).padStart(2, "0")}-${row.stage}`).catch((error) => log("step shot", error));
  }
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
// Closer looks for the README and the promo (PLAN 15.4.17); a miss here does not fail the run.
const tab = (name) => page.getByRole("tablist", { name: "视图" }).getByRole("tab", { name }).click();
try {
  await tab("精读");
  await page.waitForTimeout(3000);
  await page.frameLocator(".report-frame").locator("aside.viewpoint").first().scrollIntoViewIfNeeded();
  await shot("07-reader-编者观点");
} catch (error) {
  log("viewpoint shot", error);
}
try {
  await tab("导图");
  await page.waitForTimeout(3500);
  const leaf = page.locator(".react-flow__node", { has: page.locator(".mind-detail") }).nth(2);
  for (let step = 0; step < 2; step += 1) {
    const box = await leaf.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -200);
    await page.waitForTimeout(600);
  }
  await leaf.click();
  await page.getByRole("complementary", { name: "节点摘要" }).waitFor();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(shots, "08-reader-导图-要点.png") });
  log("saved 08-reader-导图-要点");
} catch (error) {
  log("map node shot", error);
}
writeFileSync(join(shots, "result.json"), JSON.stringify(row, null, 2));
log("done", row.id);
process.exit(0); // leave the app's window open: the script closes it properly, as a user would
