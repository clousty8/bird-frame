import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiRequestError, getSites, getSpeciesDetail, postFalseNegative, subscribeToPending } from '../src/lib/api/client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('client API — gestion des erreurs (contrat §1.8)', () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('renvoie les données sur un 200 valide', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse(200, { sites: [] }));

    const result = await getSites();

    expect(result).toEqual({ sites: [] });
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/sites', expect.objectContaining({ method: 'GET' }));
  });

  it('transforme le corps d\'erreur JSON du contrat en ApiRequestError', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      jsonResponse(404, { error: 'species_not_found', message: 'Espèce inconnue.', details: null })
    );

    await expect(getSpeciesDetail('Oiseau inconnu')).rejects.toMatchObject({
      code: 'species_not_found',
      message: 'Espèce inconnue.',
      status: 404,
    });
  });

  it('ne masque jamais une erreur réseau (serveur injoignable)', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    const promise = getSites();
    await expect(promise).rejects.toBeInstanceOf(ApiRequestError);
    await expect(promise).rejects.toMatchObject({ code: 'network_error', status: 0 });
  });

  it('signale une réponse non-JSON plutôt que de planter silencieusement', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response('<html>500</html>', { status: 500, headers: { 'Content-Type': 'text/html' } })
    );

    await expect(getSites()).rejects.toMatchObject({ code: 'invalid_response', status: 500 });
  });

  it('envoie le corps JSON pour une requête POST', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      jsonResponse(201, {
        false_negative: {
          id: 1,
          scientific_name: 'Strix aluco',
          common_name_fr: 'Chouette hulotte',
          known_species: true,
          approx_time_utc: null,
          notes: null,
          reported_at: '2026-09-27T15:12:00Z',
          reported_by: null,
        },
      })
    );

    await postFalseNegative('pornic', { scientific_name: 'Strix aluco' });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/sites/pornic/false-negatives',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ scientific_name: 'Strix aluco' }),
      })
    );
  });
});

describe('subscribeToPending — helper SSE (contrat §6.4)', () => {
  class FakeEventSource {
    static instances: FakeEventSource[] = [];
    url: string;
    listeners = new Map<string, ((event: MessageEvent) => void)[]>();
    closed = false;

    constructor(url: string) {
      this.url = url;
      FakeEventSource.instances.push(this);
    }

    addEventListener(type: string, listener: (event: MessageEvent) => void): void {
      const list = this.listeners.get(type) ?? [];
      list.push(listener);
      this.listeners.set(type, list);
    }

    close(): void {
      this.closed = true;
    }

    emit(type: string, data: unknown): void {
      for (const listener of this.listeners.get(type) ?? []) {
        listener({ data: JSON.stringify(data) } as MessageEvent);
      }
    }
  }

  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ne remonte pas l'erreur émise par le navigateur quand on quitte la page", () => {
    vi.useFakeTimers();
    try {
      const onError = vi.fn();
      const unsubscribe = subscribeToPending('pornic', { onError });
      const source = FakeEventSource.instances[0];

      // Vraie coupure réseau : remontée.
      source?.emit('error', {});
      expect(onError).toHaveBeenCalledTimes(1);

      // Rechargement / fermeture : beforeunload puis error (ordre constaté dans Chrome).
      window.dispatchEvent(new Event('beforeunload'));
      source?.emit('error', {});
      expect(onError).toHaveBeenCalledTimes(1);

      // Navigation finalement abandonnée : les erreurs suivantes sont de nouveau remontées.
      vi.advanceTimersByTime(1000);
      source?.emit('error', {});
      expect(onError).toHaveBeenCalledTimes(2);

      unsubscribe();
    } finally {
      vi.useRealTimers();
    }
  });

  it('se connecte à la bonne URL et relaie les événements "pending"', () => {
    const onPending = vi.fn();
    const unsubscribe = subscribeToPending('pornic', { onPending });

    const source = FakeEventSource.instances[0];
    expect(source?.url).toBe('/api/v1/sites/pornic/pending/stream');

    source?.emit('pending', { site_slug: 'pornic', updated_at_utc: '2026-09-27T14:39:05Z', pending: [] });
    expect(onPending).toHaveBeenCalledWith({ site_slug: 'pornic', updated_at_utc: '2026-09-27T14:39:05Z', pending: [] });

    unsubscribe();
    expect(source?.closed).toBe(true);
  });
});
