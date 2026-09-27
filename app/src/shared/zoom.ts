// Reading zoom (PLAN 15.4.7): 80%–160% in 10% steps, shared by 精读 and 字幕, remembered.

export const ZOOM_MIN = 0.8;
export const ZOOM_MAX = 1.6;

/** Tenths are kept exact so repeated steps never drift (1.1 + 0.1 = 1.2000000000000002). */
export function stepZoom(zoom: number, direction: -1 | 0 | 1): number {
  if (direction === 0) return 1;
  const tenths = Math.round(zoom * 10) + direction;
  return Math.min(ZOOM_MAX * 10, Math.max(ZOOM_MIN * 10, tenths)) / 10;
}
