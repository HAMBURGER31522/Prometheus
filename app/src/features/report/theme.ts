// The report keeps its light paper (the agent draws charts for white paper, D-29), but is
// shown in the app's palette: the override is injected at display time and the file on
// disk is never touched (PLAN 15.4.5). Every value comes from tokens.css / motion.css at
// runtime. The injected script also serves the reader (PLAN 15.4.7): table of contents,
// zoom and click-to-zoom images, talking to the app through postMessage (the report runs
// sandboxed in an opaque origin).

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

  /* the chapter a moment belongs to (导图's 在精读中查看): the one that most recently started,
     as chapters overlap by a second and a mind map leaf sits at its chapter's start; a moment
     a little before the first chapter belongs to it (backend: mindmap/retrieve.py) */
  function toSeconds(label) {
    return label.split(":").reduce(function (total, part) { return total * 60 + Number(part); }, 0);
  }
  function chapterAt(seconds) {
    var best = null, bestStart = -1, first = null, firstStart = Infinity;
    document.querySelectorAll("h2").forEach(function (heading) {
      var match = heading.textContent.match(/(\\d{1,2}:\\d{2}(?::\\d{2})?)\\s*[–—-]\\s*(\\d{1,2}:\\d{2}(?::\\d{2})?)/);
      if (!match) return;
      var start = toSeconds(match[1]);
      var target = (heading.closest && heading.closest("section[id]")) || heading;
      if (start <= seconds && start > bestStart) { best = target; bestStart = start; }
      if (start < firstStart) { first = target; firstStart = start; }
    });
    return best || (first && firstStart - 5 <= seconds ? first : null);
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

  /* click-to-zoom images (like Discourse): float up from the page, wheel to zoom around
     the cursor, drag to move, click outside or Esc to fly back */
  var open = null;
  function place(state) {
    state.image.style.transform = "translate(" + state.x + "px," + state.y + "px) scale(" + state.scale + ")";
  }
  function fromRect(state, rect) {
    state.scale = rect.width / state.width;
    state.x = rect.left;
    state.y = rect.top;
  }
  function openImage(img) {
    if (open) return;
    var rect = img.getBoundingClientRect();
    var overlay = document.createElement("div");
    overlay.className = "pz-lightbox";
    var image = img.cloneNode(true);
    image.className = "pz-image";
    image.removeAttribute("width");
    image.removeAttribute("height");
    image.style.width = rect.width + "px";
    image.style.height = rect.height + "px";
    overlay.appendChild(image);
    document.body.appendChild(overlay);
    var state = { img: img, overlay: overlay, image: image, width: rect.width, x: 0, y: 0, scale: 1, moved: false };
    var natural = img.naturalWidth || rect.width * 2;
    var fit = Math.min((innerWidth * 0.9) / rect.width, (innerHeight * 0.9) / rect.height, Math.max(1, natural / rect.width));
    state.fit = fit;
    image.setAttribute("data-dragging", "");
    fromRect(state, rect);
    place(state);
    img.style.visibility = "hidden";
    open = state;
    requestAnimationFrame(function () {
      image.removeAttribute("data-dragging");
      overlay.setAttribute("data-open", "");
      state.scale = fit;
      state.x = (innerWidth - rect.width * fit) / 2;
      state.y = (innerHeight - rect.height * fit) / 2;
      place(state);
    });
    overlay.addEventListener("wheel", function (event) {
      event.preventDefault();
      var next = Math.min(state.fit * 4, Math.max(state.fit * 0.5, state.scale * Math.exp(-event.deltaY * 0.0015)));
      state.x = event.clientX - (event.clientX - state.x) * (next / state.scale);
      state.y = event.clientY - (event.clientY - state.y) * (next / state.scale);
      state.scale = next;
      place(state);
    }, { passive: false });
    image.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      var startX = event.clientX, startY = event.clientY, fromX = state.x, fromY = state.y;
      state.moved = false;
      image.setAttribute("data-dragging", "");
      image.setPointerCapture(event.pointerId);
      function move(e) {
        state.x = fromX + e.clientX - startX;
        state.y = fromY + e.clientY - startY;
        if (Math.abs(e.clientX - startX) + Math.abs(e.clientY - startY) > 3) state.moved = true;
        place(state);
      }
      function up() {
        image.removeAttribute("data-dragging");
        image.removeEventListener("pointermove", move);
        image.removeEventListener("pointerup", up);
      }
      image.addEventListener("pointermove", move);
      image.addEventListener("pointerup", up);
    });
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
  addEventListener("keydown", function (event) { if (event.key === "Escape") closeImage(); });

  function ready() {
    document.querySelectorAll(".paper img, main img").forEach(function (img) {
      if (img.closest("a")) return;
      img.classList.add("pz-zoomable");
      img.addEventListener("click", function (event) { event.preventDefault(); openImage(img); });
    });
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
