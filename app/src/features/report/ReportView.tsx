// 精读 (PLAN 15.4.5, 15.4.7): the report on its light paper inside the app's palette. The HTML
// is fetched, themed and shown through srcdoc in a sandbox without allow-same-origin, so the
// report's own scripts run in an opaque origin and cannot reach the app or its token. The
// injected script reports the table of contents and follows the reading zoom.
import { useEffect, useRef, useState } from "react";

import { type ReaderProps } from "../../shared/LibraryPage";
import { ReaderTools, ZoomControls, useZoom } from "../../shared/ReaderTools";
import { api } from "../../shared/api";
import { openExternal } from "../../shared/platform";
import { reportThemeVars, themeReport } from "./theme";

type TocItem = { id: string; title: string };

export function ReportView({ item }: ReaderProps) {
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [toc, setToc] = useState<TocItem[]>([]);
  const frame = useRef<HTMLIFrameElement>(null);
  const { zoom } = useZoom();

  useEffect(() => {
    let alive = true;
    setHtml(null);
    setFailed(false);
    setToc([]);
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

  const send = (message: object) => frame.current?.contentWindow?.postMessage(message, "*");

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string; href?: string; items?: TocItem[] };
      if (data?.type === "open-external" && typeof data.href === "string" && /^https?:/.test(data.href)) {
        void openExternal(data.href); // injected by the backend (PLAN 9.3)
      } else if (data?.type === "toc" && event.source === frame.current?.contentWindow) {
        setToc(data.items ?? []);
        send({ type: "zoom", value: zoom }); // the report is ready: bring it to the reading zoom
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  });

  useEffect(() => {
    send({ type: "zoom", value: zoom });
  }, [zoom]);

  if (failed) return <p className="empty">报告还没有生成。</p>;
  if (html === null) return <p className="empty">正在打开报告…</p>;
  return (
    <>
      <ReaderTools>
        <TocMenu items={toc} onPick={(id) => send({ type: "goto", id })} />
        <ZoomControls />
      </ReaderTools>
      <iframe ref={frame} className="report-frame" title="精读报告" sandbox="allow-scripts allow-popups" srcDoc={html} />
    </>
  );
}

function TocMenu({ items, onPick }: { items: TocItem[]; onPick: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !box.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", close);
    };
  }, [open]);
  return (
    <div className="toc" ref={box}>
      <button
        type="button"
        className="btn quiet small"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={items.length === 0}
        onClick={() => setOpen(!open)}
      >
        目录
      </button>
      {open && (
        <div className="popover toc-menu" role="menu" aria-label="报告目录">
          {items.map((entry, index) => (
            <button
              key={entry.id}
              type="button"
              role="menuitem"
              onClick={() => {
                onPick(entry.id);
                setOpen(false);
              }}
            >
              <span className="toc-num">{String(index + 1).padStart(2, "0")}</span>
              {entry.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
