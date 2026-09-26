// Knowledge-base tab: the report iframe; external links route to the browser.

import { useEffect, useState } from "react";

import LibraryBrowser from "../../shared/LibraryBrowser";
import type { ContentTabProps } from "../../shared/LibraryBrowser";
import { contentUrl } from "../../shared/api";
import { openExternal } from "../../shared/platform";

export default function ReportView(props: ContentTabProps) {
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const data = event.data as { type?: string; href?: string };
      if (event.origin.startsWith("http://127.0.0.1:") && data?.type === "open-external" && data.href) {
        openExternal(data.href);
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  return (
    <LibraryBrowser kind="知识库" selection={props.selection} onSelect={props.onSelect}>
      {(item) => (
        <ReportFrame itemId={item.id} key={item.id} />
      )}
    </LibraryBrowser>
  );
}

function ReportFrame(props: { itemId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    contentUrl(props.itemId, "report").then(setSrc, () => setSrc(null));
  }, [props.itemId]);
  if (!src) return <p className="empty">报告尚未生成</p>;
  return (
    <iframe
      title="精读报告"
      sandbox="allow-scripts"
      src={src}
      className="report-frame"
    />
  );
}
