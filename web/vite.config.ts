/// <reference types="vitest/config" />
import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import { playwright } from '@vitest/browser-playwright'

// The ViralTrack API (D5) is localhost-only and has no authentication. The UI reaches it through this
// same-origin proxy, so the API keeps CORS closed. Both servers bind to the loopback interface only.
const API_TARGET = process.env.VT_API_PROXY_TARGET ?? 'http://127.0.0.1:8000'
if (!/^http:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$/.test(API_TARGET)) {
  throw new Error(
    `VT_API_PROXY_TARGET must be a loopback http URL, got ${API_TARGET}`
  )
}
const proxy = { '/api': { target: API_TARGET, changeOrigin: false } }

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Pre-bundle every runtime dependency: lazily loaded route chunks would otherwise make Vite discover and
  // re-optimize them mid-run, which reloads the page and duplicates React in browser tests.
  optimizeDeps: {
    include: [
      '@radix-ui/react-alert-dialog',
      '@radix-ui/react-collapsible',
      '@radix-ui/react-dialog',
      '@radix-ui/react-direction',
      '@radix-ui/react-dropdown-menu',
      '@radix-ui/react-label',
      '@radix-ui/react-popover',
      '@radix-ui/react-radio-group',
      '@radix-ui/react-scroll-area',
      '@radix-ui/react-select',
      '@radix-ui/react-separator',
      '@radix-ui/react-slot',
      '@radix-ui/react-tooltip',
      '@tanstack/react-query',
      '@tanstack/react-router',
      'class-variance-authority',
      'clsx',
      'cmdk',
      'lucide-react',
      'openapi-fetch',
      'react',
      'react-dom',
      'react-top-loading-bar',
      'sonner',
      'tailwind-merge',
      'zod',
      'axe-core',
      'react-dom/client',
      'react/jsx-runtime',
      'vitest-browser-react',
    ],
  },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
  test: {
    silent: 'passed-only',
    unstubEnvs: true,
    browser: {
      enabled: true,
      provider: playwright(),
      instances: [{ browser: 'chromium' }],
    },
    coverage: {
      exclude: [
        'src/components/ui/**',
        'src/assets/**',

        'src/routeTree.gen.ts',
        'src/test-utils/**',
        'src/routes/**',
        'src/lib/api/schema.d.ts',
      ],
    },
  },
})
