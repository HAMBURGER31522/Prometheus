// The report keeps its light paper (the agent draws charts for white paper, D-29), but is
// shown in the app's palette: the override is injected at display time and the file on
// disk is never touched (PLAN 15.4.5). Every value comes from tokens.css / motion.css at
// runtime. The injected script also serves the reader (PLAN 15.4.7): table of contents,
// zoom and click-to-zoom images, talking to the app through postMessage (the report runs
// sandboxed in an opaque origin).
import { chapterAt } from "./chapters";

/** Report template variable -> app token that supplies its value. */
export const REPORT_TOKENS: Record<string, string> = {
  "--paper": "--report-paper",
  "--canvas": "--report-paper",
  "--ink": "--report-ink",
  "--heading": "--report-heading",
  "--muted": "--report-muted",
  "--accent": "--report-accent",
  "--orange": "--report-orange",
  "--line": "--report-line",
  "--blue": "--report-blue",
  "--blue-wash": "--report-blue-wash",
  "--wash": "--report-wash",
  "--p-around": "--window",
  "--p-shadow": "--report-shadow",
  "--p-bar-from": "--report-bar-from",
  "--p-bar-to": "--report-bar-to",
  "--p-serif": "--font-serif",
  "--p-thumb": "--scroll-thumb",
  "--p-thumb-idle": "--scroll-thumb-idle",
  "--p-backdrop": "--report-backdrop",
  "--p-ease": "--ease-spatial",
  "--p-dur": "--dur-spatial",
  "--p-ease-fx": "--ease-effects",
  "--p-dur-fx": "--dur-effects",
};

export function reportThemeVars(read: (token: string) => string): Record<string, string> {
  return Object.fromEntries(Object.entries(REPORT_TOKENS).map(([name, token]) => [name, read(token)]));
}

const RULES = `
html, body { background: var(--p-around); }
.paper { box-shadow: var(--p-shadow); }
.paper:before, .paper:after { background: linear-gradient(90deg, var(--p-bar-from), var(--p-bar-to)); }
h1, h2, h3, .subtitle, .report-nav-title { font-family: var(--p-serif); }
/* The paper follows the window (15.4.10): 40px each side, at most 1280px; the template's left nav
   is hidden (the toolbar's 目录 does its job) so the template's room for it goes back to the text. */
.paper { width: auto; max-width: min(1280px, calc(100% - 80px)); margin-left: auto; margin-right: auto; }
.report-nav { display: none !important; }
.paper img { width: auto; max-width: 100%; height: auto; }
.paper svg.pz-capped { display: block; margin-left: auto; margin-right: auto; }
::-webkit-scrollbar { width: 12px; height: 12px; background: transparent; }
::-webkit-scrollbar-thumb {
  border: 4px solid transparent; border-radius: 12px; background-clip: padding-box;
  background-color: var(--p-thumb-idle);
}
::-webkit-scrollbar-thumb:hover,
html[data-scrolling]::-webkit-scrollbar-thumb,
html[data-scrolling] ::-webkit-scrollbar-thumb { border-width: 3px; background-color: var(--p-thumb); }
.pz-zoomable { cursor: zoom-in; }
.pz-lightbox {
  position: fixed; inset: 0; z-index: 2147483000; background: var(--p-backdrop); opacity: 0;
  transition: opacity var(--p-dur-fx) var(--p-ease-fx); cursor: zoom-out;
}
.pz-lightbox[data-open] { opacity: 1; }
.pz-image {
  position: fixed; left: 0; top: 0; max-width: none; margin: 0; transform-origin: 0 0; border-radius: 6px;
  box-shadow: var(--p-shadow); cursor: grab; user-select: none; -webkit-user-drag: none;
  transition: transform var(--p-dur) var(--p-ease);
}
.pz-image[data-dragging] { transition: none; cursor: grabbing; }
.pz-svg { background: var(--paper); }
.pz-nav {
  position: fixed; top: 50%; width: 44px; height: 64px; margin-top: -32px; border: 0; border-radius: 12px;
  background: var(--paper); color: var(--ink); opacity: .8; font-size: 32px; line-height: 1; cursor: pointer;
}
.pz-nav:hover { opacity: 1; }
.pz-nav:disabled { opacity: .25; cursor: default; }
.pz-prev { left: 20px; }
.pz-next { right: 20px; }
.pz-caption {
  position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%); display: flex; gap: 12px;
  align-items: baseline; max-width: min(80%, 900px); padding: 6px 14px; border-radius: 12px;
  background: var(--paper); color: var(--ink); font-size: 14px; line-height: 1.5; cursor: default;
}
.pz-count { color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
`;

