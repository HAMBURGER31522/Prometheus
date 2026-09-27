import { describe, expect, it } from "vitest";

import { REPORT_TOKENS, reportThemeVars, themeReport } from "./theme";

const REPORT = `<!doctype html><html><head><style>:root{--paper:#fff}</style></head><body><main class="paper">正文</main></body></html>`;

describe("report theme (PLAN 15.4.5: injected at display time, file untouched)", () => {
  it("adds the override after the report's own styles", () => {
    const themed = themeReport(REPORT, { "--paper": "wheat" });
    expect(themed.indexOf('id="prometheus-theme"')).toBeGreaterThan(themed.indexOf(":root{--paper:#fff}"));
    expect(themed.indexOf('id="prometheus-theme"')).toBeLessThan(themed.indexOf("</head>"));
    expect(themed).toContain("--paper: wheat;");
    expect(themed).toContain('<main class="paper">正文</main>');
  });

  it("brings the floating scrollbar along", () => {
    const themed = themeReport(REPORT, {});
    expect(themed).toContain("::-webkit-scrollbar");
    expect(themed).toContain("data-scrolling");
  });

  it("works on a report without a head", () => {
    const themed = themeReport("<p>片段</p>", { "--ink": "black" });
    expect(themed).toContain('id="prometheus-theme"');
    expect(themed).toContain("<p>片段</p>");
  });

  it("maps every report variable to an app token", () => {
    const vars = reportThemeVars((token) => `value-of-${token}`);
    expect(Object.keys(vars).sort()).toEqual(Object.keys(REPORT_TOKENS).sort());
    expect(vars["--paper"]).toBe("value-of---report-paper");
  });
});
