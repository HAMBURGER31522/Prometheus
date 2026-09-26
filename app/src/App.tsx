import { useEffect, useState } from "react";

import ConsolePage from "./features/console/ConsolePage";
import MindmapView from "./features/mindmap/MindmapView";
import ReportView from "./features/report/ReportView";
import SettingsPage from "./features/settings/SettingsPage";
import SubtitleView from "./features/subtitle/SubtitleView";
import { api } from "./shared/api";
import { pickDirectory } from "./shared/platform";
import Sidebar from "./shared/Sidebar";
import type { Tab } from "./shared/Sidebar";
import { TABS } from "./shared/Sidebar";
import "./app.css";
import "./shared/tokens.css";

export interface Selection {
  categoryId: number | null;
  itemId: string | null;
}

export default function App() {
  const [dataDir, setDataDir] = useState<string | null | "loading">("loading");
  const [tab, setTab] = useState<Tab>(TABS[0]);
  const [selection, setSelection] = useState<Selection>({ categoryId: null, itemId: null });

  useEffect(() => {
    api.getDataDir().then(
      (result) => setDataDir(result.data_dir),
      () => setDataDir(null),
    );
  }, []);

  if (dataDir === "loading") {
    return <main className="app-shell"><p>正在连接后端…</p></main>;
  }

  if (dataDir === null) {
    return (
      <main className="app-shell">
        <h1>Prometheus</h1>
        <p>选择一个数据目录，报告、导图与字幕都会存放在这里。</p>
        <button
          type="button"
          className="primary"
          onClick={async () => {
            const dir = await pickDirectory();
            if (!dir) return;
            const result = await api.setDataDir(dir);
            setDataDir(result.data_dir);
          }}
        >
          选择数据目录
        </button>
      </main>
    );
  }

  const sharedProps = {
    selection,
    onSelect: (next: Selection) => setSelection(next),
  };

  return (
    <div className="app-frame">
      <Sidebar current={tab} onSelect={setTab} />
      <main className="app-content">
        {tab === "控制台" && <ConsolePage />}
        {tab === "知识库" && <ReportView {...sharedProps} />}
        {tab === "思维导图" && <MindmapView {...sharedProps} />}
        {tab === "字幕" && <SubtitleView {...sharedProps} />}
        {tab === "设置" && <SettingsPage onDataDirChanged={setDataDir} />}
      </main>
    </div>
  );
}
