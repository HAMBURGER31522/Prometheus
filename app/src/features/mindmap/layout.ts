// Horizontal tidy tree for the knowledge-tree mind map (PLAN 15.4.2), after BiliSum's
// layoutMindMap idea: one column per level, leaves stacked top to bottom, every parent
// centred on its visible children. A collapsed node is laid out as a leaf.

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
  /** Descendants hidden because this node is collapsed. */
  hiddenCount: number;
}

export interface Edge {
  id: string;
  source: string;
  target: string;
}

export const NODE_SIZE: Record<TreeNode["type"], { width: number; height: number }> = {
  root: { width: 240, height: 72 },
  theme: { width: 220, height: 56 },
  topic: { width: 200, height: 48 },
  leaf: { width: 260, height: 64 },
};
const GAP_X = 72;
const GAP_Y = 14;
const COLUMN = Math.max(...Object.values(NODE_SIZE).map((size) => size.width)) + GAP_X;

function descendants(node: TreeNode): number {
  return node.children.reduce((sum, child) => sum + 1 + descendants(child), 0);
}

export function layoutTree(root: TreeNode, collapsed: Set<string>): { nodes: PlacedNode[]; edges: Edge[] } {
  const nodes: PlacedNode[] = [];
  const edges: Edge[] = [];
  let cursor = 0; // next free y for a leaf

  // Returns the placed node so the parent can centre on its children.
  const place = (node: TreeNode, id: string, parentId: string | null, depth: number): PlacedNode => {
    const size = NODE_SIZE[node.type];
    const folded = collapsed.has(id) && node.children.length > 0;
    const placed: PlacedNode = {
      id, parentId, node, depth, x: depth * COLUMN, y: 0, width: size.width, height: size.height,
      hiddenCount: folded ? descendants(node) : 0,
    };
    nodes.push(placed);
    if (folded || node.children.length === 0) {
      placed.y = cursor;
      cursor += size.height + GAP_Y;
      return placed;
    }
    const children = node.children.map((child, index) => {
      const childId = `${id}.${index}`;
      edges.push({ id: `${id}-${childId}`, source: id, target: childId });
      return place(child, childId, id, depth + 1);
    });
    const first = children[0];
    const last = children[children.length - 1];
    const mid = (first.y + first.height / 2 + last.y + last.height / 2) / 2;
    placed.y = mid - size.height / 2;
    return placed;
  };

  place(root, "0", null, 0);
  // A parent taller than its only child can poke above the first leaf: shift everything down.
  const top = Math.min(...nodes.map((n) => n.y));
  if (top < 0) for (const n of nodes) n.y -= top;
  return { nodes, edges };
}