const SCRIPT = `
(function () {
  var post = function (message) { parent.postMessage(message, "*"); };

  /* floating scrollbar: visible while scrolling, fades 800 ms after */
  var idle = 0;
  addEventListener("scroll", function () {
    document.documentElement.setAttribute("data-scrolling", "");
    clearTimeout(idle);
    idle = setTimeout(function () { document.documentElement.removeAttribute("data-scrolling"); }, 800);
  }, { passive: true, capture: true });

  /* In-page links (#s3 in the report's own table of contents): a srcdoc page resolves
     "#s3" against the app's address, so following it would load the app (a blank page). */
  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest('a[href^="#"]');
    if (!link) return;
    event.preventDefault();
    var id = decodeURIComponent(link.getAttribute("href").slice(1));
    var target = id ? document.getElementById(id) : document.documentElement;
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }, true);

  /* table of contents for the reader toolbar */
  function toc() {
    var items = [];
    document.querySelectorAll("h2").forEach(function (heading, index) {
      var target = (heading.closest && heading.closest("section[id]")) || heading;
      if (!target.id) target.id = "pz-s" + (index + 1);
      var copy = heading.cloneNode(true);
      copy.querySelectorAll(".num, .section-time").forEach(function (node) { node.remove(); });
      items.push({ id: target.id, title: copy.textContent.replace(/\\s+/g, " ").trim() });
    });
    return items;
  }

  /* zoom: the app sends a factor, the page eases towards it */
  var zoom = 1, frame = 0;
  function zoomTo(value) {
    cancelAnimationFrame(frame);
    var from = zoom, start = performance.now(), span = 220;
    function step(now) {
      var t = Math.min(1, (now - start) / span), eased = 1 - Math.pow(1 - t, 3);
      zoom = t < 1 ? from + (value - from) * eased : value;
      document.documentElement.style.zoom = String(zoom);
      if (t < 1) frame = requestAnimationFrame(step);
    }
    frame = requestAnimationFrame(step);
  }

  /* the chapter a moment belongs to (导图's 在精读中查看): chapters.ts, tested there and
     injected here from its source; the headings give it each chapter's time range */
  function toSeconds(label) {
    return label.split(":").reduce(function (total, part) { return total * 60 + Number(part); }, 0);
  }
  var chapterIndex = ${chapterAt.toString()};
  function chapterAt(seconds) {
    var headings = Array.prototype.slice.call(document.querySelectorAll("h2"));
    var ranges = headings.map(function (heading) {
      var match = heading.textContent.match(/(\\d{1,2}:\\d{2}(?::\\d{2})?)\\s*[–—-]\\s*(\\d{1,2}:\\d{2}(?::\\d{2})?)/);
      return match ? [toSeconds(match[1]), toSeconds(match[2])] : null;
    });
    var index = chapterIndex(ranges, seconds);
    if (index === null) return null;
    return (headings[index].closest && headings[index].closest("section[id]")) || headings[index];
  }

  addEventListener("message", function (event) {
    var data = event.data || {};
    if (data.type === "goto") {
      var target = document.getElementById(data.id);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (data.type === "goto-time" && typeof data.seconds === "number") {
      var chapter = chapterAt(data.seconds);
      if (chapter) chapter.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (data.type === "zoom" && typeof data.value === "number") {
      zoomTo(data.value);
    }
  });

  /* click-to-zoom pictures (like Discourse): float up from the page, wheel to zoom around the
     cursor, drag to move, the side buttons or ← → for the next picture in page order (PLAN
     15.4.11), click outside or Esc to fly back. Screenshots and drawn diagrams (top-level SVG) alike. */
  var open = null;
  function pictures() {
    return Array.prototype.filter.call(document.querySelectorAll(".paper img, main img, .paper svg, main svg"), function (el) {
      if (el.closest("a, button, .pz-lightbox")) return false;
      if (el.tagName.toLowerCase() !== "svg") return true;
      if (el.parentElement && el.parentElement.closest("svg")) return false;
      return el.getBoundingClientRect().width >= 160;
    });
  }
  function captionOf(el) {
    var figure = el.closest("figure");
    var caption = figure && figure.querySelector("figcaption");
    return caption ? caption.textContent.trim() : el.getAttribute("alt") || "";
  }
  function place(state) {
    state.image.style.transform = "translate(" + state.x + "px," + state.y + "px) scale(" + state.scale + ")";
  }
  function fromRect(state, rect) {
    state.scale = rect.width / state.width;
    state.x = rect.left;
    state.y = rect.top;
  }
  function navButton(label, text, className, onClick) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "pz-nav " + className;
    button.setAttribute("aria-label", label);
    button.textContent = text;
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      onClick();
    });
    return button;
  }
  function drag(state, image, event) {
    event.preventDefault();
    var startX = event.clientX, startY = event.clientY, fromX = state.x, fromY = state.y;
    image.setAttribute("data-dragging", "");
    image.setPointerCapture(event.pointerId);
    function move(e) {
      state.x = fromX + e.clientX - startX;
      state.y = fromY + e.clientY - startY;
      place(state);
    }
    function up() {
      image.removeAttribute("data-dragging");
      image.removeEventListener("pointermove", move);
      image.removeEventListener("pointerup", up);
    }
    image.addEventListener("pointermove", move);
    image.addEventListener("pointerup", up);
  }
  /* show el in the open viewer: flying up from its place, or straight in the middle */
  function mount(state, el, fly) {
    if (state.image) {
      state.image.remove();
      state.img.style.visibility = "";
    }
    var rect = el.getBoundingClientRect();
    var image = el.cloneNode(true);
    image.setAttribute("class", el.tagName.toLowerCase() === "svg" ? "pz-image pz-svg" : "pz-image");
    image.removeAttribute("width");
    image.removeAttribute("height");
    image.style.width = rect.width + "px";
    image.style.height = rect.height + "px";
    image.style.visibility = "";
    state.overlay.insertBefore(image, state.overlay.firstChild);
    state.img = el;
    state.image = image;
    state.width = rect.width;
    var natural = el.naturalWidth || rect.width * 2;
    state.fit = Math.min((innerWidth * 0.9) / rect.width, (innerHeight * 0.8) / rect.height, Math.max(1, natural / rect.width));
    el.style.visibility = "hidden";
    image.addEventListener("pointerdown", function (event) { drag(state, image, event); });
    function centre() {
      state.scale = state.fit;
      state.x = (innerWidth - rect.width * state.fit) / 2;
      state.y = (innerHeight - rect.height * state.fit) / 2;
      place(state);
    }
    image.setAttribute("data-dragging", "");
    if (fly) {
      fromRect(state, rect);
      place(state);
    } else {
      centre();
    }
    requestAnimationFrame(function () {
      image.removeAttribute("data-dragging");
      state.overlay.setAttribute("data-open", "");
      if (fly) centre();
    });
    state.index = state.list.indexOf(el);
    state.count.textContent = state.index + 1 + " / " + state.list.length;
    state.caption.textContent = captionOf(el);
    state.prev.disabled = state.index <= 0;
    state.next.disabled = state.index >= state.list.length - 1;
  }
  function step(delta) {
    if (!open) return;
    var next = open.list[open.index + delta];
    if (!next) return;
    next.scrollIntoView({ block: "center" }); /* the page behind follows, so closing flies back to it */
    mount(open, next, false);
  }
  function openImage(el) {
    if (open) return;
    var overlay = document.createElement("div");
    overlay.className = "pz-lightbox";
    var state = { overlay: overlay, image: null, img: el, list: pictures(), x: 0, y: 0, scale: 1 };
    state.prev = navButton("上一张", "‹", "pz-prev", function () { step(-1); });
    state.next = navButton("下一张", "›", "pz-next", function () { step(1); });
    var bar = document.createElement("div");
    bar.className = "pz-caption";
    state.count = document.createElement("span");
    state.count.className = "pz-count";
    state.caption = document.createElement("span");
    bar.appendChild(state.count);
    bar.appendChild(state.caption);
    overlay.appendChild(state.prev);
    overlay.appendChild(state.next);
    overlay.appendChild(bar);
    document.body.appendChild(overlay);
    open = state;
    mount(state, el, true);
    overlay.addEventListener("wheel", function (event) {
      event.preventDefault();
      var next = Math.min(state.fit * 4, Math.max(state.fit * 0.5, state.scale * Math.exp(-event.deltaY * 0.0015)));
      state.x = event.clientX - (event.clientX - state.x) * (next / state.scale);
      state.y = event.clientY - (event.clientY - state.y) * (next / state.scale);
      state.scale = next;
      place(state);
    }, { passive: false });
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) closeImage();
    });
  }
  function closeImage() {
    if (!open) return;
    var state = open;
    open = null;
    fromRect(state, state.img.getBoundingClientRect());
    place(state);
    state.overlay.removeAttribute("data-open");
    var done = function () {
      if (!state.overlay.parentNode) return;
      state.overlay.remove();
      state.img.style.visibility = "";
    };
    state.image.addEventListener("transitionend", done, { once: true });
    setTimeout(done, 700);
  }
  addEventListener("keydown", function (event) {
    if (!open) return;
    if (event.key === "Escape") closeImage();
    else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      step(event.key === "ArrowRight" ? 1 : -1);
    }
  });
  /* one listener for every picture, also those added after load */
  document.addEventListener("click", function (event) {
    if (open || !event.target.closest) return;
    var el = event.target.closest("img, svg");
    while (el && el.parentElement && el.parentElement.closest("svg")) el = el.parentElement.closest("svg");
    if (!el || pictures().indexOf(el) < 0) return;
    event.preventDefault();
    openImage(el);
  });

  function ready() {
    /* a chart is drawn for about 900px: a wider paper must not blow it up past its own width */
    document.querySelectorAll(".paper svg[viewBox]").forEach(function (svg) {
      if (svg.parentElement && svg.parentElement.closest("svg")) return;
      var width = parseFloat((svg.getAttribute("viewBox") || "").trim().split(/[^0-9.eE+-]+/)[2]);
      if (!(width > 0)) return;
      svg.style.maxWidth = width + "px";
      svg.classList.add("pz-capped");
    });
    pictures().forEach(function (el) { el.classList.add("pz-zoomable"); });
    post({ type: "toc", items: toc() });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready);
  else ready();
})();
`;

export function themeReport(html: string, vars: Record<string, string>): string {
  const declarations = Object.entries(vars)
    .map(([name, value]) => `  ${name}: ${value};`)
    .join("\n");
  const block = `<style id="prometheus-theme">\n:root {\n${declarations}\n}\n${RULES}</style>\n<script>${SCRIPT}</script>\n`;
  const head = html.search(/<\/head>/i);
  return head >= 0 ? html.slice(0, head) + block + html.slice(head) : block + html;
}
