// Shared E2E helpers: seed the fake backend and move around the app.
import { type APIRequestContext, type Page, expect } from "@playwright/test";

export const API = "http://127.0.0.1:8765";
export const AUTH = { Authorization: "Bearer e2e" };
export const VIDEOS = ["BV1xJYT6EEYc", "BV1bZhQ6VEQK"];

/** Create the sample items once per backend run (a second file gets 409 and reuses them). */
export async function seed(request: APIRequestContext): Promise<string[]> {
  const ids: string[] = [];
  for (const bv of VIDEOS) {
    const created = await request.post(`${API}/api/items`, {
      headers: AUTH,
      data: { url: `https://www.bilibili.com/video/${bv}/`, figures: false },
    });
    ids.push((await created.json()).id);
  }
  for (const id of ids) {
    await expect
      .poll(async () => (await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json()).status, {
        timeout: 20_000,
      })
      .toBe("done");
  }
  return ids;
}

export const sidebar = (page: Page) => page.getByRole("navigation", { name: "主导航" });

export async function openTab(page: Page, label: string) {
  await sidebar(page).getByRole("button", { name: label, exact: true }).click();
}

export async function openFirstItem(page: Page) {
  await page.getByRole("list", { name: "分类" }).getByRole("button").first().click();
  await page.getByRole("list", { name: "条目" }).getByRole("button").first().click();
  await expect(page.getByRole("toolbar", { name: "阅读" })).toBeVisible();
}

export const report = (page: Page) => page.frameLocator('iframe[title="精读报告"]');

/** Evaluate inside the report frame (srcdoc, sandboxed). */
export async function inReport<T>(page: Page, fn: () => T): Promise<T> {
  // Right after opening an item (or a reload) the srcdoc frame may not be attached yet.
  await expect.poll(() => page.frames().some((f) => f.url() === "about:srcdoc"), { timeout: 10_000 }).toBe(true);
  const frame = page.frames().find((f) => f.url() === "about:srcdoc");
  if (!frame) throw new Error("report frame not found");
  return frame.evaluate(fn);
}

/** Wait until page transitions (the lists swap through a view transition) have finished. */
export async function settle(page: Page) {
  await page.waitForFunction(() => document.getAnimations().length === 0);
}
