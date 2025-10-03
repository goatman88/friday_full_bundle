// frontend/vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    // When running `npm run dev`, calls to /api/* will be proxied to localhost:8000
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});






