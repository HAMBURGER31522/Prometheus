// Subtitle tab: raw segment list, click-to-moment, SRT/TXT export (PLAN 9.3).

import { useEffect, useState } from "react";

import LibraryBrowser from "../../shared/LibraryBrowser";
import type { ContentTabProps } from "../../shared/LibraryBrowser";
import { contentUrl } from "../../shared/api";
import type { ItemRow } from "../../shared/api";
import { openExternal } from "../../shared/platform";

interface Segment {
  start: number;
  end: number;
  text: string;
}

export default function SubtitleView(props: ContentTabProps) {
  return (
    <LibraryBrowser kind="字幕" selection={props.selection} onSelect={props.onSelect}>
      {(item) => <SubtitleList item={item} key={item.id} />}
    </LibraryBrowser>
  );
}

function SubtitleList(props: { item: ItemRow }) {
  const [segments, setSegments] = useState<Segment[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    contentUrl(props.item.id, "subtitle", "json")
      .then((url) => fetch(url))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data) => {
        if (!cancelled) setSegments(data);
      })
      .catch(() => {
        if (!cancelled) setSegments(null);
      });
    return () => {
      cancelled = true;
    };
  }, [props.item.id]);

  if (segments === null) {
    return <p className="empty">字幕尚未生成</p>;
  }

  const moment = (seconds: number) => {
    const t = Math.floor(seconds);
    if (props.item.platform === "youtube") {
      return `https://www.youtube.com/watch?v=${props.item.video_id}&t=${t}s`;
    }
    const bare = props.item.video_id.split("?")[0];
    const page = /p=(\d+)/.exec(props.item.video_id)?.[1] ?? "1";
    return `https://www.bilibili.com/video/${bare}/?p=${page}&t=${t}`;
  };

  const download = async (format: "srt" | "txt") => {
    const url = await contentUrl(props.item.id, "subtitle", format);
    const response = await fetch(url);
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `subtitle.${format}`;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  };

  return (
    <div className="subtitle-wrap">
      <div className="subtitle-actions">
        <button type="button" onClick={() => download("srt")}>导出 SRT</button>
        <button type="button" onClick={() => download("txt")}>导出 TXT</button>
      </div>
      <ul className="subtitle-list">
        {segments.map((segment, index) => (
          <li key={index}>
            <button
              type="button"
              className="subtitle-time"
              onClick={() => openExternal(moment(segment.start))}
            >
              [{clock(segment.start)}]
            </button>
            <span>{segment.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function clock(seconds: number): string {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
