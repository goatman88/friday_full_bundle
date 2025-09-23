// Minimal dev proxy to your FastAPI backend on :8000
// Proxies both HTTP (/api/*) and WS (/realtime)
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      // WebSocket proxy for the server-side realtime bridge
      '/realtime': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true
      },
      // Optional: if you also expose a ws path like /ws
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true
      },
      // Ephemeral token fetch (HTTP) lives at /session on your backend
      '/session': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
});
