// 导图 (PLAN 15.4.2): the knowledge tree on a React Flow canvas, laid out as a horizontal
// tidy tree; themes fold, nodes open a summary panel, times open the video at that moment.
import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";

import { type ReaderProps } from "../../shared/LibraryPage";
import { type MindmapTree, api, itemTitle } from "../../shared/api";
import { clock, momentLink } from "../../shared/format";
import { downloadText, openExternal } from "../../shared/platform";
import { type PlacedNode, layoutTree } from "./layout";

type MindData = { placed: PlacedNode; folded: boolean; onToggle: (id: string) => void };

function MindNode({ data, selected }: NodeProps<Node<MindData>>) {
  const { placed, folded, onToggle } = data;
  const { node } = placed;
  const canFold = node.type !== "root" && node.children.length > 0;
  return (
    <div className={`mind-node ${node.type}`} data-selected={selected || undefined}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="mind-label">{node.label}</span>
      {node.type === "leaf" && node.summary && <span className="mind-summary">{node.summary}</span>}
      {node.type === "leaf" && node.time != null && <span className="mind-time">{clock(node.time)}</span>}
      {canFold && (
        <button
          type="button"
          className="mind-fold nodrag"
          aria-label={folded ? `展开 ${node.label}` : `折叠 ${node.label}`}
          onClick={(event) => {
            event.stopPropagation();
            onToggle(placed.id);
          }}
        >
          {folded ? `+${placed.hiddenCount}` : "−"}
        </button>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const NODE_TYPES = { mind: MindNode };

export function MindmapView(props: ReaderProps) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}

function Canvas({ item, refresh }: ReaderProps) {
  const [tree, setTree] = useState<MindmapTree | null>(null);
  const [missing, setMissing] = useState(false);
  const [folded, setFolded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<PlacedNode | null>(null);
  const flow = useReactFlow();

  useEffect(() => {
    let alive = true;
    setSelected(null);
    api
      .mindmapTree(item.id)
      .then((value) => {
        if (!alive) return;
        setTree(value);
        setMissing(false);
      })
      .catch(() => alive && setMissing(true));
    return () => {
      alive = false;
    };
  }, [item.id, item.mindmap_status]);

  const toggle = (id: string) =>
    setFolded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const { nodes, edges } = useMemo(() => {
    if (!tree) return { nodes: [], edges: [] };
    const layout = layoutTree(tree.root, folded);
    return {
      nodes: layout.nodes.map<Node<MindData>>((placed) => ({
        id: placed.id,
        type: "mind",
        position: { x: placed.x, y: placed.y },
        width: placed.width,
        height: placed.height,
        style: { width: placed.width, height: placed.height },
        data: { placed, folded: folded.has(placed.id), onToggle: toggle },
        draggable: false,
        connectable: false,
      })),
      edges: layout.edges.map((edge) => ({ ...edge, type: "simplebezier", className: "mind-edge" })),
    };
  }, [tree, folded]);

  useEffect(() => {
    if (nodes.length) requestAnimationFrame(() => void flow.fitView({ padding: 0.12, duration: 300 }));
  }, [tree, flow, nodes.length]);

  const regenerate = async () => {
    await api.regenerateMindmap(item.id);
    await refresh();
  };

  if (!tree) {
    const failed = item.mindmap_status === "failed";
    return (
      <div className="page">
        <p className={failed ? "notice danger" : "notice"}>
          {failed ? "这个视频的导图没有生成成功。" : missing ? "导图正在生成…" : "正在打开导图…"}
        </p>
        {failed && (
          <button type="button" className="btn" style={{ marginTop: 14 }} onClick={regenerate}>
            重新生成导图
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="mindmap">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodeClick={(_event, node) => setSelected((node.data as MindData).placed)}
        onPaneClick={() => setSelected(null)}
        minZoom={0.2}
        maxZoom={1.6}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        colorMode="dark"
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} className="mind-dots" />
        <Controls showInteractive={false} position="bottom-left" />
      </ReactFlow>
      <div className="mind-tools">
        {item.mindmap_status === null && <span className="badge accent">重新生成中…</span>}
        <button type="button" className="btn small" onClick={() => void flow.fitView({ padding: 0.12, duration: 400 })}>
          适应画布
        </button>
        <button
          type="button"
          className="btn small"
          onClick={async () => downloadText(`${itemTitle(item)} 思维导图.md`, await api.mindmapMarkdown(item.id), "text/markdown")}
        >
          导出 .md
        </button>
        <button type="button" className="btn small quiet" onClick={regenerate}>
          重新生成
        </button>
      </div>
      {selected && (
        <aside className="mind-panel" aria-label="节点摘要">
          <span className="badge accent">{{ root: "中心", theme: "主题", topic: "子题", leaf: "要点" }[selected.node.type]}</span>
          <h3>{selected.node.label}</h3>
          {selected.node.summary && <p>{selected.node.summary}</p>}
          {selected.node.time != null && (
            <button
              type="button"
              className="btn small"
              onClick={() => openExternal(momentLink(item.platform, item.video_id, selected.node.time!))}
            >
              在视频中打开 {clock(selected.node.time)}
            </button>
          )}
        </aside>
      )}
    </div>
  );
}
