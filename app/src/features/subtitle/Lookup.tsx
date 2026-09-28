// 查词 (PLAN 15.4.9, 15.4.10): resting the pointer on an English word for about 300 ms opens a
// popup with the offline dictionary's phonetic, Chinese translation, base form (went → go) and
// up to three English definitions, and buttons that open the word in seven online dictionaries.
// The offline dictionary (ECDICT) is a local component downloaded on first use; one downloaded
// before English definitions offers 「更新词库」 and keeps working until then.
import { type MouseEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { ApiError, type ComponentStatus, type LookupEntry, api } from "../../shared/api";
import { openExternal } from "../../shared/platform";
import { DICTIONARIES } from "./words";

const HOVER_MS = 300;
const CLOSE_MS = 250;

type Target = { word: string; rect: DOMRect };

type State =
  | { kind: "loading" }
  | { kind: "found"; entry: LookupEntry }
  | { kind: "unknown" }
  | { kind: "no-dictionary"; detail: string }
  | { kind: "installing"; progress: number | null }
  | { kind: "failed"; detail: string };

/** Hover handlers for the words of a line, and the popup to render once. */
export function useWordLookup() {
  const [target, setTarget] = useState<Target | null>(null);
  const timers = useRef({ open: 0, close: 0 });

  const close = () => {
    window.clearTimeout(timers.current.close);
    timers.current.close = window.setTimeout(() => setTarget(null), CLOSE_MS);
  };
  useEffect(() => () => {
    window.clearTimeout(timers.current.open);
    window.clearTimeout(timers.current.close);
  }, []);

  const wordProps = (word: string) => ({
    onMouseEnter: (event: MouseEvent<HTMLElement>) => {
      const element = event.currentTarget;
      window.clearTimeout(timers.current.open);
      window.clearTimeout(timers.current.close);
      timers.current.open = window.setTimeout(() => setTarget({ word, rect: element.getBoundingClientRect() }), HOVER_MS);
    },
    onMouseLeave: () => {
      window.clearTimeout(timers.current.open);
      close();
    },
  });

  const popup = target
    ? createPortal(
        <LookupPopup
          key={target.word}
          target={target}
          onClose={() => setTarget(null)}
          onHold={(holding) => (holding ? window.clearTimeout(timers.current.close) : close())}
        />,
        document.body,
      )
    : null;
  return { wordProps, popup };
}

function LookupPopup({ target, onClose, onHold }: { target: Target; onClose: () => void; onHold: (holding: boolean) => void }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [place, setPlace] = useState({ left: target.rect.left, top: target.rect.bottom + 6 });
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    api.lookupWord(target.word).then(
      (entry) => alive && setState({ kind: "found", entry }),
      async (error: unknown) => {
        if (!alive) return;
        if (error instanceof ApiError && error.code === "DICTIONARY_NOT_INSTALLED") {
          const status: ComponentStatus | null = await api.dictionaryStatus().catch(() => null);
          if (!alive) return;
          setState(
            status?.state === "installing"
              ? { kind: "installing", progress: status.progress }
              : { kind: "no-dictionary", detail: status?.state === "failed" ? status.detail : "离线词典还没有下载，只需下载一次" },
          );
        } else if (error instanceof ApiError && error.code === "WORD_NOT_FOUND") {
          setState({ kind: "unknown" });
        } else {
          setState({ kind: "failed", detail: "查词失败，请稍后再试" });
        }
      },
    );
    return () => {
      alive = false;
    };
  }, [target.word, attempt]);

  // While the dictionary downloads, follow its progress, then look the word up again.
  useEffect(() => {
    if (state.kind !== "installing") return;
    const timer = window.setInterval(async () => {
      const status = await api.dictionaryStatus().catch(() => null);
      if (status?.state === "ready") setAttempt((count) => count + 1);
      else if (status?.state === "failed") setState({ kind: "no-dictionary", detail: status.detail });
      else if (status) setState({ kind: "installing", progress: status.progress });
    }, 500);
    return () => window.clearInterval(timer);
  }, [state.kind]);

  // Esc or scrolling the subtitles closes it.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    const onScroll = (event: Event) => !box.current?.contains(event.target as Node) && onClose();
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [onClose]);

  // Below the word, or above it when there is no room; never off the right edge.
  useLayoutEffect(() => {
    const size = box.current?.getBoundingClientRect();
    if (!size) return;
    const below = target.rect.bottom + 6;
    const top = below + size.height > window.innerHeight - 8 ? Math.max(8, target.rect.top - 6 - size.height) : below;
    const left = Math.max(8, Math.min(target.rect.left, window.innerWidth - size.width - 8));
    setPlace((current) => (current.top === top && current.left === left ? current : { top, left }));
  }, [state, target.rect]);

  const install = async () => {
    await api.installDictionary();
    setState({ kind: "installing", progress: null });
  };

  return (
    <div
      ref={box}
      role="dialog"
      aria-label="查词"
      className="lookup"
      style={place}
      onMouseEnter={() => onHold(true)}
      onMouseLeave={() => onHold(false)}
    >
      {state.kind === "loading" && <p className="muted">正在查「{target.word}」…</p>}
      {state.kind === "found" && (
        <>
          <div className="lookup-head">
            <strong data-testid="lookup-headword">{state.entry.headword}</strong>
            {state.entry.phonetic && <span className="lookup-phonetic">/{state.entry.phonetic}/</span>}
          </div>
          {state.entry.inflection && (
            <p className="lookup-form">
              {state.entry.query} 是 {state.entry.headword} 的{state.entry.inflection}
            </p>
          )}
          <ul className="lookup-senses">
            {state.entry.translation.slice(0, 6).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {state.entry.definition.length > 0 && (
            <section className="lookup-english" aria-label="英英释义">
              <p className="lookup-label">英英释义</p>
              <ul className="lookup-senses" lang="en">
                {state.entry.definition.map((line) => (
                  <li key={line} title={line}>
                    {line}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      {state.kind === "unknown" && <p className="muted">离线词典里没有「{target.word}」，可以在下面的在线词典里查。</p>}
      {state.kind === "no-dictionary" && (
        <>
          <p className="muted">{state.detail}（ECDICT，约 23MB）</p>
          <button type="button" className="btn small" onClick={install}>
            下载离线词典
          </button>
        </>
      )}
      {state.kind === "installing" && (
        <p className="muted">
          正在下载离线词典{state.progress != null ? ` ${Math.round(state.progress * 100)}%` : "…"}
        </p>
      )}
      {state.kind === "failed" && <p className="notice danger">{state.detail}</p>}
      <div className="lookup-links" aria-label="在线词典">
        {DICTIONARIES.map((dictionary) => (
          <button key={dictionary.name} type="button" className="btn small quiet" onClick={() => openExternal(dictionary.url(target.word))}>
            {dictionary.name}
          </button>
        ))}
      </div>
      {state.kind === "found" && state.entry.needs_update && (
        <div className="lookup-update">
          <span className="muted">更新词库可显示英英释义（约 23MB）</span>
          <button type="button" className="btn small" onClick={install}>
            更新词库
          </button>
        </div>
      )}
    </div>
  );
}
