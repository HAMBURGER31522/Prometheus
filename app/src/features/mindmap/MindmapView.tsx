// Mindmap tab: markmap rendering + moment-link interception + .md export (PLAN 9.3).

import { useEffect, useRef, useState } from "react";

import LibraryBrowser from "../../shared/LibraryBrowser";
import type { ContentTabProps } from "../../shared/LibraryBrowser";
import { contentUrl } from "../../shared/api";
import { openExternal } from "../../shared/platform";

export default function MindmapView(props: ContentTabProps) {
  return (
    <LibraryBrowser kind="思维导图" selection={props.selection} onSelect={props.onSelect}>
      {(item) => <MindmapFrame itemId={item.id} key={item.id} />}
    </LibraryBrowser>
  );
}

function MindmapFrame(props: { itemId: string }) {
  const container = useRef<HTMLDivElement | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    contentUrl(props.itemId, "mindmap")
      .then((url) => fetch(url))
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((text) => {
        if (!cancelled) setMarkdown(text);
      })
      .catch(() => {
        if (!cancelled) setMarkdown(null);
      });
    return () => {
      cancelled = true;
    };
  }, [props.itemId]);

  useEffect(() => {
    if (!markdown || !container.current) return;
    let cancelled = false;
    (async () => {
      const { Transformer } = await import("markmap-lib");
      const { Markmap } = await import("markmap-view");
      const transformer = new Transformer();
      const { root } = transformer.transform(markdown);
      if (cancelled || !container.current) return;
      container.current.innerHTML = "<svg />";
      const svg = container.current.querySelector("svg");
      if (!svg) return;
      Markmap.create(svg, { initialExpandLevel: 2 }, root);
      svg.addEventListener("click", (event) => {
        const target = event.target as HTMLElement;
        const anchor = target.closest("a");
        if (anchor) {
          event.preventDefault();
          event.stopPropagation();
          openExternal(anchor.href);
        }
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [markdown]);

  if (markdown === null) {
    return <p className="empty">导图尚未生成</p>;
  }

  const download = () => {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "mindmap.md";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mindmap-wrap">
      <button type="button" onClick={download}>导出 .md</button>
      <div className="markmap-container" ref={container} />
    </div>
  );
}
