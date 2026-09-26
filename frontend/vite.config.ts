import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The UI talks to the API under /api. In development Vite forwards it to the
// FastAPI server; in the Docker build nginx does the same, so the browser
// never needs CORS and the demo runs fully offline.
const api = process.env.PRAMANA_API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: api, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
})
