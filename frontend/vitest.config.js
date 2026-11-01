import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.mjs'],
    exclude: ['tests/**/module-icon.test.mjs', 'tests/**/module-icon-error-wiring.test.mjs',
      'tests/**/unified-timeout-settings.test.mjs', 'tests/**/http-error-message.test.mjs',
      'tests/**/icon-error-message.test.mjs'],
  },
})
