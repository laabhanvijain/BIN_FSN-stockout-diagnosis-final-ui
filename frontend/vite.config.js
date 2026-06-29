import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy /api/* to the FastAPI backend
      // In Docker, use service name (backend:8000); for local dev, set VITE_BACKEND_URL=http://localhost:8000
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
