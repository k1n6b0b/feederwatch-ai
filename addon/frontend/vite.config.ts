import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // base: './' ensures relative asset paths — required for HA Ingress
  // which mounts the app at a dynamic prefix like /api/hassio_ingress/<token>/
  base: './',
  build: {
    outDir: 'dist',
    minify: 'terser',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    // Tests live in tests/frontend/ (two levels up from addon/frontend/)
    include: [
      'src/**/*.{test,spec}.{ts,tsx}',
      '../../tests/frontend/**/*.{test,spec}.{ts,tsx}',
    ],
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '../../tests/frontend/node_modules/**',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
    },
  },
  server: {
    port: 5173,
    fs: {
      // Allow vitest to load test files from tests/frontend/ (two levels up)
      allow: ['../..'],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8099',
        changeOrigin: true,
      },
    },
  },
})
