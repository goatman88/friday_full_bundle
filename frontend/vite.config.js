import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Use env var for backend API
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL,
        changeOrigin: true,
        secure: false,
      }
    }
  }
})



