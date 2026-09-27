// Which chapter of a report a moment belongs to (PLAN 15.4.9, 「在精读中查看」); the same rule as
// backend/src/prometheus/mindmap/retrieve.py. Self-contained: its source is injected into the
// report page (theme.ts), so it may not use anything from outside the function.

export function chapterAt(ranges: Array<[number, number] | null>, seconds: number): number | null {
  return null;
}
