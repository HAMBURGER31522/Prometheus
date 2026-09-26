import { defineConfig } from "@playwright/test";

// The backend (8765) and Vite dev server (1420) are started externally;
// CI does not run E2E (PLAN 11).
export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL: "http://localhost:1420",
    trace: "off",
  },
  timeout: 60_000,
});
