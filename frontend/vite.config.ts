import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Ketcher's transitive deps (util, assert) reach for Node's `process.env`,
// which webpack defines for free but Vite doesn't. Without these defines,
// the canvas blanks out with a runtime "process is not defined" error.
export default defineConfig({
  plugins: [react()],
  define: {
    'process.env': {},
    global: 'globalThis',
  },
})
