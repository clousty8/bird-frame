import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { authStore } from '../src/lib/stores/auth.svelte';
import * as client from '../src/lib/api/client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('authStore — état de session (contrat §2.2)', () => {
  beforeEach(() => {
    authStore._resetForTests({ authEnabled: true, authenticated: false });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('charge /auth/me et en déduit les droits', async () => {
    vi.spyOn(client, 'getAuthStatus').mockResolvedValue({ authenticated: true, auth_enabled: true });
    await authStore.load();
    expect(authStore.authenticated).toBe(true);
    expect(authStore.unlocked).toBe(true);
  });

  it('reste verrouillé sans session quand l’authentification est active', async () => {
    vi.spyOn(client, 'getAuthStatus').mockResolvedValue({ authenticated: false, auth_enabled: true });
    await authStore.load();
    expect(authStore.unlocked).toBe(false);
  });

  it('déverrouille tout quand l’authentification est désactivée (dev)', async () => {
    vi.spyOn(client, 'getAuthStatus').mockResolvedValue({ authenticated: false, auth_enabled: false });
    await authStore.load();
    expect(authStore.unlocked).toBe(true);
  });

  it('expose l’erreur de /auth/me et reste verrouillé (jamais avalée)', async () => {
    vi.spyOn(client, 'getAuthStatus').mockRejectedValue(
      new client.ApiRequestError('network_error', 'Serveur injoignable.', 0)
    );
    await authStore.load();
    expect(authStore.error).toBe('Serveur injoignable.');
    expect(authStore.unlocked).toBe(false);
    expect(authStore.loaded).toBe(true);
  });

  it('résout l’attente de la modale à true après connexion', async () => {
    vi.spyOn(client, 'login').mockResolvedValue({ authenticated: true, auth_enabled: true });
    const waiting = authStore.openLoginModal();
    expect(authStore.modalOpen).toBe(true);

    await authStore.login('mot de passe');

    await expect(waiting).resolves.toBe(true);
    expect(authStore.modalOpen).toBe(false);
    expect(authStore.authenticated).toBe(true);
    expect(client.login).toHaveBeenCalledWith('mot de passe');
  });

  it('résout l’attente à false quand la modale est fermée', async () => {
    const waiting = authStore.openLoginModal();
    authStore.cancelLogin();
    await expect(waiting).resolves.toBe(false);
    expect(authStore.modalOpen).toBe(false);
  });

  it('laisse la modale ouverte et relève l’erreur sur mauvais mot de passe', async () => {
    vi.spyOn(client, 'login').mockRejectedValue(
      new client.ApiRequestError('invalid_password', 'Mot de passe incorrect.', 401)
    );
    void authStore.openLoginModal();
    await expect(authStore.login('faux')).rejects.toMatchObject({ code: 'invalid_password' });
    expect(authStore.modalOpen).toBe(true);
    expect(authStore.authenticated).toBe(false);
  });

  it('se déconnecte, et expose une erreur de déconnexion', async () => {
    authStore._resetForTests({ authEnabled: true, authenticated: true });
    vi.spyOn(client, 'logout').mockResolvedValueOnce({ authenticated: false, auth_enabled: true });
    await authStore.logout();
    expect(authStore.authenticated).toBe(false);

    authStore._resetForTests({ authEnabled: true, authenticated: true });
    vi.spyOn(client, 'logout').mockRejectedValueOnce(new client.ApiRequestError('network_error', 'Hors ligne.', 0));
    await authStore.logout();
    expect(authStore.error).toBe('Hors ligne.');
  });

  it('n’ouvre pas de modale quand l’authentification est désactivée', async () => {
    authStore._resetForTests({ authEnabled: false });
    await expect(authStore.openLoginModal()).resolves.toBe(true);
    expect(authStore.modalOpen).toBe(false);
  });
});

describe('authStore — une action refusée en 401 ouvre la modale puis est rejouée', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    authStore._resetForTests({ authEnabled: true, authenticated: true });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('session expirée : 401 → modale → connexion → la modification aboutit', async () => {
    const rule = { rule: { scientific_name: 'Columba livia' } };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: 'auth_required', message: 'Connexion requise.', details: null }))
      .mockResolvedValueOnce(jsonResponse(200, { authenticated: true, auth_enabled: true }))
      .mockResolvedValueOnce(jsonResponse(200, rule));
    globalThis.fetch = fetchMock;

    const pending = client.putSpeciesRule('pornic', 'Columba livia', {
      rule: 'impossible',
      threshold_override: null,
      redirect_to_scientific_name: null,
      reason: null,
    });

    await vi.waitFor(() => expect(authStore.modalOpen).toBe(true));
    expect(authStore.authenticated).toBe(false);

    await authStore.login('mot de passe');

    await expect(pending).resolves.toEqual(rule);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/auth/login');
    expect(fetchMock.mock.calls[2]?.[0]).toBe('/api/v1/sites/pornic/species-rules/Columba%20livia');
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({ method: 'PUT' });
  });

  it('modale fermée : l’erreur 401 remonte à la page', async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(jsonResponse(401, { error: 'auth_required', message: 'Connexion requise.', details: null }));

    const pending = client.postFalseNegative('pornic', { scientific_name: 'Strix aluco' });
    await vi.waitFor(() => expect(authStore.modalOpen).toBe(true));
    authStore.cancelLogin();

    await expect(pending).rejects.toMatchObject({ code: 'auth_required', status: 401 });
  });
});
