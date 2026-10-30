import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { launchApp } = require('./electron/appLauncher.cjs')

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

      // Backend API endpoint for app launching in browser preview mode
      server.middlewares.use(async (req, res, next) => {
        if (!req.url || !req.url.startsWith('/api/launch-app')) {
          return next()
        }

        // Set full CORS headers so any origin / webview can reach it
        res.setHeader('Access-Control-Allow-Origin', '*')
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        res.setHeader('Access-Control-Allow-Headers', '*')

        if (req.method === 'OPTIONS') {
          res.statusCode = 204
          res.end()
          return
        }

        try {
          const parsedUrl = new URL(req.url, 'http://127.0.0.1:5173')
          const appId = parsedUrl.searchParams.get('appId') || ''
          const result = await launchApp(appId)
          res.setHeader('Content-Type', 'application/json')
          res.statusCode = 200
          res.end(JSON.stringify(result))
        } catch (err: unknown) {
          res.setHeader('Content-Type', 'application/json')
          res.statusCode = 500
          res.end(
            JSON.stringify({
              success: false,
              verified: false,
              displayName: 'Application',
              mode: 'real',
              error: err instanceof Error ? err.message : String(err),
            })
          )
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
    strictPort: true,
    cors: true,
  },
})
