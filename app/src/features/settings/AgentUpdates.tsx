// 检查更新 (PLAN 15.4.13, after v2rayN's core updates): one row per Agent — installed version,
// latest version, state, 「检查」 and 「更新」 (「安装」 when missing) — and 「全部更新」. These are the
// app's own copies; the Codex CLI or Claude Code the user installed elsewhere is never touched.
import { useEffect, useState } from "react";

import { type AgentRow, api } from "../../shared/api";

function stateOf(row: AgentRow): { text: string; fresh: boolean } {
  if (!row.installed) return { text: "未安装", fresh: false };
  if (!row.latest) return { text: "未检查", fresh: false };
  return row.version === row.latest ? { text: "已是最新", fresh: false } : { text: "有新版本", fresh: true };
}

const canUpdate = (row: AgentRow) => !row.installed || (row.latest !== null && row.version !== row.latest);

export function AgentUpdates({ onClose }: { onClose: () => void }) {
  const [rows, setRows] = useState<AgentRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.agents().then(setRows).catch(() => setError("读不到 Agent 的版本"));
  }, []);
  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const run = async (action: () => Promise<AgentRow[]>, failed: string) => {
    setBusy(true);
    setError("");
    try {
      setRows(await action());
    } catch {
      setError(failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="dialog-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="dialog card" role="dialog" aria-modal="true" aria-label="Agent 更新">
        <h2>Agent 更新</h2>
        <p className="muted">这里更新的是应用自己的 Pi、Codex CLI 和 Claude Code，你电脑上另外安装的不受影响。</p>
        <ul className="agent-rows">
          {rows.map((row) => {
            const state = stateOf(row);
            return (
              <li key={row.id} aria-label={row.name} className="agent-line">
                <b>{row.name}</b>
                <span className="muted">{row.installed ? `已装 ${row.version}` : "未安装"}</span>
                <span className="muted">{row.latest ? `最新 ${row.latest}` : "最新 —"}</span>
                <span data-state={state.fresh ? "new" : undefined}>{state.text}</span>
                <button type="button" className="btn small" disabled={busy} onClick={() => run(api.checkAgents, "检查失败")}>
                  检查
                </button>
                <button
                  type="button"
                  className="btn small"
                  disabled={busy || !canUpdate(row)}
                  onClick={() => run(() => api.installAgent(row.id), `${row.name} 更新失败`)}
                >
                  {row.installed ? "更新" : "安装"}
                </button>
              </li>
            );
          })}
        </ul>
        {error && <p className="field-error">{error}</p>}
        <div className="row">
          <button type="button" className="btn primary" disabled={busy} onClick={() => run(api.updateAllAgents, "全部更新失败")}>
            {busy ? "进行中…" : "全部更新"}
          </button>
          <button type="button" className="btn quiet" onClick={onClose}>
            关闭
          </button>
        </div>
      </section>
    </div>
  );
}
