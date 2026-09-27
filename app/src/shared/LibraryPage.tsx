// 知识库, 思维导图 and 字幕 share one layout (PLAN 15.4.5): 分类 → 条目 → 内容. Only the
// content differs, and 精读 / 导图 / 字幕 in the reader switch tabs on the same item.
import { type CSSProperties, type ReactNode, useRef, useState } from "react";

import { type ItemRow, api, itemTags, itemTitle } from "./api";
import { duration, sourceLabel } from "./format";
import { Lens } from "./GlassLens";
import { READER_VIEWS, type Tab } from "./nav";
import { useNav } from "./NavContext";
import { ToolsSlot } from "./ReaderTools";
import { ScrollArea } from "./ScrollArea";
import type { Library } from "./useLibrary";

const HEADINGS: Partial<Record<Tab, { title: string; hint: string }>> = {
  library: { title: "知识库", hint: "精读报告，按分类整理" },
  mindmap: { title: "思维导图", hint: "每个视频的知识树" },
  subtitle: { title: "字幕", hint: "按时间戳完整保留原文" },
};

export interface ReaderProps {
  item: ItemRow;
  refresh: () => Promise<void>;
}

export function LibraryPage({ library, render }: {
  library: Library;
  render: (props: ReaderProps) => ReactNode;
}) {
  const { nav } = useNav();
  const item = nav.itemId ? library.items.find((row) => row.id === nav.itemId) : undefined;
  if (item) return <Reader item={item} library={library}>{render({ item, refresh: library.refresh })}</Reader>;
  return <Browse library={library} />;
}

function Browse({ library }: { library: Library }) {
  const { nav, go } = useNav();
  const heading = HEADINGS[nav.tab]!;
  const categoryId = nav.categoryId ?? library.categories[0]?.id ?? null;
  const category = library.categories.find((cat) => cat.id === categoryId);
  const items = library.items.filter((row) => row.category_id === categoryId);

  return (
    <div className="library">
      <ScrollArea className="categories">
        <h2>分类</h2>
        <ul aria-label="分类">
          {library.categories.map((cat) => (
            <li key={cat.id}>
              <button
                type="button"
                className="category"
                aria-current={cat.id === categoryId ? "true" : undefined}
                onClick={() => go({ type: "category", categoryId: cat.id })}
              >
                <span>{cat.name}</span>
                <span className="count">{library.items.filter((row) => row.category_id === cat.id).length}</span>
              </button>
            </li>
          ))}
        </ul>
      </ScrollArea>
      <ScrollArea className="items">
        <div className="items-head">
          <h1>{category?.name ?? heading.title}</h1>
          <span className="muted">{heading.hint}</span>
        </div>
        {library.loaded && items.length === 0 && (
          <p className="empty">还没有完成的条目。在「控制台」粘贴一个视频链接开始。</p>
        )}
        <ul aria-label="条目">
          {items.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                className="item-card"
                onClick={() => {
                  if (nav.categoryId !== categoryId) go({ type: "category", categoryId });
                  go({ type: "item", itemId: row.id });
                }}
              >
                <span className="item-title" data-testid="item-title">
                  {itemTitle(row)}
                </span>
                <span className="meta">
                  {row.finished_at && <span>{row.finished_at.slice(0, 10)}</span>}
                  {row.duration_s != null && <span>{duration(row.duration_s)}</span>}
                  {row.uploader && <span>{row.uploader}</span>}
                  {row.transcript_source && <span className="badge">{sourceLabel(row.transcript_source)}</span>}
                  {row.mindmap_status === "failed" && <span className="badge danger">导图未生成</span>}
                  {row.files_missing && <span className="badge danger">文件缺失</span>}
                </span>
                {row.description && <span className="desc">{row.description}</span>}
                {itemTags(row).length > 0 && (
                  <span className="tags">
                    {itemTags(row).map((tag) => (
                      <span key={tag} className="badge accent">
                        {tag}
                      </span>
                    ))}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </ScrollArea>
    </div>
  );
}

function Reader({ item, library, children }: { item: ItemRow; library: Library; children: ReactNode }) {
  const { nav, go } = useNav();
  const bar = useRef<HTMLDivElement>(null);
  const [slot, setSlot] = useState<HTMLDivElement | null>(null);
  const heading = HEADINGS[nav.tab]!;
  const category = library.categories.find((cat) => cat.id === item.category_id);
  const index = READER_VIEWS.findIndex((view) => view.id === nav.tab);

  return (
    <div className="reader">
      <Lens id="lens2" target={bar} radius={16} bezel={18} scale={38} />
      <div className="reader-bar" role="toolbar" aria-label="阅读" ref={bar}>
        <div className="crumbs">
          <button type="button" onClick={() => go({ type: "category", categoryId: null })}>
            {heading.title}
          </button>
          <span aria-hidden="true">/</span>
          <button type="button" onClick={() => go({ type: "close" })}>
            {category?.name ?? "未分类"}
          </button>
          <span aria-hidden="true">/</span>
          <span data-testid="reader-title">{itemTitle(item)}</span>
        </div>
        <div className="reader-tools" ref={setSlot} />
        <div className="segmented" role="tablist" aria-label="视图" style={{ "--i": index } as CSSProperties}>
          <span className="thumb" aria-hidden="true" />
          {READER_VIEWS.map((view) => (
            <button
              key={view.id}
              type="button"
              role="tab"
              aria-selected={nav.tab === view.id}
              onClick={() => go({ type: "tab", tab: view.id })}
            >
              {view.label}
            </button>
          ))}
        </div>
        <ItemMenu item={item} library={library} />
      </div>
      <div className="reader-body">
        <ToolsSlot value={slot}>
          {item.files_missing ? <FilesMissing item={item} refresh={library.refresh} /> : children}
        </ToolsSlot>
      </div>
    </div>
  );
}

function ItemMenu({ item, library }: { item: ItemRow; library: Library }) {
  const { go } = useNav();
  return (
    <div className="reader-actions">
      <select
        className="select"
        aria-label="移到分类"
        value={item.category_id ?? ""}
        onChange={async (event) => {
          await api.moveItem(item.id, Number(event.target.value));
          go({ type: "category", categoryId: Number(event.target.value) });
          go({ type: "item", itemId: item.id });
          await library.refresh();
        }}
      >
        {library.categories.map((cat) => (
          <option key={cat.id} value={cat.id}>
            {cat.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="btn quiet small danger"
        onClick={async () => {
          if (!window.confirm(`删除「${itemTitle(item)}」及其知识库文件夹？`)) return;
          await api.deleteItem(item.id);
          go({ type: "close" });
          await library.refresh();
        }}
      >
        删除
      </button>
    </div>
  );
}

function FilesMissing({ item, refresh }: { item: ItemRow; refresh: () => Promise<void> }) {
  const { go } = useNav();
  return (
    <div className="page">
      <p className="notice danger">这个条目在知识库里的文件夹不见了（可能在资源管理器里被移动或删除）。</p>
      <div className="row" style={{ marginTop: 16 }}>
        <button type="button" className="btn" onClick={async () => {
          await api.regenerate(item.id);
          await refresh();
        }}>
          重新生成
        </button>
        <button type="button" className="btn danger" onClick={async () => {
          await api.deleteItem(item.id);
          go({ type: "close" });
          await refresh();
        }}>
          删除记录
        </button>
      </div>
    </div>
  );
}
