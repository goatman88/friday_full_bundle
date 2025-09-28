import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      // Anything starting with /api will be forwarded to FastAPI on 8000
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // DO NOT rewrite; our backend paths already start with /api
        // rewrite: (p) => p,
      },
    },
  },
})


