// Store global de session (contrat §2.2) : lecture libre pour tout le monde, session requise
// pour modifier et pour écouter les enregistrements. Un seul mot de passe, pas de comptes.
//
// - `load()` (GET /auth/me) au démarrage de l'appli (App.svelte).
// - `unlocked` : vrai si l'authentification est désactivée (serveur de dev sans mot de passe)
//   ou si une session est ouverte. Tant que /auth/me n'a pas répondu, tout reste verrouillé
//   (le cas le plus courant sur l'instance publique).
// - `openLoginModal()` ouvre la modale (LoginModal.svelte, montée par App.svelte) et se
//   résout à `true` après connexion, `false` si elle est fermée. C'est aussi le gestionnaire
//   des 401 `auth_required` du client API : l'action refusée est rejouée après connexion.

import {
  ApiRequestError,
  getAuthStatus,
  login as apiLogin,
  logout as apiLogout,
  setAuthRequiredHandler,
} from '../api/client';

let authEnabled = $state(true);
let authenticated = $state(false);
let loaded = $state(false);
let error = $state<string | null>(null);
let modalOpen = $state(false);

// Toutes les attentes en cours sur la modale (plusieurs actions refusées en même temps
// partagent la même modale et sont toutes rejouées après une seule connexion).
let waiters: Array<(loggedIn: boolean) => void> = [];

function settleWaiters(loggedIn: boolean): void {
  const pending = waiters;
  waiters = [];
  for (const resolve of pending) resolve(loggedIn);
}

export const authStore = {
  get authEnabled(): boolean {
    return authEnabled;
  },
  get authenticated(): boolean {
    return authenticated;
  },
  /** Modifier et écouter les sons sont autorisés (un seul mot de passe pour les deux). */
  get unlocked(): boolean {
    return !authEnabled || authenticated;
  },
  get loaded(): boolean {
    return loaded;
  },
  /** Dernière erreur de /auth/me ou de déconnexion, à afficher (jamais avalée). */
  get error(): string | null {
    return error;
  },
  get modalOpen(): boolean {
    return modalOpen;
  },

  /** GET /auth/me. En cas d'échec, on reste verrouillé (le serveur fait foi de toute façon). */
  async load(): Promise<void> {
    try {
      const status = await getAuthStatus();
      authEnabled = status.auth_enabled;
      authenticated = status.authenticated;
      error = null;
    } catch (err) {
      error =
        err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors de la vérification de la session.';
    } finally {
      loaded = true;
    }
  },

  /** Ouvre la modale ; se résout à `true` après connexion, `false` si elle est fermée. */
  openLoginModal(): Promise<boolean> {
    if (!authEnabled) return Promise.resolve(true);
    modalOpen = true;
    return new Promise<boolean>((resolve) => {
      waiters.push(resolve);
    });
  },

  /** Ferme la modale sans se connecter. */
  cancelLogin(): void {
    modalOpen = false;
    settleWaiters(false);
  },

  /** POST /auth/login. Lève l'ApiRequestError (mot de passe incorrect, 429…) pour la modale. */
  async login(password: string): Promise<void> {
    const status = await apiLogin(password);
    authEnabled = status.auth_enabled;
    authenticated = status.authenticated;
    error = null;
    modalOpen = false;
    settleWaiters(true);
  },

  async logout(): Promise<void> {
    try {
      const status = await apiLogout();
      authEnabled = status.auth_enabled;
      authenticated = false;
      error = null;
    } catch (err) {
      error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors de la déconnexion.';
    }
  },

  /** Réservé aux tests : remet le store dans un état donné (défaut : état initial). */
  _resetForTests(state: { authEnabled?: boolean; authenticated?: boolean } = {}): void {
    authEnabled = state.authEnabled ?? true;
    authenticated = state.authenticated ?? false;
    loaded = true;
    error = null;
    modalOpen = false;
    waiters = [];
  },
};

// Toute action refusée faute de session (401 `auth_required`) : on repasse en déconnecté
// (session expirée, secret serveur changé) et on propose de se connecter.
setAuthRequiredHandler(() => {
  authEnabled = true;
  authenticated = false;
  return authStore.openLoginModal();
});
