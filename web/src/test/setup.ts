// Configuration Vitest partagée (chargée via vite.config.ts `test.setupFiles`).
// jsdom n'implémente ni matchMedia ni EventSource : polyfills minimaux pour que les
// stores/composants qui les utilisent (thème, SSE) puissent être testés.
import '@testing-library/jest-dom/vitest';
import { beforeEach } from 'vitest';
import { authStore } from '../lib/stores/auth.svelte';

// Session (contrat §2.2) : par défaut, les tests tournent comme le serveur de dev sans mot
// de passe — authentification désactivée, tout est actif. Les tests d'auth fixent eux-mêmes
// l'état voulu (`authStore._resetForTests({ authEnabled: true, authenticated: false })`).
beforeEach(() => {
  authStore._resetForTests({ authEnabled: false });
});

if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
