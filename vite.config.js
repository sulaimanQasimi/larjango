import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/static/build/',
  publicDir: false,
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    origin: 'http://127.0.0.1:5173',
    cors: true
  },
  build: {
    outDir: 'public/build',
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        app: 'resources/js/app.jsx'
      }
    }
  }
})
