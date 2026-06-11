import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss(), react()],
  base: './',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:4111',
      '/health': 'http://localhost:4111',
      '/metrics': 'http://localhost:4111',
    },
  },
  build: {
    outDir: 'dist',
  },
})
