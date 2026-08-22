import { defineConfig } from "@playwright/test";

const DEV_HOST = process.env.PLAYWRIGHT_DEV_HOST ?? "localhost";
const DEV_PORT = process.env.PLAYWRIGHT_DEV_PORT ?? "5173";
const DEV_URL = `http://${DEV_HOST}:${DEV_PORT}`;
const ROOT_DIR = import.meta.dirname;

export default defineConfig({
  testDir: "./tests",
  // Generous per-test budget: lazy-loaded route chunks are transformed
  // on-demand by the Vite dev server, and the first navigation to a route can
  // take >5s on CI runners (measured ~10s locally on a cold server).
  timeout: 90_000,
  retries: 0,
  fullyParallel: false,
  expect: {
    // Auto-waiting assertions (toBeVisible, poll, etc.). Must exceed the
    // cold-transform time of lazily imported pages or the first test that
    // visits each route fails spuriously.
    timeout: 15_000,
  },
  use: {
    // Allow overriding the dev-server host/port via env vars (useful in
    // sandboxed environments where Playwright's chromium cannot resolve
    // `localhost`). Default keeps `localhost` to match the documented dev
    // workflow.
    baseURL: DEV_URL,
    headless: true,
    viewport: { width: 1920, height: 1080 },
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
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
