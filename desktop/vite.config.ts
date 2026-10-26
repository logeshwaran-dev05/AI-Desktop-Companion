import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'
import fs from 'node:fs'
import path from 'node:path'

function electronDevServerPlugin(): Plugin {
  return {
    name: 'electron-dev-server-info',
    configureServer(server) {
      server.httpServer?.once('listening', () => {
        const address = server.httpServer?.address()
        const port = typeof address === 'object' && address ? address.port : 5173
        const devServerUrl = `http://127.0.0.1:${port}`
        const urlFile = path.resolve(import.meta.dirname, 'dev-server-url.txt')
        try {
          fs.writeFileSync(urlFile, devServerUrl, 'utf8')
        } catch (err) {
          console.warn('Failed to write dev-server-url.txt:', err)
        }
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), electronDevServerPlugin()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
  },
})

