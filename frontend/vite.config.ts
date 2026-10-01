import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.VITE_BACKEND_ORIGIN ?? 'http://127.0.0.1:8765'

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5287,
      strictPort: true,
      proxy: {
        '/api': backend,
        '/media': backend,
      },
    },
    preview: { host: '0.0.0.0', port: 5287 },
    build: {
      // three.js alone is ~1 MB minified; it is split into its own cacheable chunk.
      chunkSizeWarningLimit: 1100,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (/node_modules\/(three|@react-three)/.test(id)) return 'three'
          },
        },
      },
    },
  }
})
