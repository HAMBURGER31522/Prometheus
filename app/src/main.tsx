import "@fontsource/noto-serif-sc/600.css";
import "./shared/tokens.css";
import "./shared/motion.css";
import "./shared/base.css";
import "./features/console/console.css";
import "./features/mindmap/mindmap.css";
import "./features/report/report.css";
import "./features/settings/settings.css";
import "./features/subtitle/subtitle.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
