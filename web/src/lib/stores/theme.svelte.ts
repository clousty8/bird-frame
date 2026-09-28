// Thème clair/sombre : préférence système par défaut, bouton pour la forcer,
// persistance localStorage. Applique `data-theme` sur <html> (tokens définis dans
// styles/tailwind.css, copiés de BirdNET-Go — voir web/NOTICE.md).

const STORAGE_KEY = 'bird-frame:theme';

export type ThemePreference = 'system' | 'light' | 'dark';
export type EffectiveTheme = 'light' | 'dark';

function readStoredPreference(): ThemePreference {
  try {
    const raw = typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw;
  } catch {
    // Stockage indisponible : on retombe sur la préférence système, sans bloquer l'UI.
  }
  return 'system';
}

function writeStoredPreference(preference: ThemePreference): void {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    // Perte silencieuse acceptable : le thème reste correct pour la session en cours.
  }
}

function systemPrefersDarkNow(): boolean {
  try {
    return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return false;
  }
}

function computeEffective(preference: ThemePreference, systemDark: boolean): EffectiveTheme {
  return preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;
}

let preference = $state<ThemePreference>(readStoredPreference());
let systemPrefersDark = $state<boolean>(systemPrefersDarkNow());

if (typeof matchMedia !== 'undefined') {
  const media = matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener('change', (event) => {
    systemPrefersDark = event.matches;
  });
}

export const themeStore = {
  get preference(): ThemePreference {
    return preference;
  },
  get effective(): EffectiveTheme {
    return computeEffective(preference, systemPrefersDark);
  },

  set(next: ThemePreference): void {
    preference = next;
    writeStoredPreference(next);
  },

  /** Fait défiler système → clair → sombre → système (pour le bouton unique de la coquille). */
  cycle(): void {
    const order: ThemePreference[] = ['system', 'light', 'dark'];
    const currentIndex = order.indexOf(preference);
    const next = order[(currentIndex + 1) % order.length] ?? 'system';
    this.set(next);
  },
};

/** Applique le thème effectif sur <html data-theme>. À appeler dans un $effect (App.svelte)
 *  pour réagir aussi bien aux changements de préférence qu'aux changements système. */
export function applyThemeToDocument(theme: EffectiveTheme): void {
  try {
    if (typeof document !== 'undefined') document.documentElement.dataset.theme = theme;
  } catch {
    // Environnement sans document (SSR/tests) : rien à faire.
  }
}

// Applique une première fois dès l'import, pour limiter le flash de thème avant que
// App.svelte ne monte son $effect.
applyThemeToDocument(themeStore.effective);
