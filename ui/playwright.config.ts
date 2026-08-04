import { defineConfig } from "@playwright/test";

const DEV_HOST = process.env.PLAYWRIGHT_DEV_HOST ?? "localhost";
const DEV_PORT = process.env.PLAYWRIGHT_DEV_PORT ?? "5173";
const DEV_URL = `http://${DEV_HOST}:${DEV_PORT}`;
const ROOT_DIR = import.meta.dirname;

export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  retries: 0,
  fullyParallel: false,
  use: {
    // Allow overriding the dev-server host/port via env vars (useful in
    // sandboxed environments where Playwright's chromium cannot resolve
    // `localhost`). Default keeps `localhost` to match the documented dev
    // workflow.
    baseURL: DEV_URL,
    headless: true,
    viewport: { width: 1920, height: 1080 },
    actionTimeout: 10000,
    screenshot: "only-on-failure",
  },
  // Spawn the Vite dev server automatically (unless PLAYWRIGHT_NO_WEBSERVER=1,
  // in which case the developer is expected to run `npm run dev` themselves).
  webServer: process.env.PLAYWRIGHT_NO_WEBSERVER
    ? undefined
    : {
        command: `npx vite --port ${DEV_PORT} --host ${DEV_HOST}`,
        url: DEV_URL,
        reuseExistingServer: true,
        timeout: 60_000,
        cwd: ROOT_DIR,
      },
  projects: [
    {
      name: "chromium",
      use: {
        browserName: "chromium",
        launchOptions: {
          args: ["--no-sandbox", "--disable-setuid-sandbox"],
        },
      },
    },
  ],
});
