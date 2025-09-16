import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: process.env.VITE_API_BASE
      ? undefined
      : {
          '/api': {
            target: 'http://localhost:8000', // change if you run a local backend
            changeOrigin: true,
          }
        }
  }
})
