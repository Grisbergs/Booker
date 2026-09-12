import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'url'

const ds = (pkg) =>
  fileURLToPath(new URL(`./src/design-system/${pkg}`, import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@ds/button':      ds('button'),
      '@ds/input':       ds('input'),
      '@ds/textarea':    ds('textarea'),
      '@ds/card':        ds('card'),
      '@ds/alert':       ds('alert'),
      '@ds/modal':       ds('modal'),
      '@ds/page-layout': ds('page-layout'),
      '@ds/form-group':  ds('form-group'),
      '@ds/badge':       ds('badge'),
      '@ds/theme':       ds('theme'),
      '@ds':             ds(''),
    },
  },
})
