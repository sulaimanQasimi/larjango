import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    origin: 'http://127.0.0.1:5173',
    cors: true
  },
  build: {
    outDir: 'public/build',
    manifest: true,
    rollupOptions: {
      input: {
        app: 'resources/js/app.jsx'
      }
    }
  }
})
