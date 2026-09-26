// Tauri capability wrappers; browser/E2E runs use fixed stubs (PLAN 9.4).

export interface BackendInfo {
  port: number;
  token: string;
}

const E2E = import.meta.env.VITE_E2E === "1";

export const recordedExternal: string[] = [];

export async function backendInfo(): Promise<BackendInfo> {
  if (E2E) return { port: 8765, token: "e2e" };
  const globalWindow = window as unknown as {
    __PROMETHEUS_BACKEND__?: BackendInfo;
    __TAURI__?: { invoke: (cmd: string) => Promise<BackendInfo> };
  };
  if (globalWindow.__PROMETHEUS_BACKEND__) return globalWindow.__PROMETHEUS_BACKEND__;
  if (globalWindow.__TAURI__) return globalWindow.__TAURI__.invoke("backend_info");
  // Plain browser dev: allow explicit override via URL, else default dev backend.
  const params = new URLSearchParams(window.location.search);
  return {
    port: Number(params.get("port") ?? 8765),
    token: params.get("token") ?? "e2e",
  };
}

export async function pickDirectory(): Promise<string | null> {
  if (!E2E && (window as unknown as { __TAURI__?: unknown }).__TAURI__) {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ directory: true });
    return typeof selected === "string" ? selected : null;
  }
  return window.prompt("输入数据目录路径：");
}

export async function pickFile(): Promise<string | null> {
  if (!E2E && (window as unknown as { __TAURI__?: unknown }).__TAURI__) {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ multiple: false });
    return typeof selected === "string" ? selected : null;
  }
  return window.prompt("输入文件路径：");
}

export async function openExternal(url: string): Promise<void> {
  recordedExternal.push(url);
  (window as unknown as { __lastOpenedExternal?: string }).__lastOpenedExternal = url;
  if (!E2E && (window as unknown as { __TAURI__?: unknown }).__TAURI__) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  }
}
