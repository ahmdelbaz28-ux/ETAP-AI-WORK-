<<<<<<< HEAD
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Minimal config matching Vitest official React 19 example
// to diagnose if extra config causes the Proxy wrapping issue
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/tests/**",
    ],
  },
});
=======
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: true,
  },
})
>>>>>>> origin/fix/scenario-tests-properly
