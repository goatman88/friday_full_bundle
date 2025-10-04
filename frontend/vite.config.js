import { defineConfig } from 'vite';

export default defineConfig({
  define: {
    'process.env': process.env,
    'import.meta.env.VITE_BACKEND_URL': JSON.stringify('https://friday-backend-ksep.onrender.com')
  }
});












