import { type Dispatch, type ReactNode, createContext, startTransition, useCallback, useContext, useReducer } from "react";

import { type NavAction, type NavState, initialNav, navReducer } from "./nav";

const NavContext = createContext<{ nav: NavState; go: Dispatch<NavAction> } | null>(null);

export function NavProvider({ children, initial = initialNav }: { children: ReactNode; initial?: NavState }) {
  const [nav, dispatch] = useReducer(navReducer, initial);
  // Navigating inside a transition lets <ViewTransition> animate the page change.
  const go = useCallback((action: NavAction) => startTransition(() => dispatch(action)), []);
  return <NavContext value={{ nav, go }}>{children}</NavContext>;
}

export function useNav() {
  const value = useContext(NavContext);
  if (!value) throw new Error("useNav outside NavProvider");
  return value;
}
