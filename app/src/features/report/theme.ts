// Stub (R7 red).
export const REPORT_TOKENS: Record<string, string> = {};

export function reportThemeVars(_read: (token: string) => string): Record<string, string> {
  return {};
}

export function themeReport(html: string, _vars: Record<string, string>): string {
  return html;
}
