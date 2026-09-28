// E13 ② (PLAN 15.4.10 「导入失败写明原因」): a failed row says in which step it failed, why, and
// what to do; 「详情」 holds the original error text, folded, and it can be copied.
import { expect, test } from "@playwright/test";

import { API, AUTH, openTab } from "./helpers";

// In fake mode this Bilibili link fails in the download stage with Bilibili's HTTP 412 (fake/pipeline.py).
const RISK_CONTROL_VIDEO = "BV412RiskCtl";

test("下载阶段遇到 B 站 412 风控：写明哪一步、原因、怎么办，详情里是原始报错，可以复制", async ({ page, request, context }) => {
  const created = await request.post(`${API}/api/items`, {
    headers: AUTH,
    data: { url: `https://www.bilibili.com/video/${RISK_CONTROL_VIDEO}/`, figures: false },
  });
  const id = (await created.json()).id as string;
  await expect
    .poll(async () => (await (await request.get(`${API}/api/items/${id}`, { headers: AUTH })).json()).status, {
      timeout: 20_000,
    })
    .toBe("failed");

  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await openTab(page, "控制台");
  const row = page.locator(".queue-row", { hasText: RISK_CONTROL_VIDEO });
  await expect(row).toContainText("在「下载」这一步失败：B 站暂时拒绝了请求");
  await expect(row).toContainText("怎么办：");

  const original = row.locator("details pre");
  await expect(original).toBeHidden();
  await row.locator("details summary", { hasText: "详情" }).click();
  await expect(original).toBeVisible();
  await expect(original).toContainText(
    `ERROR: [BiliBili] ${RISK_CONTROL_VIDEO}: Unable to download webpage: HTTP Error 412: Precondition Failed`,
  );

  await row.getByRole("button", { name: "复制" }).click();
  await expect(row.getByRole("button", { name: "已复制" })).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toBe(await original.innerText());
});

test("改版前失败的条目照常显示原来的报错，新的条目按阶段写明", async ({ page }) => {
  const base = {
    platform: "bilibili", source_title: null, uploader: null, duration_s: null, report_title: null,
    category_id: null, figures: 0, status: "failed", mindmap_status: null, subtitle_status: null,
    created_at: "2026-09-28T00:00:00+00:00", finished_at: "2026-09-28T00:01:00+00:00", library_path: null,
    tags: null, description: null, transcript_source: null, notice: null, files_missing: false,
  };
  const legacyMessage = "模型调用失败：请在「设置 · 模型」里点「测试模型」，检查 Key、模型名和网络；中转站超时可以稍后重试。（Request timed out.）";
  const rows = [
    {
      ...base, id: "legacy", video_id: "BV1old0000000", source_url: "https://www.bilibili.com/video/BV1old0000000/",
      stage: null, error_code: "EXTERNAL_MODEL_FAILURE", error_message: legacyMessage, error_reason: null, error_action: null,
    },
    {
      ...base, id: "fresh", video_id: "BV1new0000000", source_url: "https://www.bilibili.com/video/BV1new0000000/",
      stage: "report", error_code: "MODEL_TIMEOUT", error_message: "PiError: Request timed out.",
      error_reason: "模型没有回应（超时或连不上）。", error_action: "检查网络和接口地址后重试。",
    },
  ];
  await page.route("**/api/queue", (route) => route.fulfill({ json: rows }));
  await page.goto("/");
  await openTab(page, "控制台");

  const legacy = page.locator(".queue-row", { hasText: "BV1old0000000" });
  await expect(legacy).toContainText(legacyMessage);
  await expect(legacy).not.toContainText("怎么办");
  const fresh = page.locator(".queue-row", { hasText: "BV1new0000000" });
  await expect(fresh).toContainText("在「写精读报告」这一步失败：模型没有回应（超时或连不上）。");
  await expect(fresh).toContainText("怎么办：检查网络和接口地址后重试。");
});
