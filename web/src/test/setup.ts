// Configuration Vitest partagée (chargée via vite.config.ts `test.setupFiles`).
// jsdom n'implémente ni matchMedia ni EventSource : polyfills minimaux pour que les
// stores/composants qui les utilisent (thème, SSE) puissent être testés.
import '@testing-library/jest-dom/vitest';

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
