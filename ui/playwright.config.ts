import { defineConfig, devices } from "@playwright/test";

const DEV_HOST = process.env.PLAYWRIGHT_DEV_HOST ?? "localhost";
const DEV_PORT = process.env.PLAYWRIGHT_DEV_PORT ?? "5173";
const DEV_URL = `http://${DEV_HOST}:${DEV_PORT}`;
const ROOT_DIR = import.meta.dirname;
// Skill pattern: multi-browser matrix (chromium/firefox/webkit/mobile) is
// opt-in via PLAYWRIGHT_BROWSERS=all to keep default CI fast and stable.
// Default runs chromium-only with --no-sandbox for container runners.
const ALL_BROWSERS = process.env.PLAYWRIGHT_BROWSERS === "all";

export default defineConfig({
  testDir: "./tests",
  // Generous per-test budget: lazy-loaded route chunks are transformed
  // on-demand by the Vite dev server, and the first navigation to a route can
  // take >5s on CI runners (measured ~10s locally on a cold server).
  timeout: 90_000,
  // Skill pattern: fail CI if test.only is committed; retry flaky tests in CI.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  fullyParallel: true,
  // Skill pattern: html + junit + json reporters for CI artifact triage.
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["junit", { outputFile: "playwright-results.xml" }],
    ["json", { outputFile: "playwright-results.json" }],
    ["list"],
  ],
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
    baseURL: process.env.BASE_URL || DEV_URL,
    headless: true,
    viewport: { width: 1920, height: 1080 },
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    // Skill pattern: artifact management — trace on retry, screenshot/video
    // only on failure to keep CI artifacts small but debuggable.
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  // Spawn the Vite dev server automatically (unless PLAYWRIGHT_NO_WEBSERVER=1,
  // in which case the developer is expected to run `npm run dev` themselves).
  webServer: process.env.PLAYWRIGHT_NO_WEBSERVER
    ? undefined
    : {
        command: `npx vite --port ${DEV_PORT} --host ${DEV_HOST}`,
        url: DEV_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        cwd: ROOT_DIR,
      },
  projects: ALL_BROWSERS
    ? [
        { name: "chromium", use: { ...devices["Desktop Chrome"] } },
        { name: "firefox", use: { ...devices["Desktop Firefox"] } },
        { name: "webkit", use: { ...devices["Desktop Safari"] } },
        { name: "mobile-chrome", use: { ...devices["Pixel 5"] } },
      ]
    : [
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
