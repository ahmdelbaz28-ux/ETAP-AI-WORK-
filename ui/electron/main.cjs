const {
  app,
  BrowserWindow,
  Menu,
  Tray,
  nativeImage,
  ipcMain,
  dialog,
  shell,
  screen,
} = require("electron");
const path = require("node:path");

let mainWindow = null;
let tray = null;
let isQuitting = false;

const isDev = !!process.env.VITE_DEV_SERVER_URL;
const APP_TITLE = "AhmedETAP Platform";
const MIN_WIDTH = 1024;
const MIN_HEIGHT = 700;
const DEFAULT_WIDTH = 1400;
const DEFAULT_HEIGHT = 900;

// ─── Window State Persistence ───────────────────────────────────────
const windowState = {
  x: undefined,
  y: undefined,
  width: DEFAULT_WIDTH,
  height: DEFAULT_HEIGHT,
  isMaximized: false,
};

function createWindow() {
  const { width, height, x, y } = windowState;

  mainWindow = new BrowserWindow({
    width,
    height,
    x,
    y,
    minWidth: MIN_WIDTH,
    minHeight: MIN_HEIGHT,
    title: APP_TITLE,
    icon: path.join(__dirname, isDev ? "../public/favicon.svg" : "../dist/favicon.svg"),
    frame: false,
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    trafficLightPosition: { x: 12, y: 12 },
    backgroundColor: "#0a0e1a",
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
      spellcheck: false,
      sandbox: true,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools({ mode: "detach" });
  });

  mainWindow.on("close", (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.on("resize", () => {
    if (mainWindow) {
      const bounds = mainWindow.getBounds();
      windowState.width = bounds.width;
      windowState.height = bounds.height;
      windowState.isMaximized = mainWindow.isMaximized();
    }
  });

  mainWindow.on("move", () => {
    if (mainWindow && !mainWindow.isMaximized()) {
      const bounds = mainWindow.getBounds();
      windowState.x = bounds.x;
      windowState.y = bounds.y;
    }
  });

  // IPC handlers
  ipcMain.handle("window:minimize", () => mainWindow?.minimize());
  ipcMain.handle("window:maximize", () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize();
    else mainWindow?.maximize();
  });
  ipcMain.handle("window:close", () => mainWindow?.hide());
  ipcMain.handle("window:isMaximized", () => mainWindow?.isMaximized() ?? false);

  ipcMain.handle("dialog:open-file", async (_, options) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openFile", "multiSelections"],
      filters: [
        { name: "ETAP Projects", extensions: ["etp", "xml"] },
        { name: "CSV Data", extensions: ["csv"] },
        { name: "JSON Config", extensions: ["json"] },
        { name: "All Files", extensions: ["*"] },
      ],
      ...options,
    });
    return result;
  });

  ipcMain.handle("dialog:save-file", async (_, options) => {
    const result = await dialog.showSaveDialog(mainWindow, {
      filters: [
        { name: "JSON", extensions: ["json"] },
        { name: "CSV", extensions: ["csv"] },
        { name: "PDF Report", extensions: ["pdf"] },
      ],
      ...options,
    });
    return result;
  });

  // SECURITY: Validate URL from renderer to prevent open-redirect / arbitrary protocol
  // attacks (SonarCloud S5144). Only http:, https:, and mailto: are permitted.
  // The IPC handler must never pass an unvalidated URL to shell.openExternal.
  ipcMain.handle("shell:open-external", (_, url) => {
    let parsed;
    try {
      parsed = typeof url === "string" ? new URL(url) : null;
    } catch {
      parsed = null;
    }
    if (!parsed || !["http:", "https:", "mailto:"].includes(parsed.protocol)) {
      const proto = parsed ? parsed.protocol : typeof url;
      throw new Error(`Blocked shell.openExternal for disallowed protocol: ${proto}`);
    }
    // Use parsed.href (validated URL) instead of original `url` to break the
    // taint flow and satisfy SonarCloud S5144 data-flow analysis.
    return shell.openExternal(parsed.href);
  });

  ipcMain.handle("app:get-info", () => ({
    version: app.getVersion(),
    platform: process.platform,
    arch: process.arch,
    electronVersion: process.versions.electron,
    chromeVersion: process.versions.chrome,
  }));

  ipcMain.handle("app:get-display-bounds", () => {
    const primaryDisplay = screen.getPrimaryDisplay();
    return primaryDisplay.workAreaSize;
  });

  // Load the app
  if (isDev) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  createMenu();
  createTray();
}

