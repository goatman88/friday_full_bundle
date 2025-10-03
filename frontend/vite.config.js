import { defineConfig, loadEnv } from 'vite';

export default ({ mode }) => {
  // load .env/.env.local values as plain strings
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_BACKEND_URL || 'http://localhost:8000';

  return defineConfig({
    server: {
      // dev-only proxy so your local Vite app can call /api/* without CORS
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    // nothing special needed for build; our JS will call the absolute URL
  });
};





