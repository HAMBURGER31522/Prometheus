// 要点覆盖 in the reader (PLAN 15.4.11): points written out of those not skipped for a reason.
import { type Coverage } from "../../shared/api";

export function coverageLabel(coverage: Coverage): string {
  return `要点 ${coverage.written}/${coverage.points_total - coverage.skipped.length}`;
}
