// 控制台 (PLAN 9 / 15.4.5): paste a Bilibili or YouTube link, watch the queue.
import { type CSSProperties, type FormEvent, useEffect, useState } from "react";

import { ApiError, type ItemRow, api, itemTitle } from "../../shared/api";
import { useNav } from "../../shared/NavContext";
import { ScrollArea } from "../../shared/ScrollArea";
import { STAGES, stageText } from "./stages";

const STATUS: Record<ItemRow["status"], string> = {
  queued: "排队中",
  running: "进行中",
  done: "已完成",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "已中断",
};

const ADD_ERRORS: Record<string, string> = {
  URL_UNSUPPORTED: "只支持 B 站和 YouTube 的视频链接。",
};

export function ConsolePage({ queue, reload }: { queue: ItemRow[]; reload: () => Promise<void> }) {
  const [url, setUrl] = useState("");
  const [figures, setFigures] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.settings().then((s) => setFigures(s.figures_default)).catch(() => undefined);
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      await api.addItem(url.trim(), figures);
      setUrl("");
      await reload();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setMessage("这个视频已经在库里了。");
      else setMessage((error instanceof ApiError && error.code && ADD_ERRORS[error.code]) || "添加失败，请检查链接。");
    }
  };

  const active = queue.filter((row) => row.status !== "done");
  const finished = queue.filter((row) => row.status === "done");

  return (
    <ScrollArea>
      <div className="page">
        <div className="page-head">
          <div>
            <h1>控制台</h1>
            <p>粘贴视频链接，生成精读报告、思维导图和字幕，自动放进知识库。</p>
          </div>
        </div>
        <form className="importer card" onSubmit={submit}>
          <input
            className="input"
            aria-label="视频链接"
            placeholder="https://www.bilibili.com/video/BV… 或 https://www.youtube.com/watch?v=…"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          <label className="switch-label">
            <button
              type="button"
              role="switch"
              className="switch"
              aria-checked={figures}
              aria-label="配图"
              onClick={() => setFigures(!figures)}
            />
            配图
          </label>
          <button type="submit" className="btn primary" disabled={!url.trim()}>
            开始
          </button>
        </form>
        {message && (
          <p className="notice danger" role="alert" style={{ marginTop: 10 }}>
            {message}
          </p>
        )}

        <section className="section">
          <h2>任务</h2>
          {active.length === 0 && <p className="muted">没有进行中的任务。</p>}
          <ul className="queue">
            {active.map((row) => (
              <QueueRow key={row.id} row={row} reload={reload} />
            ))}
          </ul>
        </section>

        {finished.length > 0 && (
          <section className="section">
            <h2>最近完成</h2>
            <ul className="queue">
              {finished.map((row) => (
                <QueueRow key={row.id} row={row} reload={reload} />
              ))}
            </ul>
          </section>
        )}
      </div>
    </ScrollArea>
  );
}

/** A failed row (PLAN 15.4.10): the step, why, what to do; the original error folded under 「详情」. */
function Failure({ row }: { row: ItemRow }) {
  const [copied, setCopied] = useState(false);
  const step = STAGES.find(([id]) => id === row.stage)?.[1];
  const copy = () =>
    navigator.clipboard.writeText(row.error_message ?? "").then(
      () => setCopied(true),
      () => undefined, // no clipboard: the text itself can still be selected
    );
  return (
    <div className="queue-failure">
      <span className="queue-error">
        {step ? `在「${step}」这一步失败：` : "失败："}
        {row.error_reason}
      </span>
      <span className="queue-action">怎么办：{row.error_action}</span>
      <details className="queue-details">
        <summary>详情</summary>
        <pre>{row.error_message}</pre>
        <button type="button" className="btn small quiet" onClick={copy}>
          {copied ? "已复制" : "复制"}
        </button>
      </details>
    </div>
  );
}

function QueueRow({ row, reload }: { row: ItemRow; reload: () => Promise<void> }) {
  const { go } = useNav();
  const index = STAGES.findIndex(([id]) => id === row.stage);
  const progress = row.status === "done" ? 1 : index < 0 ? 0 : index / STAGES.length;
  const act = (action: () => Promise<unknown>) => async () => {
    await action();
    await reload();
  };
  return (
    <li className="queue-row card" data-status={row.status}>
      <div className="queue-main">
        <span className="queue-title">{itemTitle(row)}</span>
        <span className="muted queue-url">{row.source_url}</span>
        {row.status === "running" && (
          <span className="queue-stage">
            {stageText(row)}
            <span className="muted">
              {" "}
              · {Math.max(index, 0) + 1}/{STAGES.length}
            </span>
          </span>
        )}
        {row.status === "failed" && row.error_reason ? (
          <Failure row={row} />
        ) : (
          row.error_message && <span className="queue-error">{row.error_message}</span>
        )}
        {row.notice && <span className="muted">{row.notice}</span>}
        <span className="progress" style={{ "--p": progress } as CSSProperties} aria-hidden="true" />
      </div>
      <div className="queue-side">
        <span className={`badge ${row.status === "failed" ? "danger" : row.status === "done" ? "accent" : ""}`}>
          {STATUS[row.status]}
        </span>
        {(row.status === "queued" || row.status === "running") && (
          <button type="button" className="btn small quiet" onClick={act(() => api.cancelItem(row.id))}>
            取消
          </button>
        )}
        {(row.status === "failed" || row.status === "cancelled" || row.status === "interrupted") && (
          <button type="button" className="btn small" onClick={act(() => api.retryItem(row.id))}>
            重试
          </button>
        )}
        {row.status === "done" && (
          <button
            type="button"
            className="btn small"
            onClick={() => {
              go({ type: "tab", tab: "library" });
              go({ type: "category", categoryId: row.category_id });
              go({ type: "item", itemId: row.id });
            }}
          >
            打开
          </button>
        )}
      </div>
    </li>
  );
}
