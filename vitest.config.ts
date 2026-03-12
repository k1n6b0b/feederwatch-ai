/**
 * Root vitest config — runs frontend tests from tests/frontend/
 * while resolving modules from addon/frontend/node_modules.
 *
 * Run from project root:  npx vitest run --config vitest.config.ts
 * Or via addon/frontend:  npm test  (the include pattern picks these up via vite.config.ts)
 */

import { defineConfig } from './addon/frontend/node_modules/vite/dist/node/index.js'
import react from './addon/frontend/node_modules/@vitejs/plugin-react/dist/index.mjs'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Source files resolve relative to addon/frontend/src
      '@': path.resolve(__dirname, 'addon/frontend/src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: [path.resolve(__dirname, 'addon/frontend/src/test-setup.ts')],
    include: ['tests/frontend/**/*.{test,spec}.{ts,tsx}'],
    // Look for node_modules in addon/frontend first (where deps are installed)
    server: {
      deps: {
        moduleDirectories: [
          path.resolve(__dirname, 'addon/frontend/node_modules'),
          'node_modules',
        ],
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
    },
  },
})
