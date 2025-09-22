import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_API_BASE || 'http://localhost:8000';
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        // direct hits
        '/health': { target, changeOrigin: true },
        // your API routes
        '/api': { target, changeOrigin: true },
      },
    },
  };
});
