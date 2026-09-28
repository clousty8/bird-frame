// Store global de site : liste des sites (GET /api/v1/sites), site courant persisté en
// localStorage, exposé à toutes les pages. Singleton (un seul état pour toute l'appli),
// pattern objet + accesseurs recommandé pour un module .svelte.ts en Svelte 5.

import { getSites, ApiRequestError } from '../api/client';
import type { Site } from '../api/types';

const STORAGE_KEY = 'bird-frame:selected-site';

function readStoredSlug(): string | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
  } catch {
    // Stockage indisponible (navigation privée, quota, etc.) : pas de préférence retenue,
    // ce n'est jamais bloquant pour l'appli.
    return null;
  }
}

function writeStoredSlug(slug: string | null): void {
  try {
    if (typeof localStorage === 'undefined') return;
    if (slug) localStorage.setItem(STORAGE_KEY, slug);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Idem : perte silencieuse acceptable, la sélection reste correcte pour la session en cours.
  }
}

let sites = $state<Site[]>([]);
let selectedSlug = $state<string | null>(readStoredSlug());
let loading = $state(false);
let error = $state<string | null>(null);
let loaded = $state(false);

export const siteStore = {
  get sites(): Site[] {
    return sites;
  },
  get selectedSlug(): string | null {
    return selectedSlug;
  },
  get selectedSite(): Site | null {
    return sites.find((site) => site.slug === selectedSlug) ?? null;
  },
  get loading(): boolean {
    return loading;
  },
  get error(): string | null {
    return error;
  },
  get loaded(): boolean {
    return loaded;
  },

  /** Charge la liste des sites depuis le serveur. Idempotent sauf `force`. */
  async load(force = false): Promise<void> {
    if (loaded && !force) return;
    loading = true;
    error = null;
    try {
      const response = await getSites();
      sites = response.sites;
      if (selectedSlug === null || !sites.some((site) => site.slug === selectedSlug)) {
        selectedSlug = sites[0]?.slug ?? null;
        writeStoredSlug(selectedSlug);
      }
      loaded = true;
    } catch (err) {
      // Ne jamais avaler l'erreur : exposée via `siteStore.error` pour que les pages l'affichent.
      error =
        err instanceof ApiRequestError
          ? err.message
          : 'Erreur inconnue lors du chargement des sites.';
    } finally {
      loading = false;
    }
  },

  /** Sélectionne un site (doit être un slug présent dans `sites`). */
  select(slug: string): void {
    selectedSlug = slug;
    writeStoredSlug(slug);
  },

  /** Réservé aux tests : remet le store à son état initial. */
  _resetForTests(): void {
    sites = [];
    selectedSlug = null;
    loading = false;
    error = null;
    loaded = false;
    writeStoredSlug(null);
  },
};
