// 精读的详细程度和配图 (PLAN 15.4.15): beside the console's link box for one video, and beside the
// reader's 「现在生成」 of a missing report. Shared so the two read alike; both start from the settings.
import { type CSSProperties, useEffect, useState } from "react";

import { type ReportDepth, api } from "./api";

const DEPTHS: { value: ReportDepth; label: string }[] = [
  { value: "standard", label: "标准" },
  { value: "full", label: "完整" },
];

/** This video's depth and figures, starting from the settings' defaults. */
export function useReportChoice() {
  const [depth, setDepth] = useState<ReportDepth>("full");
  const [figures, setFigures] = useState(true);
  useEffect(() => {
    api
      .settings()
      .then((s) => {
        setFigures(s.figures_default);
        setDepth(s.report.depth);
      })
      .catch(() => undefined);
  }, []);
  return { depth, setDepth, figures, setFigures };
}

/** `off`: there is no report to make (the console without 精读): grey, and figures show off. */
export function ReportOptions({ choice, off = false }: { choice: ReturnType<typeof useReportChoice>; off?: boolean }) {
  const { depth, setDepth, figures, setFigures } = choice;
  return (
    <div className="report-options" data-off={off || undefined}>
      <span className="muted">精读</span>
      <div
        className="segmented two"
        role="radiogroup"
        aria-label="精读详细程度"
        style={{ "--i": depth === "full" ? 1 : 0 } as CSSProperties}
      >
        <span className="thumb" aria-hidden="true" />
        {DEPTHS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={depth === value}
            disabled={off}
            onClick={() => setDepth(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <label className="switch-label">
        <button
          type="button"
          role="switch"
          className="switch"
          aria-checked={figures && !off}
          aria-label="配图"
          disabled={off}
          onClick={() => setFigures(!figures)}
        />
        配图
      </label>
    </div>
  );
}
