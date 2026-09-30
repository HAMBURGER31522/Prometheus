// Shell (PLAN 15.4.5): the capsule in its own column, pages beside it, page changes
// animated with React's <ViewTransition>.
import { ViewTransition, useCallback, useEffect, useState } from "react";

import { ConsolePage } from "./features/console/ConsolePage";
import { MindmapView } from "./features/mindmap/MindmapView";
import { ReportView } from "./features/report/ReportView";
import { SettingsPage } from "./features/settings/SettingsPage";
import { SubtitleView } from "./features/subtitle/SubtitleView";
import { type ItemRow, api } from "./shared/api";
import { FirstRun, Starting, useStartup } from "./shared/FirstRun";
import { LibraryPage } from "./shared/LibraryPage";
import { NavProvider, useNav } from "./shared/NavContext";
import { ZoomProvider } from "./shared/ReaderTools";
import { Sidebar } from "./shared/Sidebar";
import { useLibrary } from "./shared/useLibrary";

// The sidebar folds into an icon rail (PLAN 15.4.7); remembered across launches.
const RAIL_KEY = "prometheus.rail";

function Shell() {
  const { nav } = useNav();
  const library = useLibrary();
  const [queue, setQueue] = useState<ItemRow[]>([]);

  const reloadQueue = useCallback(async () => {
    setQueue(await api.queue());
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = () => alive && reloadQueue().catch(() => undefined);
    tick();
    const timer = setInterval(tick, 1500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [reloadQueue]);

  const busy = queue.filter((row) => row.status === "queued" || row.status === "running").length;
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(RAIL_KEY) === "collapsed");
  const toggleRail = useCallback(() => {
    setCollapsed((value) => {
      localStorage.setItem(RAIL_KEY, value ? "expanded" : "collapsed");
      return !value;
    });
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey && !event.altKey && event.key.toLowerCase() === "b") {
        event.preventDefault();
        toggleRail();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleRail]);

  let page;
  switch (nav.tab) {
    case "console":
      page = <ConsolePage queue={queue} reload={reloadQueue} />;
      break;
    case "library":
      page = <LibraryPage library={library} render={(props) => <ReportView {...props} />} />;
      break;
    case "mindmap":
      page = <LibraryPage library={library} render={(props) => <MindmapView {...props} />} />;
      break;
    case "subtitle":
      page = <LibraryPage library={library} render={(props) => <SubtitleView {...props} />} />;
      break;
    case "settings":
      page = <SettingsPage />;
      break;
  }

  return (
    <div className="app" data-rail={collapsed ? "collapsed" : "expanded"}>
      <Sidebar busy={busy} collapsed={collapsed} onToggle={toggleRail} />
      <main className="stage">
        <ViewTransition key={`${nav.tab}:${nav.itemId ?? ""}`}>
          <div className="stage-page">{page}</div>
        </ViewTransition>
      </main>
    </div>
  );
}

export default function App() {
  const [startup, chosen] = useStartup();
  if (startup.phase === "starting") return <Starting />;
  if (startup.phase === "choose") return <FirstRun suggested={startup.suggested} onChosen={chosen} />;
  return (
    <NavProvider>
      <ZoomProvider>
        <Shell />
      </ZoomProvider>
    </NavProvider>
  );
}
