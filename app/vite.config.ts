import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

// Port 1420 / strictPort must match tauri.conf.json devUrl and the backend CORS whitelist (PLAN 8.1).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 1420,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
