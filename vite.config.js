// frontend/vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      // Any request starting with /api will be forwarded to FastAPI in dev
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
