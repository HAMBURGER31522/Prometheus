// Where the user is (PLAN 15.4.5). The sidebar highlight is always `tab`; opening an item
// never changes it, and 精读 / 导图 / 字幕 are the same item seen through three tabs.

export type Tab = "console" | "library" | "mindmap" | "subtitle" | "settings";

export const TABS: { id: Tab; label: string }[] = [
  { id: "console", label: "控制台" },
  { id: "library", label: "知识库" },
  { id: "mindmap", label: "思维导图" },
  { id: "subtitle", label: "字幕" },
  { id: "settings", label: "设置" },
];

/** The reader's switch: same item, three tabs. */
export const READER_VIEWS: { id: Tab; label: string }[] = [
  { id: "library", label: "精读" },
  { id: "mindmap", label: "导图" },
  { id: "subtitle", label: "字幕" },
];

export interface NavState {
  tab: Tab;
  categoryId: number | null;
  itemId: string | null;
  /** A moment (seconds) the next view should show once: 导图's 「在精读中查看」 (PLAN 15.4.9). */
  at?: number;
}

export type NavAction =
  | { type: "tab"; tab: Tab; at?: number }
  | { type: "category"; categoryId: number | null }
  | { type: "item"; itemId: string }
  | { type: "close" };

export const initialNav: NavState = { tab: "console", categoryId: null, itemId: null };

export function navReducer(state: NavState, action: NavAction): NavState {
  switch (action.type) {
    case "tab":
      return { ...state, tab: action.tab };
    case "category":
      return { ...state, categoryId: action.categoryId, itemId: null };
    case "item":
      return { ...state, itemId: action.itemId };
    case "close":
      return { ...state, itemId: null };
  }
}
