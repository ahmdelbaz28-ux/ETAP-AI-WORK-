/**
 * Vitest configuration — resolves React module duplication by:
 * 1. Externalizing React packages to prevent Vite transformation
 * 2. Deduplicating React to prevent multiple instances
 */
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom", "react-is", "scheduler"],
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/tests/**",
    ],
    // Force SSR transform mode for all files to ensure consistent module resolution
    transformMode: {
      web: {
        exclude: [/.*/], // Use SSR mode for all files
      },
    },
  },
  // Externalize React packages to prevent Vite transformation
  server: {
    deps: {
      external: ["react", "react-dom", "react-is", "scheduler", "@testing-library/react"],
    },
  },
});