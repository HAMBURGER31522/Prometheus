// The glass capsule in its own left column (PLAN 15.4.5): it never covers the content, and its
// highlight is always the current tab. It folds into an icon rail (PLAN 15.4.7).
import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";

import { Lens } from "./GlassLens";
import { icons } from "./icons";
import { TABS } from "./nav";
import { useNav } from "./NavContext";

export function Sidebar({ busy, collapsed, onToggle }: { busy: number; collapsed: boolean; onToggle: () => void }) {
  const { nav, go } = useNav();
  const capsule = useRef<HTMLElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [y, setY] = useState(0);

  useLayoutEffect(() => {
    const active = list.current?.querySelector<HTMLElement>('[aria-current="page"]');
    if (active) setY(active.offsetTop);
  }, [nav.tab]);

  return (
    <aside className="rail">
      <Lens id="lens" target={capsule} radius={22} bezel={26} scale={46} />
      <nav className="sidebar" aria-label="主导航" ref={capsule}>
        <div className="brand">
          <span className="seal" aria-hidden="true">
            火
          </span>
          <div className="brand-text">
            <b>Prometheus</b>
            <small>视频精读</small>
          </div>
        </div>
        <div className="nav" ref={list}>
          <span className="indicator" style={{ "--y": `${y}px` } as CSSProperties} aria-hidden="true" />
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              title={collapsed ? tab.label : undefined}
              aria-current={nav.tab === tab.id ? "page" : undefined}
              onClick={() => go({ type: "tab", tab: tab.id })}
            >
              {icons[tab.id]}
              <span className="label">{tab.label}</span>
            </button>
          ))}
        </div>
        <div className="foot">
          <span className="status" aria-live="polite" title={busy ? `${busy} 个任务进行中` : "空闲"}>
            <span className={busy ? "dot busy" : "dot"} />
            <span className="label">{busy ? `${busy} 个任务进行中` : "空闲"}</span>
          </span>
          <button
            type="button"
            className="fold"
            aria-label={collapsed ? "展开侧栏" : "收起侧栏"}
            title={`${collapsed ? "展开" : "收起"}侧栏（Ctrl+B）`}
            onClick={onToggle}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M15 6l-6 6 6 6" />
            </svg>
          </button>
        </div>
      </nav>
    </aside>
  );
}