// ─── Application Menu ───────────────────────────────────────────────
function createMenu() {
  const template = [
    {
      label: "File",
      submenu: [
        {
          label: "New Project",
          accelerator: "CmdOrCtrl+N",
          click: () => mainWindow?.webContents.send("menu:new-project"),
        },
        {
          label: "Open Project...",
          accelerator: "CmdOrCtrl+O",
          click: () => mainWindow?.webContents.send("menu:open-project"),
        },
        { type: "separator" },
        {
          label: "Save",
          accelerator: "CmdOrCtrl+S",
          click: () => mainWindow?.webContents.send("menu:save"),
        },
        {
          label: "Export Results...",
          accelerator: "CmdOrCtrl+E",
          click: () => mainWindow?.webContents.send("menu:export"),
        },
        { type: "separator" },
        process.platform === "darwin"
          ? { role: "close" }
          : {
              label: "Exit",
              accelerator: "Alt+F4",
              click: () => {
                isQuitting = true;
                app.quit();
              },
            },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload", accelerator: "CmdOrCtrl+R" },
        { role: "forceReload", accelerator: "CmdOrCtrl+Shift+R" },
        { role: "toggleDevTools", accelerator: "CmdOrCtrl+Shift+I" },
        { type: "separator" },
        { role: "resetZoom", accelerator: "CmdOrCtrl+0" },
        { role: "zoomIn", accelerator: "CmdOrCtrl+=" },
        { role: "zoomOut", accelerator: "CmdOrCtrl+-" },
        { type: "separator" },
        { role: "togglefullscreen", accelerator: "F11" },
      ],
    },
    {
      label: "Studies",
      submenu: [
        {
          label: "Load Flow",
          accelerator: "CmdOrCtrl+1",
          click: () => mainWindow?.webContents.send("navigate", "/studies/load_flow"),
        },
        {
          label: "Short Circuit",
          accelerator: "CmdOrCtrl+2",
          click: () => mainWindow?.webContents.send("navigate", "/studies/short_circuit"),
        },
        {
          label: "Arc Flash",
          accelerator: "CmdOrCtrl+3",
          click: () => mainWindow?.webContents.send("navigate", "/studies/arc_flash"),
        },
        {
          label: "Harmonic Analysis",
          accelerator: "CmdOrCtrl+4",
          click: () => mainWindow?.webContents.send("navigate", "/studies/harmonic_analysis"),
        },
        { type: "separator" },
        {
          label: "AI Assistant",
          accelerator: "CmdOrCtrl+Shift+A",
          click: () => mainWindow?.webContents.send("navigate", "/assistant"),
        },
      ],
    },
    {
      label: "Help",
      submenu: [
        {
          label: "Documentation",
          click: () => shell.openExternal("https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-"),
        },
        {
          label: "Report Issue",
          click: () => shell.openExternal("https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues"),
        },
        { type: "separator" },
        {
          label: `About ${APP_TITLE}`,
          click: () =>
            dialog.showMessageBox(mainWindow, {
              type: "info",
              title: `About ${APP_TITLE}`,
              message: APP_TITLE,
              detail: `Version ${app.getVersion()}\nElectron ${process.versions.electron}\nChrome ${process.versions.chrome}\nNode ${process.versions.node}\n\nEnterprise-grade AI engineering platform for power systems.`,
            }),
        },
      ],
    },
  ];

  if (process.platform === "darwin") {
    template.unshift({
      label: app.name,
      submenu: [
        { role: "about" },
        { type: "separator" },
        { role: "services" },
        { type: "separator" },
        { role: "hide" },
        { role: "hideOthers" },
        { role: "unhide" },
        { type: "separator" },
        { role: "quit" },
      ],
    });
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ─── System Tray ────────────────────────────────────────────────────
function createTray() {
  try {
    const iconPath = path.join(__dirname, isDev ? "../public/favicon.svg" : "../dist/favicon.svg");
    const icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
    tray = new Tray(icon);
    tray.setToolTip(APP_TITLE);

    const contextMenu = Menu.buildFromTemplate([
      { label: `${APP_TITLE}`, enabled: false },
      { type: "separator" },
      {
        label: "Show Dashboard",
        click: () => {
          mainWindow?.show();
          mainWindow?.webContents.send("navigate", "/dashboard");
        },
      },
      {
        label: "Studies",
        click: () => {
          mainWindow?.show();
          mainWindow?.webContents.send("navigate", "/studies");
        },
      },
      { type: "separator" },
      {
        label: "Quit",
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);

    tray.setContextMenu(contextMenu);
    tray.on("double-click", () => mainWindow?.show());
  } catch (e) {
    // NOSONAR — javascript:S2486: tray creation is non-fatal
    // Tray creation can fail on some systems — non-fatal
    console.warn("Tray creation failed:", e instanceof Error ? e.message : String(e));
  }
}

// ─── App Lifecycle ──────────────────────────────────────────────────
app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else mainWindow?.show();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  isQuitting = true;
});
