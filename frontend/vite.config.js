import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = (env.VITE_BACKEND_URL || "").replace(/\/+$/, "");

  return {
    server: {
      proxy: backend
        ? {
            // dev convenience: requests to /api/* go to your local backend
            "/api": {
              target: backend,
              changeOrigin: true,
              secure: false,
            },
          }
        : undefined,
    },
    build: { sourcemap: false },
  };
});








