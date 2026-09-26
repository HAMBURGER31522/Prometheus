// Shared "category → item → content" browser for the three content tabs (PLAN 9.3).

import { useEffect, useState } from "react";

import type { ReactNode } from "react";

import { ApiError, api } from "./api";
import type { CategoryRow, ItemRow } from "./api";

export interface LibrarySelection {
  categoryId: number | null;
  itemId: string | null;
}

export interface ContentTabProps {
  selection: LibrarySelection;
  onSelect: (selection: LibrarySelection) => void;
}

export interface LibraryBrowserProps {
  kind: "知识库" | "思维导图" | "字幕";
  selection: LibrarySelection;
  onSelect: (selection: LibrarySelection) => void;
  children: (item: ItemRow) => ReactNode;
}

const FORBIDDEN_RENAME = ["其他", "综合", "杂项"];

export default function LibraryBrowser(props: LibraryBrowserProps) {
  const [categories, setCategories] = useState<CategoryRow[]>([]);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [error, setError] = useState("");

  const refreshCategories = () => {
    api.getCategories().then(setCategories, (e: ApiError) => setError(String(e)));
  };

  useEffect(refreshCategories, []);

  useEffect(() => {
    if (props.selection.categoryId !== null) {
      api
        .getItems()
        .then((rows) =>
          setItems(rows.filter((row) => row.category_id === props.selection.categoryId)),
        )
        .catch(() => setItems([]));
    }
  }, [props.selection.categoryId]);

  if (props.selection.itemId !== null) {
    const item = items.find((row) => row.id === props.selection.itemId);
    if (!item) {
      return <p className="empty">条目加载中…</p>;
    }
    return (
      <section className="library">
        <nav className="breadcrumb" aria-label="面包屑">
          <button type="button" onClick={() => props.onSelect({ ...props.selection, itemId: null })}>
            {props.kind}
          </button>
          <span> / {currentCategoryName(categories, props.selection.categoryId)}</span>
          <span> / {item.report_title || item.source_title || item.video_id}</span>
        </nav>
        {props.children(item)}
      </section>
    );
  }

  if (props.selection.categoryId !== null) {
    return (
      <section className="library">
        <nav className="breadcrumb" aria-label="面包屑">
          <button type="button" onClick={() => props.onSelect({ categoryId: null, itemId: null })}>
            {props.kind}
          </button>
          <span> / {currentCategoryName(categories, props.selection.categoryId)}</span>
        </nav>
        <ul className="item-list">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className="row-main"
                onClick={() => props.onSelect({ ...props.selection, itemId: item.id })}
              >
                {item.report_title || item.source_title || item.video_id}
                <span className="row-sub">
                  {item.source_title} · {item.uploader} · {formatDuration(item.duration_s)}
                </span>
              </button>
            </li>
          ))}
          {items.length === 0 && <li className="empty">该分类暂无条目</li>}
        </ul>
      </section>
    );
  }

  return (
    <section className="library">
      <h2>{props.kind}</h2>
      {error && <p className="error">{error}</p>}
      <ul className="category-list">
        {categories.map((category) => (
          <li key={category.id}>
            <button
              type="button"
              className="row-main"
              onClick={() => props.onSelect({ ...props.selection, categoryId: category.id })}
            >
              {category.name}
              <span className="row-sub">{category.count} 个条目</span>
            </button>
            <span className="row-actions">
              <button
                type="button"
                onClick={async () => {
                  const name = window.prompt("重命名分类：", category.name);
                  if (!name || FORBIDDEN_RENAME.includes(name)) return;
                  try {
                    await api.renameCategory(category.id, name);
                    refreshCategories();
                  } catch (e) {
                    setError(e instanceof ApiError && e.status === 409 ? "分类名已存在" : String(e));
                  }
                }}
              >
                重命名
              </button>
              <button
                type="button"
                onClick={async () => {
                  const target = window.prompt("合并到分类：");
                  const targetRow = categories.find((c) => c.name === target);
                  if (!targetRow || targetRow.id === category.id) return;
                  await api.mergeCategory(category.id, targetRow.id);
                  refreshCategories();
                }}
              >
                合并到…
              </button>
              {category.count === 0 && (
                <button type="button" onClick={async () => {
                  try {
                    await api.deleteCategory(category.id);
                    refreshCategories();
                  } catch {
                    setError("删除失败：分类非空");
                  }
                }}>
                  删除
                </button>
              )}
            </span>
          </li>
        ))}
        {categories.length === 0 && <li className="empty">还没有任何分类</li>}
      </ul>
    </section>
  );
}

function currentCategoryName(categories: CategoryRow[], id: number | null): string {
  return categories.find((c) => c.id === id)?.name ?? "";
}

function formatDuration(duration_s: number | null): string {
  if (!duration_s) return "";
  const total = Math.round(duration_s);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
