// The reader toolbar's tool slot and the shared reading zoom (PLAN 15.4.7). Each view puts
// its own tools (目录, A− / A+) into the glass toolbar through <ReaderTools>.
import { type ReactNode, createContext, useContext, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { stepZoom } from "./zoom";

export const ToolsSlot = createContext<HTMLElement | null>(null);

export function ReaderTools({ children }: { children: ReactNode }) {
  const slot = useContext(ToolsSlot);
  return slot ? createPortal(children, slot) : null;
}

const ZOOM_KEY = "prometheus.zoom";
const ZoomContext = createContext<{ zoom: number; setZoom: (value: number) => void }>({
  zoom: 1,
  setZoom: () => undefined,
});

export function ZoomProvider({ children }: { children: ReactNode }) {
  const [zoom, setZoomState] = useState(() => Number(localStorage.getItem(ZOOM_KEY)) || 1);
  const setZoom = (value: number) => {
    setZoomState(value);
    localStorage.setItem(ZOOM_KEY, String(value));
  };
  return <ZoomContext value={{ zoom, setZoom }}>{children}</ZoomContext>;
}

export const useZoom = () => useContext(ZoomContext);

/** A− 100% A+, plus Ctrl+= / Ctrl+- / Ctrl+0 while a reader is open. */
export function ZoomControls() {
  const { zoom, setZoom } = useZoom();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.ctrlKey || event.altKey) return;
      const direction = event.key === "=" || event.key === "+" ? 1 : event.key === "-" ? -1 : event.key === "0" ? 0 : null;
      if (direction === null) return;
      event.preventDefault();
      setZoom(stepZoom(zoom, direction));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  return (
    <div className="zoom" role="group" aria-label="正文缩放">
      <button type="button" className="btn quiet small" aria-label="缩小正文" onClick={() => setZoom(stepZoom(zoom, -1))}>
        A−
      </button>
      <button type="button" className="zoom-level" data-testid="zoom-level" title="恢复 100%" onClick={() => setZoom(1)}>
        {Math.round(zoom * 100)}%
      </button>
      <button type="button" className="btn quiet small" aria-label="放大正文" onClick={() => setZoom(stepZoom(zoom, 1))}>
        A+
      </button>
    </div>
  );
}
