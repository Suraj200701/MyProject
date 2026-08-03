/**
 * Optional desktop (Electron) integration.
 *
 * This repository ships a **web app only** — there is no Electron shell in it
 * today. But the requirement is that a desktop build opens Google Maps in an
 * embedded window while the web build opens a tab, and that decision has to be
 * made at runtime by the same code either way.
 *
 * So: the app looks for a `window.leadmaster` bridge that a future Electron
 * preload script would expose, and falls back to `window.open` when it is
 * absent. Nothing here assumes the bridge exists, and the web path is the one
 * that actually runs right now.
 *
 * A preload script would satisfy this contract with:
 *
 *     contextBridge.exposeInMainWorld("leadmaster", {
 *       openMapsWindow: (url) => ipcRenderer.invoke("open-maps-window", url),
 *       watchDownloads: (cb) => { ... },
 *     });
 */

export interface DesktopBridge {
  /** Opens a URL in an embedded browser window. Returns false if it couldn't. */
  openMapsWindow?: (url: string) => boolean | Promise<boolean>;
  /**
   * Notifies when a CSV lands in the user's Downloads folder.
   *
   * Only a desktop build can do this — a web page has no access to the
   * filesystem, and no browser API exposes the download directory. Returns an
   * unsubscribe function.
   */
  watchDownloads?: (onCsv: (file: File) => void) => () => void;
}

declare global {
  interface Window {
    leadmaster?: DesktopBridge;
  }
}

/** True when running inside the desktop shell rather than a browser tab. */
export function isDesktop(): boolean {
  return typeof window !== "undefined" && typeof window.leadmaster?.openMapsWindow === "function";
}

/** True when the desktop shell can watch the Downloads folder for us. */
export function canWatchDownloads(): boolean {
  return typeof window !== "undefined" && typeof window.leadmaster?.watchDownloads === "function";
}

/**
 * Opens Google Maps — embedded window on desktop, new tab on the web.
 *
 * `noopener,noreferrer` on the web path: without it the opened tab gets a
 * `window.opener` handle back into the app.
 */
export async function openExternal(url: string): Promise<boolean> {
  if (typeof window === "undefined") return false;

  const bridge = window.leadmaster;
  if (typeof bridge?.openMapsWindow === "function") {
    try {
      return (await bridge.openMapsWindow(url)) !== false;
    } catch {
      // Fall through to the browser path rather than leaving the user stuck.
    }
  }

  const opened = window.open(url, "_blank", "noopener,noreferrer");
  return opened !== null;
}
