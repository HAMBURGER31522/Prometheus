// E15 ③ (PLAN 15.4.13): the Agent of a model profile, what it allows, the Codex login and the
// update window, on the fake backend (Pi and Codex CLI installed, Claude Code not).
import { type Locator, type Page, expect, test } from "@playwright/test";

import { openTab } from "./helpers";

async function newProfile(page: Page): Promise<Locator> {
  await page.goto("/");
  await openTab(page, "设置");
  await page.getByRole("button", { name: "新增配置" }).click();
  return page.getByRole("region", { name: "编辑模型配置" });
}

async function pick(page: Page, editor: Locator, box: string, option: string) {
  await editor.getByRole("combobox", { name: box }).click();
  await page.getByRole("listbox", { name: box }).getByRole("option", { name: option, exact: true }).click();
}

test("选 Claude Code：只留 Anthropic 协议的平台，协议改错时当场提示、不能保存", async ({ page }) => {
  const editor = await newProfile(page);
  await expect(editor.getByRole("combobox", { name: "Agent" })).toHaveText(/Pi/);
  await pick(page, editor, "Agent", "Claude Code");
  await expect(editor.getByRole("button", { name: "DeepSeek", exact: true })).toBeDisabled();
  await expect(editor.getByRole("button", { name: "Anthropic", exact: true })).toBeEnabled();
  await expect(editor.getByRole("combobox", { name: "接口协议" })).toHaveText(/Anthropic/);
  await pick(page, editor, "接口协议", "OpenAI 兼容");
  await expect(editor.getByText("Claude Code 只接 Anthropic 协议")).toBeVisible();
  await expect(editor.getByRole("button", { name: "保存配置" })).toBeDisabled();
});

test("Claude Code 的思考强度没有「关」：变灰并写明", async ({ page }) => {
  const editor = await newProfile(page);
  await pick(page, editor, "Agent", "Claude Code");
  await editor.getByRole("combobox", { name: "思考强度" }).click();
  const off = page.getByRole("listbox", { name: "思考强度" }).getByRole("option", { name: "关", exact: true });
  await expect(off).toHaveAttribute("aria-disabled", "true");
  await page.keyboard.press("Escape");
  await expect(editor.getByText("Claude Code 没有「关」这一档，最低是「低」")).toBeVisible();
});

test("官方登录只对 Codex CLI 开放：地址、协议和 Key 变灰，换成登录按钮，登录后显示已登录", async ({ page }) => {
  const editor = await newProfile(page);
  const official = editor.getByRole("radio", { name: "官方登录" });
  await expect(official).toBeDisabled();
  await pick(page, editor, "Agent", "Codex CLI");
  await official.check();
  await expect(editor.getByRole("textbox", { name: "接口地址" })).toBeDisabled();
  await expect(editor.getByLabel("API Key", { exact: true })).toBeDisabled();
  const login = editor.getByTestId("codex-login");
  await expect(login).toContainText("未登录");
  await login.getByRole("button", { name: "登录 ChatGPT 账户" }).click();
  await expect(login).toContainText("已登录");
});

test("Agent 没装时显示「未安装」，点「安装」后显示版本", async ({ page }) => {
  const editor = await newProfile(page);
  await pick(page, editor, "Agent", "Claude Code");
  const state = editor.getByTestId("agent-state");
  await expect(state).toContainText("未安装");
  await state.getByRole("button", { name: "安装" }).click();
  await expect(state).toContainText(/已安装 \d+\.\d+\.\d+/);
});

test("检查更新窗口：三行，「检查」后显示最新版本，「全部更新」后都是最新", async ({ page }) => {
  await page.goto("/");
  await openTab(page, "设置");
  await page.getByRole("button", { name: "检查更新" }).click();
  const window = page.getByRole("dialog", { name: "Agent 更新" });
  const rows = window.getByRole("listitem");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("Pi");
  await expect(rows.nth(1)).toContainText("Codex CLI");
  await expect(rows.nth(2)).toContainText("Claude Code");
  const codex = window.getByRole("listitem", { name: "Codex CLI" });
  await codex.getByRole("button", { name: "检查" }).click();
  await expect(codex).toContainText(/最新 \d+\.\d+\.\d+/);
  await expect(codex.getByRole("button", { name: "更新" })).toBeEnabled();
  await window.getByRole("button", { name: "全部更新" }).click();
  for (const name of ["Pi", "Codex CLI", "Claude Code"]) {
    await expect(window.getByRole("listitem", { name })).toContainText("已是最新");
  }
  await window.getByRole("button", { name: "关闭" }).click();
  await expect(window).toHaveCount(0);
});

test("目录里没有的模型选了「超高」「最高」：提示去「高级」里填最大输出", async ({ page }) => {
  const editor = await newProfile(page);
  await editor.getByRole("button", { name: "自定义", exact: true }).click();
  await editor.getByRole("combobox", { name: "模型" }).fill("fake-model-a");
  const hint = editor.getByText("思考内容也算在最大输出里");
  await expect(hint).toHaveCount(0);
  await pick(page, editor, "思考强度", "超高");
  await expect(hint).toBeVisible();
});
