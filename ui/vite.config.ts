import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  // Use absolute base ('/') so that asset URLs resolve correctly regardless
  // of the route depth. With base: './', visiting /studies/load_flow would
  // make the browser request /studies/assets/index-*.js instead of
  // /assets/index-*.js, breaking the page on any route deeper than /.
  // Vercel's SPA fallback rewrite (vercel.json) serves index.html for all
  // non-asset paths, and the absolute base ensures assets always resolve
  // to the correct /assets/* location.
  base: "/",
  server: {
    port: 5173,
    fs: { strict: true },
    watch: {
      ignored: ["**/skills/**", "**/docs/**", "**/.git/**", "**/node_modules/**"],
    },
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
      "/ready": "http://localhost:8000",
      "/readyz": "http://localhost:8000",
      "/metrics": "http://localhost:8000",
      "/docs": "http://localhost:8000",
      "/openapi.json": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          // Split vendor libraries into separate chunks for better caching
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          "charts-vendor": ["recharts"],
          "animation-vendor": ["framer-motion"],
          "icons-vendor": ["lucide-react", "react-icons"],
          "state-vendor": ["zustand", "@tanstack/react-query"],
          "i18n-vendor": ["i18next", "react-i18next", "i18next-browser-languagedetector"],
        },
      },
    },
  },
});
