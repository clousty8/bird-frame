/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';

// Contrat d'API bird-frame §2.3 : en dev, /api est proxifié vers le serveur FastAPI
// (port 8090) pour rester même origine (SSE et Range sans souci CORS).
export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  // Sous Vitest, force la résolution du build client de Svelte (sinon les composants sont
  // compilés pour le SSR et `mount()` échoue avec "not available on the server").
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8090',
        changeOrigin: true,
      },
      // GET /health est hors préfixe /api/v1 (contrat §1.12) : proxifié séparément.
      '/health': {
        target: 'http://localhost:8090',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['tests/**/*.test.ts'],
  },
});
