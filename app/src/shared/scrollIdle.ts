// Floating scrollbar rule (PLAN 15.4.5): the thumb shows while the area scrolls and fades
// 800 ms after the last scroll. CSS keys off [data-scrolling].

export function watchScrollIdle(el: HTMLElement, idleMs = 800): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const onScroll = () => {
    el.setAttribute("data-scrolling", "");
    clearTimeout(timer);
    timer = setTimeout(() => el.removeAttribute("data-scrolling"), idleMs);
  };
  el.addEventListener("scroll", onScroll, { passive: true });
  return () => {
    el.removeEventListener("scroll", onScroll);
    clearTimeout(timer);
    el.removeAttribute("data-scrolling");
  };
}
