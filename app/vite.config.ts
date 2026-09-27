import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

// Port 1420 / strictPort must match tauri.conf.json devUrl and the backend CORS whitelist (PLAN 8.1).
// Listen on 127.0.0.1: "localhost" resolved to ::1 only on this machine, where nothing could
// connect; pages still load as http://localhost:1420, which falls back to IPv4.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
