// E13 ② (PLAN 15.4.10): 设置 · 模型 — one border on the dropdowns, platform presets, six thinking
// levels, saved keys never shown, the model list says why it failed, 「高级」 limits.
import { type Page, expect, test } from "@playwright/test";

import { API, AUTH, openTab, settle } from "./helpers";

const lastOpened = (page: Page) =>
  page.evaluate(() => (window as unknown as { __lastOpenedExternal?: string }).__lastOpenedExternal);

async function newProfile(page: Page) {
  await page.goto("/");
  await openTab(page, "设置");
  await page.getByRole("button", { name: "新增配置" }).click();
  return page.getByRole("region", { name: "编辑模型配置" });
}

async function saveAll(page: Page) {
  await page.getByRole("region", { name: "编辑模型配置" }).getByRole("button", { name: "保存配置" }).click();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
}

async function savedProfile(page: Page, name: string) {
  const settings = await (await page.request.get(`${API}/api/settings`, { headers: AUTH })).json();
  return settings.llm_profiles.items.find((profile: { name: string }) => profile.name === name);
}

test("设置里的下拉框只有一层边框：外框与按钮边界重合", async ({ page }) => {
  const editor = await newProfile(page);
  const button = editor.getByRole("combobox", { name: "思考强度" });
  const wrapper = button.locator("xpath=..");
  await settle(page); // measured mid-animation, the two boxes can differ for a frame
  const inner = await button.boundingBox();
  const outer = await wrapper.boundingBox();
  for (const side of ["x", "y", "width", "height"] as const) {
    expect(Math.abs(inner![side] - outer![side])).toBeLessThanOrEqual(1);
  }
  const widths = (el: Element) => ["Top", "Right", "Bottom", "Left"].map((side) =>
    getComputedStyle(el).getPropertyValue(`border-${side.toLowerCase()}-width`));
  expect(await wrapper.evaluate(widths)).toEqual(["0px", "0px", "0px", "0px"]);
  expect(await button.evaluate(widths)).toEqual(["1px", "1px", "1px", "1px"]);
});

test("点「Kimi」后接口地址、协议和推荐模型自动填好，Key 旁可打开平台的 Key 页面", async ({ page }) => {
  const editor = await newProfile(page);
  await expect(editor.getByRole("combobox", { name: "类型" })).toHaveCount(0);
  await editor.getByRole("button", { name: "Kimi", exact: true }).click();
  await expect(editor.getByLabel("接口地址")).toHaveValue("https://api.moonshot.cn/v1");
  await expect(editor.getByRole("combobox", { name: "接口协议" })).toHaveText("OpenAI 兼容");
  await expect(editor.getByRole("combobox", { name: "模型" })).toHaveValue("kimi-k3");
  await expect(editor.getByRole("button", { name: "Kimi", exact: true })).toHaveAttribute("aria-pressed", "true");
  await editor.getByRole("button", { name: "获取 API Key ↗" }).click();
  await expect.poll(() => lastOpened(page)).toBe("https://platform.kimi.com/console/api-keys");

  await editor.getByRole("button", { name: "MiniMax", exact: true }).click();
  await expect(editor.getByLabel("接口地址")).toHaveValue("https://api.minimax.cn/anthropic");
  await expect(editor.getByRole("combobox", { name: "接口协议" })).toHaveText("Anthropic");
  await expect(editor.getByRole("button", { name: "Kimi", exact: true })).toHaveAttribute("aria-pressed", "false");
});

test("思考强度可选「超高」「最高」；目录里没有的模型全部列出并提示", async ({ page }) => {
  const editor = await newProfile(page);
  await editor.getByLabel("名称").fill("R7d 思考");
  await editor.getByRole("button", { name: "自定义", exact: true }).click();
  await editor.getByLabel("接口地址").fill(`${API}/fake-llm/v1`);
  await editor.getByRole("combobox", { name: "模型" }).fill("fake-model-a");
  await editor.getByRole("combobox", { name: "思考强度" }).click();
  const levels = page.getByRole("listbox", { name: "思考强度" }).getByRole("option");
  await expect(levels).toHaveText(["关", "低", "中", "高", "超高", "最高"]);
  await expect(editor.getByText("超高、最高只有部分模型支持")).toBeVisible();
  await levels.filter({ hasText: "最高" }).click();
  await expect(editor.getByRole("combobox", { name: "思考强度" })).toHaveText("最高");
  await saveAll(page);
  expect((await savedProfile(page, "R7d 思考")).thinking).toBe("max");
});

