// Left sidebar: fixed five tabs in PLAN 2.1 order.

export const TABS = ["控制台", "知识库", "思维导图", "字幕", "设置"] as const;
export type Tab = (typeof TABS)[number];

export default function Sidebar(props: {
  current: Tab;
  onSelect: (tab: Tab) => void;
}) {
  return (
    <nav className="sidebar" aria-label="主导航">
      {TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          className={tab === props.current ? "tab current" : "tab"}
          onClick={() => props.onSelect(tab)}
        >
          {tab}
        </button>
      ))}
    </nav>
  );
}
