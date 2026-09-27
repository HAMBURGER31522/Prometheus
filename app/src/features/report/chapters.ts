// Which chapter of a report a moment belongs to (PLAN 15.4.9, 「在精读中查看」); the same rule as
// backend/src/prometheus/mindmap/retrieve.py. Self-contained: its source is injected into the
// report page (theme.ts), so it may not use anything from outside the function.

/** The narrowest chapter containing the moment, leaving out chapters it falls in the last two
 * seconds of (chapters overlap by a second, and an overview chapter spanning others is the least
 * specific). Outside every chapter: the one that started last, or the first one just ahead. */
export function chapterAt(ranges: Array<[number, number] | null>, seconds: number): number | null {
  const pick = (last: number) => {
    let best: number | null = null;
    let bestWidth = Infinity;
    let bestStart = -Infinity;
    ranges.forEach((range, index) => {
      if (!range || range[0] > seconds || seconds > range[1] - last) return;
      const width = range[1] - range[0];
      if (width < bestWidth || (width === bestWidth && range[0] > bestStart)) {
        best = index;
        bestWidth = width;
        bestStart = range[0];
      }
    });
    return best;
  };
  const inside = pick(2) ?? pick(0);
  if (inside !== null) return inside;
  let started: number | null = null;
  let ahead: number | null = null;
  ranges.forEach((range, index) => {
    if (!range) return;
    if (range[0] <= seconds && (started === null || range[0] > (ranges[started] as [number, number])[0])) started = index;
    if (range[0] - 5 <= seconds && (ahead === null || range[0] < (ranges[ahead] as [number, number])[0])) ahead = index;
  });
  return started ?? ahead;
}
