import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  resolve: {
    // Ensure only one copy of Three.js is loaded regardless of how many
    // packages (react-force-graph-3d, three-spritetext, etc.) declare it
    // as a dependency.
    dedupe: ['three'],
  },
})
