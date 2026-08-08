const { contextBridge, ipcRenderer } = require("electron");

// SECURITY: Using contextBridge.exposeInMainWorld is the correct pattern.
// - No nodeIntegration (renderer process has no Node.js access)
// - contextIsolation is enabled (preload runs in isolated context)
// - Only explicitly exposed functions are available to the renderer
//
// Note: ipcRenderer.on() listeners are never cleaned up in this file.
// The renderer should call onNavigate(null) etc. to remove old listeners
// before adding new ones, or use a wrapper that tracks and cleans up.
// This is a minor memory leak, not a security issue.

contextBridge.exposeInMainWorld("electronAPI", {
  // Window controls
  minimize: () => ipcRenderer.invoke("window:minimize"),
  maximize: () => ipcRenderer.invoke("window:maximize"),
  close: () => ipcRenderer.invoke("window:close"),
  isMaximized: () => ipcRenderer.invoke("window:isMaximized"),

  // Dialogs
  openFileDialog: (options) => ipcRenderer.invoke("dialog:open-file", options),
  saveFileDialog: (options) => ipcRenderer.invoke("dialog:save-file", options),

  // Shell — validates URL protocol before opening (prevents file:// access)
  openExternal: (url) => {
    // SECURITY: only allow http/https URLs to be opened externally
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        console.error("[preload] Refused to open non-HTTP URL:", url);
        return Promise.reject(new Error("Only HTTP(S) URLs are allowed"));
      }
    } catch {
      console.error("[preload] Invalid URL:", url);
      return Promise.reject(new Error("Invalid URL"));
    }
    return ipcRenderer.invoke("shell:open-external", url);
  },

  // App info
  getAppInfo: () => ipcRenderer.invoke("app:get-info"),
  getDisplayBounds: () => ipcRenderer.invoke("app:get-display-bounds"),

  // Menu events — use removeAllListeners to prevent listener accumulation
  onNavigate: (callback) => {
    ipcRenderer.removeAllListeners("navigate");
    if (callback) {
      ipcRenderer.on("navigate", (_, path) => callback(path));
    }
  },
  onNewProject: (callback) => {
    ipcRenderer.removeAllListeners("menu:new-project");
    if (callback) {
      ipcRenderer.on("menu:new-project", () => callback());
    }
  },
  onOpenProject: (callback) => {
    ipcRenderer.removeAllListeners("menu:open-project");
    if (callback) {
      ipcRenderer.on("menu:open-project", () => callback());
    }
  },
  onSave: (callback) => {
    ipcRenderer.removeAllListeners("menu:save");
    if (callback) {
      ipcRenderer.on("menu:save", () => callback());
    }
  },
  onExport: (callback) => {
    ipcRenderer.removeAllListeners("menu:export");
    if (callback) {
      ipcRenderer.on("menu:export", () => callback());
    }
  },
});
