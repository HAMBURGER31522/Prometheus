// 知识库, 思维导图 and 字幕 share one layout (PLAN 15.4.5): 分类 → 条目 → 内容. Only the
// content differs, and 精读 / 导图 / 字幕 in the reader switch tabs on the same item.
import { type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { ApiError, type CategoryRow, type ItemRow, api, itemTags, itemTitle } from "./api";
import { duration, sourceLabel } from "./format";
import { Lens } from "./GlassLens";
import { icons } from "./icons";
import { READER_VIEWS, type Tab } from "./nav";
import { useNav } from "./NavContext";
import { ToolsSlot } from "./ReaderTools";
import { ScrollArea } from "./ScrollArea";
import type { Library } from "./useLibrary";

const UNCATEGORIZED = "未分类";

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
  const countOf = (id: number) => library.items.filter((row) => row.category_id === id).length;
  const categoryId =
    nav.categoryId ?? (library.categories.find((cat) => countOf(cat.id) > 0) ?? library.categories[0])?.id ?? null;
  const category = library.categories.find((cat) => cat.id === categoryId);
  const items = library.items.filter((row) => row.category_id === categoryId);
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState<number | null>(null);
  const [error, setError] = useState("");

  // One category change is one library change: the three tabs and the folders follow (15.4.10).
  const attempt = async (action: () => Promise<unknown>) => {
    try {
      await action();
      setError("");
      return true;
    } catch (failure) {
      setError(failure instanceof ApiError && failure.status === 409 ? "已有这个分类" : "操作失败，请重试");
      return false;
    }
  };
  const remove = async (cat: CategoryRow) => {
    const count = countOf(cat.id);
    const question = count > 0 ? `删除分类「${cat.name}」？其中 ${count} 篇会移到「${UNCATEGORIZED}」。` : `删除分类「${cat.name}」？`;
    if (!window.confirm(question)) return;
    if (await attempt(() => api.deleteCategory(cat.id, count > 0))) {
      if (cat.id === categoryId) go({ type: "category", categoryId: null });
      await library.refresh();
    }
  };
  const open = (row: ItemRow) => {
    if (nav.categoryId !== categoryId) go({ type: "category", categoryId });
    go({ type: "item", itemId: row.id });
  };
  const drag = useItemDrag(async (id, targetId) => {
    const row = library.items.find((entry) => entry.id === id);
    if (!row || row.category_id === targetId) return;
    await api.moveItem(id, targetId);
    await library.refresh();
  });

  return (
    <div className="library">
      <ScrollArea className="categories">
        <div className="categories-head">
          <h2>分类</h2>
          <button type="button" className="icon-btn" aria-label="新建分类" title="新建分类" onClick={() => setCreating(true)}>
            {icons.plus}
          </button>
        </div>
        <ul aria-label="分类">
          {library.categories.map((cat) => (
            <li
              key={cat.id}
              className="category-row"
              data-current={cat.id === categoryId || undefined}
              data-category-id={cat.id}
              data-drop={drag.state?.target === cat.id || undefined}
            >
              {renaming === cat.id ? (
                <NameInput
                  label="分类名称"
                  initial={cat.name}
                  onCancel={() => setRenaming(null)}
                  onSubmit={async (name) => {
                    if (name !== cat.name && !(await attempt(() => api.renameCategory(cat.id, name)))) return;
                    setRenaming(null);
                    await library.refresh();
                  }}
                />
              ) : (
                <button
                  type="button"
                  className="category"
                  aria-current={cat.id === categoryId ? "true" : undefined}
                  onClick={() => go({ type: "category", categoryId: cat.id })}
                  onDoubleClick={() => cat.name !== UNCATEGORIZED && setRenaming(cat.id)}
                >
                  <span>{cat.name}</span>
                  <span className="count">{countOf(cat.id)}</span>
                </button>
              )}
              {cat.name !== UNCATEGORIZED && renaming !== cat.id && (
                <span className="category-actions">
                  <button type="button" className="icon-btn" aria-label={`改名「${cat.name}」`} title="改名" onClick={() => setRenaming(cat.id)}>
                    {icons.pencil}
                  </button>
                  <button type="button" className="icon-btn danger" aria-label={`删除「${cat.name}」`} title="删除" onClick={() => remove(cat)}>
                    {icons.trash}
                  </button>
                </span>
              )}
            </li>
          ))}
          {creating && (
            <li className="category-row">
              <NameInput
                label="新分类名称"
                initial=""
                onCancel={() => setCreating(false)}
                onSubmit={async (name) => {
                  if (!(await attempt(() => api.createCategory(name)))) return;
                  setCreating(false);
                  await library.refresh();
                }}
              />
            </li>
          )}
        </ul>
        {error && <p className="field-error category-error">{error}</p>}
      </ScrollArea>
      {drag.state && (
        <div className="drag-ghost" style={{ left: drag.state.x + 14, top: drag.state.y + 10 }} aria-hidden="true">
          {drag.state.title}
        </div>
      )}
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
              <div
                role="button"
                tabIndex={0}
                className="item-card"
                data-dragging={drag.state?.id === row.id || undefined}
                onPointerDown={(event) => drag.start(event, row)}
                onClick={() => !drag.consumeClick() && open(row)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  open(row);
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
              </div>
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

// Pointer-driven dragging of a card onto a category (15.4.10). Not HTML5 drag and drop: Chromium
// never starts one from a <button>, and Tauri on Windows takes over the window's drag and drop.
interface DragState {
  id: string;
  title: string;
  x: number;
  y: number;
  target: number | null;
}

function useItemDrag(onDrop: (itemId: string, categoryId: number) => void) {
  const [state, setState] = useState<DragState | null>(null);
  const suppressClick = useRef(false);
  const categoryAt = (x: number, y: number) => {
    const hit = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-category-id]");
    return hit ? Number(hit.dataset.categoryId) : null;
  };

  const start = (event: ReactPointerEvent, row: ItemRow) => {
    if (event.button !== 0) return;
    // A press on a card starts no text selection: sweeping across the page would select it.
    event.preventDefault();
    const origin = { x: event.clientX, y: event.clientY };
    let moved = false;
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
      window.removeEventListener("keydown", cancel);
      delete document.documentElement.dataset.dragging;
      setState(null);
    };
    const move = (next: PointerEvent) => {
      if (!moved && Math.hypot(next.clientX - origin.x, next.clientY - origin.y) < 6) return;
      if (!moved) {
        document.documentElement.dataset.dragging = "";
        window.getSelection()?.removeAllRanges();
      }
      moved = true;
      setState({ id: row.id, title: itemTitle(row), x: next.clientX, y: next.clientY, target: categoryAt(next.clientX, next.clientY) });
    };
    const finish = (up: PointerEvent) => {
      stop();
      if (!moved) return;
      // Only the click this very release makes (it fires before any timer) is swallowed; a drop
      // on a category makes no click on a card, and the next real click must still open one.
      suppressClick.current = true;
      setTimeout(() => {
        suppressClick.current = false;
      }, 0);
      const target = categoryAt(up.clientX, up.clientY);
      if (target !== null) onDrop(row.id, target);
    };
    const cancel = (key: KeyboardEvent) => {
      if (key.key !== "Escape") return;
      stop();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish);
    window.addEventListener("keydown", cancel);
  };

  /** The click that ends a drag must not open the card. */
  const consumeClick = () => {
    const suppressed = suppressClick.current;
    suppressClick.current = false;
    return suppressed;
  };

  return { state, start, consumeClick };
}

// The old unlabeled <select> looked like a filter but moved the item on change (15.4.10); a menu says what it does.
function ItemMenu({ item, library }: { item: ItemRow; library: Library }) {
  const { go } = useNav();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const others = library.categories.filter((cat) => cat.id !== item.category_id);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  const moveTo = async (cat: CategoryRow) => {
    setOpen(false);
    await api.moveItem(item.id, cat.id);
    go({ type: "category", categoryId: cat.id });
    go({ type: "item", itemId: item.id });
    await library.refresh();
  };
  const [filling, setFilling] = useState(false);
  const missingTags = itemTags(item).length === 0;
  const fillTags = async () => {
    setOpen(false);
    setFilling(true);
    await api.fillTags(item.id);
  };
  // Done when tags arrive; failed when the rerun's stages come and go without them.
  const sawRun = useRef(false);
  useEffect(() => {
    if (!missingTags) setFilling(false);
    if (!filling) return;
    if (item.stage) sawRun.current = true;
    else if (sawRun.current) {
      sawRun.current = false;
      setFilling(false);
    }
  }, [missingTags, filling, item.stage]);
  const remove = async () => {
    setOpen(false);
    if (!window.confirm(`删除「${itemTitle(item)}」及其知识库文件夹？`)) return;
    await api.deleteItem(item.id);
    go({ type: "close" });
    await library.refresh();
  };

  return (
    <div className="reader-actions" ref={box}>
      <button
        type="button"
        className="btn quiet small icon-only"
        aria-label="条目操作"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {icons.more}
      </button>
      {open && (
        <div className="popover item-menu" role="menu" aria-label="条目操作">
          {others.length > 0 && <div className="menu-label">移到</div>}
          {others.map((cat) => (
            <button key={cat.id} type="button" role="menuitem" aria-label={`移到「${cat.name}」`} onClick={() => moveTo(cat)}>
              {cat.name}
            </button>
          ))}
          {others.length > 0 && <div className="menu-sep" role="separator" />}
          {missingTags && (
            <button type="button" role="menuitem" disabled={filling} onClick={fillTags}>
              {filling ? "正在补全标签和摘要…" : "补全标签和摘要"}
            </button>
          )}
          <button type="button" role="menuitem" className="danger" onClick={remove}>
            删除
          </button>
        </div>
      )}
    </div>
  );
}

function NameInput({ label, initial, onSubmit, onCancel }: {
  label: string;
  initial: string;
  onSubmit: (name: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <input
      className="input category-input"
      aria-label={label}
      placeholder={label}
      autoFocus
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel();
        if (event.key === "Enter" && value.trim()) onSubmit(value.trim());
      }}
      onBlur={() => !value.trim() && onCancel()}
    />
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
