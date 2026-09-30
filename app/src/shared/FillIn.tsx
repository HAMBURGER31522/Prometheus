// 「没有生成」 / 「现在生成」 (PLAN 15.4.15-5): a part this video was submitted without, made now from the
// transcript it already has. Shared by 精读, 导图 and 字幕: the report and its map are made together, so a
// missing report looks the same from either tab.
import { useState } from "react";

import { type ItemRow, api } from "./api";
import { type ReaderProps } from "./LibraryPage";
import { ReportOptions, useReportChoice } from "./ReportOptions";
import { stageText } from "./stages";

/** A fill-in waits or runs on this item: the row names a step while the item stays done. */
const filling = (item: ItemRow) => item.stage !== null;

function LastTry({ item }: { item: ItemRow }) {
  if (!item.error_code) return null;
  return <p className="notice danger">上次没有生成成功：{item.error_reason ?? item.error_message}</p>;
}

function useStart(refresh: () => Promise<void>, send: () => Promise<unknown>) {
  const [sending, setSending] = useState(false);
  const start = async () => {
    setSending(true);
    try {
      await send();
      await refresh();
    } finally {
      setSending(false);
    }
  };
  return { sending, start };
}

/** No report (精读; 导图 with `map`): choose its depth and figures, then make it with its map. */
export function FillReport({ item, refresh, map = false }: ReaderProps & { map?: boolean }) {
  const choice = useReportChoice();
  const { sending, start } = useStart(refresh, () => api.fillReport(item.id, choice.depth, choice.figures));
  return (
    <div className="page fill-in">
      <p className="notice">
        {map ? "这个视频没有生成导图。导图从精读生成，会和精读一起生成。" : "这个视频没有生成精读。"}
      </p>
      <LastTry item={item} />
      {filling(item) ? (
        <p className="muted">正在生成：{stageText(item)}</p>
      ) : (
        <div className="fill-row">
          <ReportOptions choice={choice} />
          <button type="button" className="btn primary" disabled={sending} onClick={start}>
            现在生成
          </button>
        </div>
      )}
    </div>
  );
}

/** The report is there and its map is not (导图): only the map is made. */
export function FillMindmap({ item, refresh }: ReaderProps) {
  const { sending, start } = useStart(refresh, () => api.regenerateMindmap(item.id));
  return (
    <div className="page fill-in">
      <p className="notice">这个视频没有生成导图。</p>
      <button type="button" className="btn primary" disabled={sending} onClick={start}>
        现在生成
      </button>
    </div>
  );
}

/** Subtitles shown as transcribed (字幕's bar): only the correction is made. */
export function FillSubtitles({ item, refresh }: ReaderProps) {
  const { sending, start } = useStart(refresh, () => api.fillSubtitles(item.id));
  if (filling(item)) return <span className="badge accent">正在生成：{stageText(item)}</span>;
  return (
    <>
      <span className="badge">字幕没有纠错</span>
      {(item.error_code || item.subtitle_status === "failed") && (
        <span className="badge danger">上次没有生成成功{item.error_reason ? `：${item.error_reason}` : ""}</span>
      )}
      <button type="button" className="btn small" disabled={sending} onClick={start}>
        现在生成
      </button>
    </>
  );
}
