// PLAN 15.4.16: the installed app's page sent every request to the E2E port 8765, because it looked for
// window.__TAURI__, which Tauri 2 only sets with withGlobalTauri (installed run, 2026-09-30).
import { afterEach, describe, expect, it, vi } from "vitest";

type Injected = typeof globalThis & { isTauri?: boolean; __TAURI_INTERNALS__?: unknown };

describe("backendInfo", () => {
  afterEach(() => {
    delete (globalThis as Injected).isTauri;
    delete (globalThis as Injected).__TAURI_INTERNALS__;
    vi.resetModules();
  });

  it("asks the shell for the port and token when Tauri 2 runs the page", async () => {
    const invoke = vi.fn(async () => ({ port: 61466, token: "t0ken" }));
    (globalThis as Injected).__TAURI_INTERNALS__ = { invoke, transformCallback: () => 0 };
    (globalThis as Injected).isTauri = true;
    const { backendInfo } = await import("./platform");
    expect(await backendInfo()).toEqual({ port: 61466, token: "t0ken" });
    expect(invoke).toHaveBeenCalledWith("backend_info", {}, undefined);
  });

  it("reads ?port=&token= in a plain browser", async () => {
    window.history.pushState({}, "", "/?port=8766&token=shots");
    const { backendInfo } = await import("./platform");
    expect(await backendInfo()).toEqual({ port: 8766, token: "shots" });
    window.history.pushState({}, "", "/");
  });
});
