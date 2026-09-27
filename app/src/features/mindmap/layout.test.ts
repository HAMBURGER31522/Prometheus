import { describe, expect, it } from "vitest";

import { type TreeNode, initialFolds, layoutTree } from "./layout";

const leaf = (label: string, time = 10): TreeNode => ({ label, type: "leaf", summary: "要点", time, children: [] });
const theme = (label: string, children: TreeNode[]): TreeNode => ({ label, type: "theme", summary: "主题", children });

const TREE: TreeNode = {
  label: "削藩与分配",
  type: "root",
  summary: "中国财政再平衡",
  children: [
    theme("分配的困境", [leaf("消费不足"), leaf("技术跑在前面"), leaf("资本积累")]),
    theme("「藩」的形成", [
      { label: "授权", type: "topic", summary: "中央授权地方", children: [leaf("分税制"), leaf("土地财政")] },
      leaf("利益固化"),
    ]),
    theme("再平衡的工具", [leaf("统一大市场")]),
  ],
};

function overlaps(a: { y: number; height: number }, b: { y: number; height: number }) {
  return a.y < b.y + b.height && b.y < a.y + a.height;
}

describe("mind map layout (PLAN 15.4.2, horizontal tidy tree)", () => {
  it("grows to the right, one column per level", () => {
    const { nodes } = layoutTree(TREE, new Set());
    const root = nodes.find((n) => n.id === "0")!;
    expect(root.x).toBe(0);
    for (const node of nodes) {
      if (node.parentId) expect(node.x).toBeGreaterThan(nodes.find((n) => n.id === node.parentId)!.x);
    }
  });

  it("never overlaps nodes of the same level", () => {
    const { nodes } = layoutTree(TREE, new Set());
    expect(nodes).toHaveLength(12);
    for (const a of nodes) {
      for (const b of nodes) {
        if (a !== b && a.depth === b.depth) expect(overlaps(a, b)).toBe(false);
      }
    }
  });

  it("centres each parent on its children", () => {
    const { nodes } = layoutTree(TREE, new Set());
    expect(nodes).toHaveLength(12);
    const centre = (n: { y: number; height: number }) => n.y + n.height / 2;
    for (const parent of nodes.filter((n) => nodes.some((c) => c.parentId === n.id))) {
      const children = nodes.filter((c) => c.parentId === parent.id);
      const mid = (centre(children[0]) + centre(children[children.length - 1])) / 2;
      expect(Math.abs(centre(parent) - mid)).toBeLessThan(0.5);
    }
  });

  it("links every visible child to its parent", () => {
    const { nodes, edges } = layoutTree(TREE, new Set());
    expect(edges).toHaveLength(nodes.length - 1);
    expect(edges).toContainEqual({ id: "0-0.1", source: "0", target: "0.1" });
  });

  it("a collapsed theme hides its descendants and gives the space back", () => {
    const open = layoutTree(TREE, new Set());
    const folded = layoutTree(TREE, new Set(["0.1"]));
    expect(folded.nodes.some((n) => n.id.startsWith("0.1."))).toBe(false);
    expect(folded.nodes.find((n) => n.id === "0.1")!.hiddenCount).toBe(4);
    const height = (layout: typeof open) => Math.max(...layout.nodes.map((n) => n.y + n.height));
    expect(height(folded)).toBeLessThan(height(open));
  });
});

describe("simple at the root, rich at the leaves (PLAN 15.4.9)", () => {
  const rich = (label: string, time = 10): TreeNode => ({ ...leaf(label, time), detail: "依据报告写的详解。".repeat(14) });
  const MIXED: TreeNode = {
    label: "削藩与分配",
    type: "root",
    children: [
      theme("分配的困境", [rich("消费不足"), leaf("技术跑在前面"), rich("资本积累")]),
      theme("「藩」的形成", [
        { label: "授权", type: "topic", summary: "中央授权地方", children: [rich("分税制"), leaf("土地财政")] },
        rich("利益固化"),
      ]),
    ],
  };

  it("a leaf with detail is a wider, taller card; one without stays compact", () => {
    const { nodes } = layoutTree(MIXED, new Set());
    const withDetail = nodes.find((n) => n.node.label === "消费不足")!;
    const plain = nodes.find((n) => n.node.label === "技术跑在前面")!;
    expect(withDetail.width).toBeGreaterThan(plain.width);
    expect(withDetail.height).toBeGreaterThan(plain.height);
    for (const a of nodes) {
      for (const b of nodes) {
        if (a !== b && a.depth === b.depth) expect(overlaps(a, b)).toBe(false);
      }
    }
  });

  it("neighbouring columns are the same distance apart, however wide the leaf cards", () => {
    const { nodes } = layoutTree(MIXED, new Set());
    const depths = [...new Set(nodes.map((n) => n.depth))].sort();
    const gaps = depths.slice(1).map((depth) => {
      const left = Math.max(...nodes.filter((n) => n.depth === depth - 1).map((n) => n.x + n.width));
      const right = Math.min(...nodes.filter((n) => n.depth === depth).map((n) => n.x));
      return right - left;
    });
    expect(gaps.length).toBe(3);
    expect(new Set(gaps).size).toBe(1);
    expect(gaps[0]).toBeGreaterThan(0);
  });
});

describe("first view of a big tree", () => {
  const big: TreeNode = {
    label: "长视频",
    type: "root",
    children: Array.from({ length: 5 }, (_, t) => theme(`主题${t}`, Array.from({ length: 6 }, (_, l) => leaf(`要点${t}-${l}`)))),
  };

  it("starts with every theme folded once there are more than 24 leaves", () => {
    expect([...initialFolds(big)].sort()).toEqual(["0.0", "0.1", "0.2", "0.3", "0.4"]);
  });

  it("shows a small tree whole", () => {
    expect(initialFolds(TREE).size).toBe(0);
  });
});
