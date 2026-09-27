// Stub (R7 red).
export type Tab = "console" | "library" | "mindmap" | "subtitle" | "settings";

export const TABS: { id: Tab; label: string }[] = [];

export interface NavState {
  tab: Tab;
  categoryId: number | null;
  itemId: string | null;
}

export type NavAction =
  | { type: "tab"; tab: Tab }
  | { type: "category"; categoryId: number | null }
  | { type: "item"; itemId: string }
  | { type: "close" };

export const initialNav: NavState = { tab: "console", categoryId: null, itemId: null };

export function navReducer(state: NavState, _action: NavAction): NavState {
  return state;
}
