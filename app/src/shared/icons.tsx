// Line icons, drawn with currentColor so they follow the text colour.
import type { ReactElement } from "react";

const svg = (children: ReactElement | ReactElement[]) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const icons = {
  console: svg([<path key="a" d="M4 5h16v14H4z" />, <path key="b" d="m8 10 3 2-3 2M13 15h3" />]),
  library: svg([<path key="a" d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z" />, <path key="b" d="M5 17a3 3 0 0 1 3-3h10M9 8h5" />]),
  mindmap: svg([<circle key="a" cx="6" cy="12" r="2.2" />, <circle key="b" cx="18" cy="6" r="2" />, <circle key="c" cx="18" cy="18" r="2" />, <path key="d" d="M8 11.2 16 6.8M8 12.8l8 4.4" />]),
  subtitle: svg([<rect key="a" x="3.5" y="5" width="17" height="14" rx="2.5" />, <path key="b" d="M7 11h4M13 11h4M7 15h10" />]),
  plus: svg(<path d="M12 5v14M5 12h14" />),
  pencil: svg([<path key="a" d="M15.5 5.5 18.5 8.5 9 18H6v-3z" />, <path key="b" d="m13.5 7.5 3 3" />]),
  trash: svg([<path key="a" d="M5 7h14M10 7V5h4v2" />, <path key="b" d="M7 7l1 12h8l1-12M10.5 11v5M13.5 11v5" />]),
  more: svg([<circle key="a" cx="6" cy="12" r="1.1" />, <circle key="b" cx="12" cy="12" r="1.1" />, <circle key="c" cx="18" cy="12" r="1.1" />]),
  settings: svg([<circle key="a" cx="12" cy="12" r="3" />, <path key="b" d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" />]),
};
