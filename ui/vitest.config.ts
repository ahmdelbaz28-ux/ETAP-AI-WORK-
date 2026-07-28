import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: true,
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/tests/**", // Playwright E2E tests — run via npx playwright test
    ],
  },
});
