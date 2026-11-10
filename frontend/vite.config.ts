import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'

// Backend FastAPI chạy ở cổng 8000. Frontend gọi qua tiền tố /api để
// tránh trùng với các route giao diện như /product, /user...
const BACKEND = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

const pages = [
  'index', 'login', 'register', 'product', 'post', 'my-products',
  'favorites', 'messages', 'notifications', 'profile',
]

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: BACKEND,
        changeOrigin: true,
        ws: true, // WebSocket chat + thông báo
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    rollupOptions: {
      input: Object.fromEntries(pages.map((p) => [p, resolve(__dirname, `${p}.html`)])),
    },
  },
})
