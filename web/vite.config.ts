import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const puertoApi = process.env.LICIGT_API_PUERTO ?? '8000'

// Sin CORS en desarrollo: /api se reenvía al adaptador de consulta (make api).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: `http://127.0.0.1:${puertoApi}`, changeOrigin: true },
    },
  },
  test: { include: ['src/**/*.test.ts'] },
})
