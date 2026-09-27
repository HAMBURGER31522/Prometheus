// The report keeps its light paper (the agent draws charts for white paper, D-29), but is
// shown in the app's palette: the override is injected at display time and the file on
// disk is never touched (PLAN 15.4.5). Every value comes from tokens.css at runtime.

/** Report template variable -> app token that supplies its value. */
export const REPORT_TOKENS: Record<string, string> = {
  "--paper": "--report-paper",
  "--canvas": "--report-paper",
  "--ink": "--report-ink",
  "--heading": "--report-heading",
  "--muted": "--report-muted",
  "--accent": "--report-accent",
  "--orange": "--report-orange",
  "--line": "--report-line",
  "--blue": "--report-blue",
  "--blue-wash": "--report-blue-wash",
  "--wash": "--report-wash",
  "--p-around": "--window",
  "--p-shadow": "--report-shadow",
  "--p-bar-from": "--report-bar-from",
  "--p-bar-to": "--report-bar-to",
  "--p-serif": "--font-serif",
  "--p-thumb": "--scroll-thumb",
  "--p-thumb-idle": "--scroll-thumb-idle",
};

export function reportThemeVars(read: (token: string) => string): Record<string, string> {
  return Object.fromEntries(Object.entries(REPORT_TOKENS).map(([name, token]) => [name, read(token)]));
}

const RULES = `
html, body { background: var(--p-around); }
.paper { box-shadow: var(--p-shadow); }
.paper:before, .paper:after { background: linear-gradient(90deg, var(--p-bar-from), var(--p-bar-to)); }
h1, h2, h3, .subtitle, .report-nav-title { font-family: var(--p-serif); }
::-webkit-scrollbar { width: 12px; height: 12px; background: transparent; }
::-webkit-scrollbar-thumb {
  border: 4px solid transparent; border-radius: 12px; background-clip: padding-box;
  background-color: var(--p-thumb-idle);
}
::-webkit-scrollbar-thumb:hover,
html[data-scrolling]::-webkit-scrollbar-thumb,
html[data-scrolling] ::-webkit-scrollbar-thumb { border-width: 3px; background-color: var(--p-thumb); }
`;

// Same idle rule as the app's scroll areas: visible while scrolling, fades 800 ms after.
// In-page links (#s3 in the table of contents): a srcdoc page resolves "#s3" against the
// app's own address, so following it would load the app into the frame (a blank page).
// Scroll to the target instead.
const SCROLL_SCRIPT = `
(function () {
  var timer = 0;
  addEventListener("scroll", function () {
    document.documentElement.setAttribute("data-scrolling", "");
    clearTimeout(timer);
    timer = setTimeout(function () { document.documentElement.removeAttribute("data-scrolling"); }, 800);
  }, { passive: true, capture: true });
  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest('a[href^="#"]');
    if (!link) return;
    event.preventDefault();
    var id = decodeURIComponent(link.getAttribute("href").slice(1));
    var target = id ? document.getElementById(id) : document.documentElement;
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }, true);
})();
`;

export function themeReport(html: string, vars: Record<string, string>): string {
  const declarations = Object.entries(vars)
    .map(([name, value]) => `  ${name}: ${value};`)
    .join("\n");
  const block =
    `<style id="prometheus-theme">\n:root {\n${declarations}\n}\n${RULES}</style>\n` +
    `<script>${SCROLL_SCRIPT}</script>\n`;
  const head = html.search(/<\/head>/i);
  return head >= 0 ? html.slice(0, head) + block + html.slice(head) : block + html;
}
