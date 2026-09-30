// The console's stage names (PLAN 9, 15.4.11): the order the queue runs them in.
export const STAGES: [string, string][] = [
  ["resolve", "解析链接"],
  ["download", "下载"],
  ["transcribe", "转写"],
  ["transcript", "整理转写"],
  ["frames", "抽帧"],
  ["keypoints", "提取要点"],
  ["plan", "规划"],
  ["report", "写精读报告"],
  ["finalize", "定稿"],
  ["subtitle_fix", "字幕纠错"],
  ["mindmap", "生成导图"],
  ["classify", "分类"],
  ["publish", "放入知识库"],
];

/** Which step a running row is on, and of how many: the steps this video runs (PLAN 15.4.15). */
export function stepOf(row: { stage: string | null; stages?: string[] }): { index: number; total: number } {
  return { index: STAGES.findIndex(([id]) => id === row.stage), total: STAGES.length };
}

/** What a running row shows: the stage's own words while it reports them (「写作（第 3/10 章）」). */
export function stageText(row: { stage: string | null; stage_detail: string | null }): string {
  return row.stage_detail || STAGES.find(([id]) => id === row.stage)?.[1] || "准备中";
}
