import { defineConfig } from 'vite'
export default defineConfig({
  define: {
    __BACKEND__: JSON.stringify(process.env.VITE_BACKEND_URL || '')
  }
  export default {
  root: './frontend',
  build: { outDir: 'dist' }
}

})
