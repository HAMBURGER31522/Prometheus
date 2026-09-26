// Console: multi-line import + figures toggle + live queue (PLAN 9.3).

import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "../../shared/api";
import type { ItemRow } from "../../shared/api";

const STAGE_NAMES: Record<string, string> = {
  resolve: "解析", download: "下载", transcribe: "转写", transcript: "整理转写",
  frames: "抽帧", report: "写作", finalize: "定稿", mindmap: "导图", classify: "归类",
};

export default function ConsolePage() {
  const [text, setText] = useState("");
  const [figures, setFigures] = useState(false);
  const [queue, setQueue] = useState<ItemRow[]>([]);
  const [notice, setNotice] = useState("");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    api.getSettings().then(
      (settings) => setFigures(settings.figures_default),
      () => undefined,
    );
    const poll = () => {
      api.getQueue().then(setQueue, () => undefined);
    };
    poll();
    timer.current = window.setInterval(poll, 1000);
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current);
    };
  }, []);

  const import_ = async () => {
    setNotice("");
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    for (const line of lines) {
      try {
        await api.postItem(line, figures);
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) {
          setNotice(`已存在：${line}`);
        } else if (e instanceof ApiError && e.status === 422) {
          setNotice(`链接不支持：${line}`);
        } else {
          setNotice(`导入失败：${line}`);
        }
        return;
      }
    }
    setText("");
  };

  return (
    <section className="console">
      <h2>控制台</h2>
      <textarea
        rows={4}
        placeholder="粘贴 B 站或 YouTube 链接，每行一个"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <label className="figures-toggle">
        <input
          type="checkbox"
          checked={figures}
          onChange={(e) => setFigures(e.target.checked)}
        />
        配图
      </label>
      <button type="button" className="primary" onClick={import_}>导入</button>
      {notice && <p className="notice">{notice}</p>}
      <ul className="queue" aria-label="任务队列">
        {queue.map((item) => (
          <QueueRow key={item.id} item={item} />
        ))}
        {queue.length === 0 && <li className="empty">队列为空</li>}
      </ul>
    </section>
  );
}

function QueueRow(props: { item: ItemRow }) {
  const item = props.item;
  const stage = item.status === "running" && item.stage
    ? STAGE_NAMES[item.stage] ?? item.stage
    : "";
  return (
    <li>
      <span className="row-main">
        {item.report_title || item.source_title || item.source_url}
        <span className="row-sub">
          {item.status === "running" ? `正在${stage}` : STATUS_NAMES[item.status] ?? item.status}
          {item.status === "failed" && item.error_message ? ` · ${item.error_message}` : ""}
        </span>
      </span>
      <span className="row-actions">
        {(item.status === "queued" || item.status === "running") && (
          <button type="button" onClick={() => api.cancelItem(item.id)}>取消</button>
        )}
        {(item.status === "failed" || item.status === "cancelled" || item.status === "interrupted") && (
          <button type="button" onClick={() => api.retryItem(item.id)}>重试</button>
        )}
        {item.status === "done" && <span>完成</span>}
      </span>
    </li>
  );
}

const STATUS_NAMES: Record<string, string> = {
  queued: "排队中", running: "进行中", done: "完成", failed: "失败",
  cancelled: "已取消", interrupted: "已中断",
};
