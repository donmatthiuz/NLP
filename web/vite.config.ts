import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const puertoApi = process.env.LICIGT_API_PUERTO ?? '8000'

// Sin CORS en desarrollo: /api se reenvía al adaptador de consulta (make api).
// Tailwind v4 entra como plugin de Vite; "@" apunta a src, como pide shadcn/ui.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  server: {
    proxy: {
      '/api': { target: `http://127.0.0.1:${puertoApi}`, changeOrigin: true },
    },
  },
  test: { include: ['src/**/*.test.ts'] },
})
