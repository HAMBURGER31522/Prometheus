// PLAN 15.4.16: what the installed app's first launch looked like — no place for the library chosen, and a
// page that started before its backend (the settings it asked for once never came).
import { type Page, expect, test } from "@playwright/test";

import { API } from "./helpers";

const SUGGESTED = "D:\\Users\\me\\Documents\\Prometheus 知识库";

/** The backend as a first launch sees it: no data dir until one is chosen. */
async function firstLaunch(page: Page) {
  const state = { chosen: null as string | null, refused: 0 };
  await page.route(`${API}/api/app/data-dir`, async (route) => {
    if (route.request().method() === "PUT") {
      state.chosen = route.request().postDataJSON().data_dir;
      return route.fulfill({ json: { data_dir: state.chosen } });
    }
    return route.fulfill({ json: { data_dir: state.chosen, suggested: SUGGESTED } });
  });
  return state;
}

test("第一次打开：先选知识库放在哪里，用推荐的位置就进入应用", async ({ page }) => {
  const state = await firstLaunch(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "选择知识库放在哪里" })).toBeVisible();
  await expect(page.getByText(SUGGESTED)).toBeVisible();
  await expect(page.getByRole("navigation", { name: "主导航" })).toHaveCount(0);
  await page.getByRole("button", { name: "用这个位置" }).click();
  await expect.poll(() => state.chosen).toBe(SUGGESTED);
  await expect(page.getByRole("heading", { name: "控制台" })).toBeVisible();
});

test("后台还没起来：先显示正在启动，起来以后照常进入", async ({ page }) => {
  let refused = 0;
  await page.route(`${API}/api/app/data-dir`, async (route) => {
    if (refused < 4) {
      refused += 1;
      return route.abort("connectionrefused");
    }
    return route.fallback();
  });
  await page.goto("/");
  await expect(page.getByText("正在启动")).toBeVisible();
  await expect(page.getByRole("heading", { name: "控制台" })).toBeVisible({ timeout: 15_000 });
});

test("设置第一次没取到：控制台的详细程度照样跟上设置", async ({ page }) => {
  let refused = 0;
  await page.route(`${API}/api/settings`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    if (refused < 2) {
      refused += 1;
      return route.abort("connectionrefused");
    }
    const response = await route.fetch();
    const settings = await response.json();
    await route.fulfill({ response, json: { ...settings, report: { ...settings.report, depth: "standard" } } });
  });
  await page.goto("/");
  const depth = page.getByRole("radiogroup", { name: "精读详细程度" });
  await expect(depth.getByRole("radio", { name: "标准" })).toHaveAttribute("aria-checked", "true", { timeout: 15_000 });
});
