const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  // Window controls
  minimize: () => ipcRenderer.invoke("window:minimize"),
  maximize: () => ipcRenderer.invoke("window:maximize"),
  close: () => ipcRenderer.invoke("window:close"),
  isMaximized: () => ipcRenderer.invoke("window:isMaximized"),

  // Dialogs
  openFileDialog: (options) => ipcRenderer.invoke("dialog:open-file", options),
  saveFileDialog: (options) => ipcRenderer.invoke("dialog:save-file", options),

  // Shell
  openExternal: (url) => ipcRenderer.invoke("shell:open-external", url),

  // App info
  getAppInfo: () => ipcRenderer.invoke("app:get-info"),
  getDisplayBounds: () => ipcRenderer.invoke("app:get-display-bounds"),

  // Menu events
  onNavigate: (callback) => ipcRenderer.on("navigate", (_, path) => callback(path)),
  onNewProject: (callback) => ipcRenderer.on("menu:new-project", () => callback()),
  onOpenProject: (callback) => ipcRenderer.on("menu:open-project", () => callback()),
  onSave: (callback) => ipcRenderer.on("menu:save", () => callback()),
  onExport: (callback) => ipcRenderer.on("menu:export", () => callback()),
});
