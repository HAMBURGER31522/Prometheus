// One source for 知识库, 思维导图 and 字幕: the same categories and items in all three (E6 ③).
import { useCallback, useEffect, useState } from "react";

import { type CategoryRow, type ItemRow, api } from "./api";

export interface Library {
  categories: CategoryRow[];
  items: ItemRow[];
  loaded: boolean;
  refresh: () => Promise<void>;
}

const UNCATEGORIZED = "未分类";

export function useLibrary(pollMs = 4000): Library {
  const [categories, setCategories] = useState<CategoryRow[]>([]);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    const [cats, rows] = await Promise.all([api.categories(), api.items()]);
    const done = rows.filter((row) => row.status === "done");
    // Every category, empty ones too (hiding them left no way to move an item back, 15.4.10); 未分类 last.
    const shown = cats
      .sort((a, b) => Number(a.name === UNCATEGORIZED) - Number(b.name === UNCATEGORIZED) || a.name.localeCompare(b.name, "zh-CN"));
    setCategories(shown);
    setItems(done.sort((a, b) => (b.finished_at ?? "").localeCompare(a.finished_at ?? "")));
    setLoaded(true);
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = () => alive && refresh().catch(() => undefined);
    tick();
    const timer = setInterval(tick, pollMs);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [refresh, pollMs]);

  return { categories, items, loaded, refresh };
}
