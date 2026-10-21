import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', 'VITE_');
  if (mode === 'launch') {
    if (!/^pk_live_[A-Za-z0-9_-]+$/.test(env.VITE_CLERK_PUBLISHABLE_KEY || '')) {
      throw new Error('Launch builds require a production Clerk publishable key.');
    }
    const apiUrl = new URL(env.VITE_API_URL || 'invalid');
    if (apiUrl.protocol !== 'https:' || apiUrl.username || apiUrl.password || apiUrl.search || apiUrl.hash || !apiUrl.pathname.endsWith('/api')) {
      throw new Error('Launch builds require an exact HTTPS VITE_API_URL ending in /api.');
    }
    if (env.VITE_ENABLE_DIAGNOSTICS === 'true') throw new Error('Disable diagnostics for launch builds.');
    if (env.VITE_API_TIMEOUT_MS) {
      const timeout = Number(env.VITE_API_TIMEOUT_MS);
      if (!Number.isInteger(timeout) || timeout < 1_000 || timeout > 120_000) {
        throw new Error('VITE_API_TIMEOUT_MS must be between 1000 and 120000 milliseconds.');
      }
    }
  }
  return {
  plugins: [react(), tailwindcss()],
  envDir: '..',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
  };
})
