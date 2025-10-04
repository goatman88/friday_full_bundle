// frontend/vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      // send /api/* to the backend running on 8000
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        // keep the /api prefix (FastAPI routes are /api/...)
        // if your FastAPI routes did NOT include /api, you'd add:
        // rewrite: (path) => path.replace(/^\/api/, '')
      },
    },
  },
});
