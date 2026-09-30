// 第一次打开 (PLAN 15.4.16): before anything else, where the library goes; and a backend that is still
// starting (the page can load first). App-wide, so it lives in shared/.
import { useEffect, useState } from "react";

import { api } from "./api";
import { pickDirectory } from "./platform";

type Startup = { phase: "starting" } | { phase: "choose"; suggested: string } | { phase: "ready" };

/** Asks the backend for its data dir until it answers. */
export function useStartup(): [Startup, () => void] {
  const [startup, setStartup] = useState<Startup>({ phase: "starting" });
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const ask = () =>
      api
        .dataDir()
        .then((answer) => {
          if (!alive) return;
          setStartup(answer.data_dir ? { phase: "ready" } : { phase: "choose", suggested: answer.suggested ?? "" });
        })
        .catch(() => {
          if (alive) timer = setTimeout(ask, 500);
        });
    ask();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, []);
  return [startup, () => setStartup({ phase: "ready" })];
}

export function Starting() {
  return (
    <div className="first-run">
      <p className="muted">正在启动…</p>
    </div>
  );
}

export function FirstRun({ suggested, onChosen }: { suggested: string; onChosen: () => void }) {
  const [error, setError] = useState("");
  const use = async (folder: string) => {
    setError("");
    try {
      await api.setDataDir(folder);
      onChosen();
    } catch {
      setError("这个文件夹用不了，换一个试试。");
    }
  };
  return (
    <div className="first-run">
      <div className="first-run-card card">
        <h1>选择知识库放在哪里</h1>
        <p className="muted">
          精读、思维导图和字幕都会放进这个文件夹，按分类分好，看文件名就知道是什么。以后可以在「设置 → 数据目录」里换。
        </p>
        <code className="path">{suggested}</code>
        <div className="row">
          <button type="button" className="btn primary" disabled={!suggested} onClick={() => use(suggested)}>
            用这个位置
          </button>
          <button
            type="button"
            className="btn"
            onClick={async () => {
              const chosen = await pickDirectory();
              if (chosen) await use(chosen);
            }}
          >
            选择其他文件夹…
          </button>
        </div>
        {error && <p className="notice danger">{error}</p>}
      </div>
    </div>
  );
}
