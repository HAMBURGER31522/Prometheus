// Fake-pipeline backend for Playwright (PLAN 15.4.5 / E6): a fresh data dir per run,
// port 8765 and token "e2e" to match platform.ts in VITE_E2E mode.
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const repo = fileURLToPath(new URL("../..", import.meta.url));
const python = join(repo, ".venv", "Scripts", "python.exe");
const dataDir = mkdtempSync(join(tmpdir(), "prometheus-e2e-"));

const child = spawn(python, ["-m", "prometheus.server", "--port", "8765", "--token", "e2e"], {
  cwd: repo,
  env: { ...process.env, PROMETHEUS_FAKE: "1", PROMETHEUS_TEST_DATA_DIR: dataDir, PYTHONUTF8: "1" },
  stdio: "inherit",
});
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    child.kill();
    process.exit(0);
  });
}
child.on("exit", (code) => process.exit(code ?? 0));
