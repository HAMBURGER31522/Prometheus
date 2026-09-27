// 精读 (PLAN 15.4.5): the report on its light paper inside the app's palette. The HTML is
// fetched, themed and shown through srcdoc in a sandbox without allow-same-origin, so the
// report's own scripts run in an opaque origin and cannot reach the app or its token.
import { useEffect, useState } from "react";

import { type ReaderProps } from "../../shared/LibraryPage";
import { api } from "../../shared/api";
import { openExternal } from "../../shared/platform";
import { reportThemeVars, themeReport } from "./theme";

export function ReportView({ item }: ReaderProps) {
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setHtml(null);
    setFailed(false);
    api
      .reportHtml(item.id)
      .then((text) => {
        const style = getComputedStyle(document.documentElement);
        const vars = reportThemeVars((token) => style.getPropertyValue(token).trim());
        if (alive) setHtml(themeReport(text, vars));
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [item.id]);

  useEffect(() => {
    // The backend injects a click handler that posts external links here (PLAN 9.3).
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string; href?: string };
      if (data?.type === "open-external" && typeof data.href === "string" && /^https?:/.test(data.href)) {
        void openExternal(data.href);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  if (failed) return <p className="empty">报告还没有生成。</p>;
  if (html === null) return <p className="empty">正在打开报告…</p>;
  return (
    <iframe
      className="report-frame"
      title="精读报告"
      sandbox="allow-scripts allow-popups"
      srcDoc={html}
    />
  );
}
