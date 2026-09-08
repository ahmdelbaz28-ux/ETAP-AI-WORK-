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
    host: "127.0.0.1",
    port: 5173,
    fs: { strict: true },
    watch: {
      ignored: ["**/skills/**", "**/docs/**", "**/.git/**", "**/node_modules/**"],
    },
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/healthz": "http://127.0.0.1:8000",
      "/ready": "http://127.0.0.1:8000",
      "/readyz": "http://127.0.0.1:8000",
      "/metrics": "http://127.0.0.1:8000",
      "/docs": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // vite@8 (rolldown) requires manualChunks to be a function, not an object.
        manualChunks: (id: string) => {
          if (id.includes("node_modules")) {
            if (id.includes("react") || id.includes("react-dom") || id.includes("react-router")) {
              return "react-vendor";
            }
            if (id.includes("recharts")) {
              return "charts-vendor";
            }
            if (id.includes("framer-motion") || id.includes("gsap")) {
              return "animation-vendor";
            }
            if (id.includes("lucide-react") || id.includes("react-icons")) {
              return "icons-vendor";
            }
            if (id.includes("zustand") || id.includes("@tanstack/react-query")) {
              return "state-vendor";
            }
            if (id.includes("i18next") || id.includes("react-i18next")) {
              return "i18n-vendor";
            }
          }
        },
      },
    },
  },
});
