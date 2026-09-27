// The glass capsule in its own left column (PLAN 15.4.5): it never covers the content,
// and its highlight is always the current tab.
import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";

import { Lens } from "./GlassLens";
import { icons } from "./icons";
import { TABS } from "./nav";
import { useNav } from "./NavContext";

export function Sidebar({ busy }: { busy: number }) {
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
          <div>
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
              aria-current={nav.tab === tab.id ? "page" : undefined}
              onClick={() => go({ type: "tab", tab: tab.id })}
            >
              {icons[tab.id]}
              {tab.label}
            </button>
          ))}
        </div>
        <div className="foot" aria-live="polite">
          <span className={busy ? "dot busy" : "dot"} />
          {busy ? `${busy} 个任务进行中` : "空闲"}
        </div>
      </nav>
    </aside>
  );
}
