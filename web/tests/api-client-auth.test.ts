import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  getAuthStatus,
  login,
  logout,
  postReview,
  setAuthRequiredHandler,
} from '../src/lib/api/client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const AUTH_REQUIRED = { error: 'auth_required', message: 'Connexion requise.', details: null };

describe('client API — session (contrat §2.2)', () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('interroge /auth/me, /auth/login et /auth/logout avec le cookie de même origine', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, { authenticated: true, auth_enabled: true })));
    globalThis.fetch = fetchMock;

    await getAuthStatus();
    await login('secret');
    await logout();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/auth/me',
      expect.objectContaining({ method: 'GET', credentials: 'same-origin' })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/auth/login',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ password: 'secret' }) })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/v1/auth/logout', expect.objectContaining({ method: 'POST' }));
  });

  it('rejoue une fois la requête refusée en 401 auth_required quand la connexion réussit', async () => {
    const handler = vi.fn().mockResolvedValue(true);
    setAuthRequiredHandler(handler);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, AUTH_REQUIRED))
      .mockResolvedValueOnce(jsonResponse(201, { review: { review_id: 1 }, command_id: null }));
    globalThis.fetch = fetchMock;

    const result = await postReview('pornic', { detection_id: 1, kind: 'correct' });

    expect(result).toEqual({ review: { review_id: 1 }, command_id: null });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('ne boucle jamais : un second 401 après connexion remonte en erreur', async () => {
    const handler = vi.fn().mockResolvedValue(true);
    setAuthRequiredHandler(handler);
    globalThis.fetch = vi.fn(() => Promise.resolve(jsonResponse(401, AUTH_REQUIRED)));

    await expect(postReview('pornic', { detection_id: 1, kind: 'correct' })).rejects.toMatchObject({
      code: 'auth_required',
      status: 401,
    });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('remonte le 401 quand la connexion est abandonnée', async () => {
    setAuthRequiredHandler(vi.fn().mockResolvedValue(false));
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse(401, AUTH_REQUIRED));

    await expect(postReview('pornic', { detection_id: 1, kind: 'correct' })).rejects.toMatchObject({
      code: 'auth_required',
    });
  });

  it('un mauvais mot de passe (401 invalid_password) n’ouvre pas la modale', async () => {
    const handler = vi.fn().mockResolvedValue(true);
    setAuthRequiredHandler(handler);
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(jsonResponse(401, { error: 'invalid_password', message: 'Mot de passe incorrect.', details: null }));

    await expect(login('faux')).rejects.toMatchObject({ code: 'invalid_password', status: 401 });
    expect(handler).not.toHaveBeenCalled();
  });
});
