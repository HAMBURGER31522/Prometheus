// Horizontal tidy tree for the knowledge-tree mind map (PLAN 15.4.2), after BiliSum's
// layoutMindMap idea: one column per level, leaves stacked top to bottom, every parent
// centred on its visible children. A collapsed node is laid out as a leaf; a leaf with detail
// is a bigger card.

export interface TreeNode {
  label: string;
  type: "root" | "theme" | "topic" | "leaf";
  summary?: string;
  /** Leaves only: 2-4 grounded sentences (PLAN 15.4.9). */
  detail?: string;
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
/** A leaf with detail: label, two lines of summary and the detail's first four lines (PLAN 15.4.9). */
export const RICH_LEAF = { width: 380, height: 168 };
const GAP_X = 72;
const GAP_Y = 14;

export function sizeOf(node: TreeNode): { width: number; height: number } {
  return node.type === "leaf" && node.detail ? RICH_LEAF : NODE_SIZE[node.type];
}

function descendants(node: TreeNode): number {
  return node.children.reduce((sum, child) => sum + 1 + descendants(child), 0);
}

export function layoutTree(root: TreeNode, collapsed: Set<string>): { nodes: PlacedNode[]; edges: Edge[] } {
  const nodes: PlacedNode[] = [];
  const edges: Edge[] = [];
  let cursor = 0; // next free y for a leaf

  // Returns the placed node so the parent can centre on its children.
  const place = (node: TreeNode, id: string, parentId: string | null, depth: number): PlacedNode => {
    const size = sizeOf(node);
    const folded = collapsed.has(id) && node.children.length > 0;
    const placed: PlacedNode = {
      id, parentId, node, depth, x: 0, y: 0, width: size.width, height: size.height,
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
  // Each column starts one gap after the widest card of the column before it.
  const widths: number[] = [];
  for (const n of nodes) widths[n.depth] = Math.max(widths[n.depth] ?? 0, n.width);
  const columns = widths.reduce<number[]>((xs, _width, depth) => [...xs, depth ? xs[depth - 1] + widths[depth - 1] + GAP_X : 0], []);
  for (const n of nodes) n.x = columns[n.depth];
  // A parent taller than its only child can poke above the first leaf: shift everything down.
  const top = Math.min(...nodes.map((n) => n.y));
  if (top < 0) for (const n of nodes) n.y -= top;
  return { nodes, edges };
}

const OVERVIEW_LEAVES = 24;

function leafCount(node: TreeNode): number {
  return node.children.length ? node.children.reduce((sum, child) => sum + leafCount(child), 0) : 1;
}

/** A long video's tree first shows its themes only, readable at a glance; a small one shows whole. */
export function initialFolds(root: TreeNode): Set<string> {
  if (leafCount(root) <= OVERVIEW_LEAVES) return new Set();
  return new Set(root.children.flatMap((child, index) => (child.children.length ? [`0.${index}`] : [])));
}
