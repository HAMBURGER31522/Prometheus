// 字幕 (PLAN 15.4.5, 15.4.6): every segment in order, `[时:分:秒] 原文`, virtualised for long
// videos. The corrected text is the default; 「原始识别」 shows what the ASR produced.
import { useVirtualizer } from "@tanstack/react-virtual";
import { type CSSProperties, useEffect, useRef, useState } from "react";

import { type ReaderProps } from "../../shared/LibraryPage";
import { type Segment, api, itemTitle } from "../../shared/api";
import { clock, momentLink, sourceLabel } from "../../shared/format";
import { downloadText, openExternal } from "../../shared/platform";
import { ScrollArea } from "../../shared/ScrollArea";
import { ReaderTools, ZoomControls, useZoom } from "../../shared/ReaderTools";

const ROW_ESTIMATE = 44;

export function SubtitleView({ item }: ReaderProps) {
  const [variant, setVariant] = useState<"fixed" | "raw">("fixed");
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const { zoom } = useZoom();

  useEffect(() => {
    let alive = true;
    setSegments(null);
    api
      .subtitle(item.id, variant)
      .then((rows) => alive && setSegments(rows))
      .catch(() => alive && setSegments([]));
    return () => {
      alive = false;
    };
  }, [item.id, variant]);

  const rows = segments ?? [];
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW_ESTIMATE,
    overscan: 12,
    // Without layout (tests, first paint) show every row rather than none.
    initialRect: { width: 800, height: 100_000 },
  });

  const exportAs = async (format: "srt" | "txt") =>
    downloadText(`${itemTitle(item)} 字幕.${format}`, await api.subtitleText(item.id, format, variant));

  return (
    <div className="subtitles" style={{ "--reader-zoom": zoom } as CSSProperties}>
      <ReaderTools>
        <ZoomControls />
      </ReaderTools>
      <div className="subtitle-bar">
        {item.transcript_source && <span className="badge">来源：{sourceLabel(item.transcript_source)}</span>}
        {item.subtitle_status === "ok" && variant === "fixed" && <span className="badge accent">已纠错</span>}
        {item.subtitle_status === "failed" && <span className="badge danger">纠错未完成，显示原文</span>}
        {item.notice && <span className="notice">{item.notice}</span>}
        <span className="spacer" />
        <label className="switch-label">
          <button
            type="button"
            role="switch"
            className="switch"
            aria-checked={variant === "raw"}
            aria-label="原始识别"
            onClick={() => setVariant(variant === "raw" ? "fixed" : "raw")}
          />
          原始识别
        </label>
        <button type="button" className="btn small" onClick={() => exportAs("srt")}>
          导出 SRT
        </button>
        <button type="button" className="btn small" onClick={() => exportAs("txt")}>
          导出 TXT
        </button>
      </div>
      <ScrollArea className="subtitle-scroll" ref={scroller}>
        {segments === null && <p className="empty">正在打开字幕…</p>}
        {segments !== null && rows.length === 0 && <p className="empty">这个条目没有字幕。</p>}
        <ul aria-label="字幕" className="subtitle-list" style={{ height: virtual.getTotalSize() }}>
          {virtual.getVirtualItems().map((row) => {
            const segment = rows[row.index];
            return (
              <li
                key={row.key}
                data-index={row.index}
                ref={virtual.measureElement}
                className="subtitle-row"
                style={{ transform: `translateY(${row.start}px)` }}
              >
                <button
                  type="button"
                  className="subtitle-time"
                  onClick={() => openExternal(momentLink(item.platform, item.video_id, segment.start))}
                >
                  {clock(segment.start)}
                </button>
                <span className="subtitle-text">{segment.text}</span>
              </li>
            );
          })}
        </ul>
      </ScrollArea>
    </div>
  );
}