test("已保存的 Key 不回填：输入框为空，占位文字给出末 4 位；留空保存不改，输入新的才替换", async ({ page }) => {
  const settings = await (await page.request.get(`${API}/api/settings`, { headers: AUTH })).json();
  const profile = {
    id: "r7d-key", name: "R7d Key", kind: "custom", base_url: `${API}/fake-llm/v1`, protocol: "openai",
    api_key: "e2e", model: "fake-model-a", supports_images: false, thinking: "medium",
  };
  const items = [...settings.llm_profiles.items.filter((p: { id: string }) => p.id !== profile.id), profile];
  await page.request.put(`${API}/api/settings`, { headers: AUTH, data: { ...settings, llm_profiles: { ...settings.llm_profiles, items } } });

  await page.goto("/");
  await openTab(page, "设置");
  const card = page.getByRole("list", { name: "模型配置" }).getByRole("listitem").filter({ hasText: "R7d Key" });
  await card.getByRole("button", { name: "编辑" }).click();
  const editor = page.getByRole("region", { name: "编辑模型配置" });
  const key = editor.getByLabel("API Key", { exact: true });
  await expect(key).toHaveValue("");
  await expect(key).toHaveAttribute("placeholder", "已保存（末 4 位 e2e），留空则不修改");
  // The eye asks the backend for the saved key and shows it (user 2026-09-28, after CC Switch).
  await editor.getByRole("button", { name: "显示 API Key" }).click();
  await expect(key).toHaveValue("e2e");
  await expect(key).toHaveAttribute("type", "text");
  await editor.getByRole("button", { name: "隐藏 API Key" }).click();
  await expect(key).toHaveAttribute("type", "password");
  await key.fill("");
  // The empty field still lists models: the backend uses the saved key.
  await editor.getByRole("button", { name: "获取模型列表" }).click();
  await expect(page.getByRole("listbox", { name: "模型列表" }).getByRole("option", { name: "fake-model-b" })).toBeVisible();
  await saveAll(page);
  expect((await savedProfile(page, "R7d Key")).api_key).toBe("****e2e");

  await card.getByRole("button", { name: "编辑" }).click();
  await key.fill("sk-r7d-new-9999");
  await expect(key).toHaveValue("sk-r7d-new-9999");
  await saveAll(page);
  expect((await savedProfile(page, "R7d Key")).api_key).toBe("****9999");
});

test("获取模型列表失败时显示状态码和原因", async ({ page }) => {
  const editor = await newProfile(page);
  await editor.getByRole("button", { name: "自定义", exact: true }).click();
  await editor.getByLabel("接口地址").fill(`${API}/no-such-list/v1`);
  await editor.getByLabel("API Key", { exact: true }).fill("e2e");
  await editor.getByRole("button", { name: "获取模型列表" }).click();
  await expect(editor.getByText("获取失败（HTTP 404）：这个地址没有模型列表接口")).toBeVisible();

  await editor.getByLabel("接口地址").fill(`${API}/fake-llm/v1`);
  await editor.getByLabel("API Key", { exact: true }).fill("wrong-key");
  await editor.getByRole("button", { name: "获取模型列表" }).click();
  await expect(editor.getByText("获取失败（HTTP 401）：Key 无效或无权限")).toBeVisible();
});

test("「高级」里预填上下文窗口和最大输出，改过的数存进配置", async ({ page }) => {
  const editor = await newProfile(page);
  await editor.getByLabel("名称").fill("R7d 高级");
  await editor.getByRole("button", { name: "自定义", exact: true }).click();
  await editor.getByLabel("接口地址").fill("https://relay.example/v1");
  await editor.getByRole("combobox", { name: "接口协议" }).click();
  await page.getByRole("listbox", { name: "接口协议" }).getByRole("option", { name: "Anthropic" }).click();
  await editor.getByRole("combobox", { name: "模型" }).fill("claude-opus-4-8");
  await editor.getByText("高级", { exact: true }).click();
  await expect(editor.getByLabel("上下文窗口（token）")).toHaveValue("1000000");
  await expect(editor.getByLabel("最大输出（token）")).toHaveValue("128000");
  await editor.getByLabel("最大输出（token）").fill("64000");
  await saveAll(page);
  const saved = await savedProfile(page, "R7d 高级");
  expect(saved.max_tokens).toBe(64000);
  expect(saved.context_window).toBeNull();
});

test("DeepSeek 和智谱也能打开官方的 Key 页面", async ({ page }) => {
  const editor = await newProfile(page);
  await editor.getByRole("button", { name: "DeepSeek", exact: true }).click();
  await editor.getByRole("button", { name: "获取 API Key ↗" }).click();
  expect(await lastOpened(page)).toBe("https://platform.deepseek.com/api_keys");
  await editor.getByRole("button", { name: "智谱", exact: true }).click();
  await editor.getByRole("button", { name: "获取 API Key ↗" }).click();
  expect(await lastOpened(page)).toBe("https://bigmodel.cn/usercenter/proj-mgmt/apikeys");
});
