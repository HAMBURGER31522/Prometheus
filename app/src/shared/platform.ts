// Tauri capability wrappers; browser and E2E runs use fixed stand-ins (PLAN 9.4).

export interface BackendInfo {
  port: number;
  token: string;
}

const E2E = import.meta.env.VITE_E2E === "1";

type TauriWindow = Window & {
  __PROMETHEUS_BACKEND__?: BackendInfo;
  __TAURI__?: { core?: { invoke: (cmd: string) => Promise<BackendInfo> }; invoke?: (cmd: string) => Promise<BackendInfo> };
  __lastOpenedExternal?: string;
};

const inTauri = () => !E2E && Boolean((window as TauriWindow).__TAURI__);

export async function backendInfo(): Promise<BackendInfo> {
  if (E2E) return { port: 8765, token: "e2e" };
  const w = window as TauriWindow;
  if (w.__PROMETHEUS_BACKEND__) return w.__PROMETHEUS_BACKEND__;
  const invoke = w.__TAURI__?.core?.invoke ?? w.__TAURI__?.invoke;
  if (invoke) return invoke("backend_info");
  // Plain browser during development: ?port=&token=, else the dev backend.
  const params = new URLSearchParams(window.location.search);
  return { port: Number(params.get("port") ?? 8765), token: params.get("token") ?? "e2e" };
}

export async function pickDirectory(): Promise<string | null> {
  if (inTauri()) {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ directory: true });
    return typeof selected === "string" ? selected : null;
  }
  return window.prompt("输入文件夹路径：");
}

export async function pickFile(): Promise<string | null> {
  if (inTauri()) {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ multiple: false });
    return typeof selected === "string" ? selected : null;
  }
  return window.prompt("输入文件路径：");
}

/** Every link leaves the app through here (PLAN 9.3); E2E reads the last one back. */
export async function openExternal(url: string): Promise<void> {
  (window as TauriWindow).__lastOpenedExternal = url;
  if (inTauri()) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  } else if (!E2E) {
    window.open(url, "_blank", "noopener"); // plain-browser preview during development
  }
}

/** Save text through the webview's download (a .md / .srt / .txt export). */
export function downloadText(filename: string, text: string, type = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
