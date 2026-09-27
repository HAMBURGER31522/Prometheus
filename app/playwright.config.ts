import { defineConfig } from "@playwright/test";

// `npm run e2e` starts both servers itself (PLAN 15.4.5 / E6): the fake-pipeline backend
// on 8765 and Vite on 1420 in E2E mode. One worker: the tests share the backend.
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 60_000,
  use: { baseURL: "http://localhost:1420", trace: "off", viewport: { width: 1280, height: 800 } },
  webServer: [
    {
      command: "node scripts/e2e-backend.mjs",
      url: "http://127.0.0.1:8765/api/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // A dev server that is already up (a preview in use) is fine: without ?port=&token=
      // the page talks to 8765 / e2e, the fake backend started above.
      command: "npm run dev",
      url: "http://localhost:1420",
      reuseExistingServer: true,
      timeout: 60_000,
      env: { VITE_E2E: "1" },
    },
  ],
});
