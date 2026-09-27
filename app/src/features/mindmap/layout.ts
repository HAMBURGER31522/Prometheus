// Stub (R7 red).
export interface TreeNode {
  label: string;
  type: "root" | "theme" | "topic" | "leaf";
  summary?: string;
  time?: number | null;
  children: TreeNode[];
}

export interface PlacedNode {
  id: string;
  parentId: string | null;
  node: TreeNode;
  depth: number;
  x: number;
  y: number;
  width: number;
  height: number;
  hiddenCount: number;
}

export interface Edge {
  id: string;
  source: string;
  target: string;
}

export function layoutTree(_root: TreeNode, _collapsed: Set<string>): { nodes: PlacedNode[]; edges: Edge[] } {
  return { nodes: [], edges: [] };
}
