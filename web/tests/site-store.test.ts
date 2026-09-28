import { describe, it, expect, vi, beforeEach } from 'vitest';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { Site } from '../src/lib/api/types';

function makeSite(overrides: Partial<Site> = {}): Site {
  return {
    slug: 'pornic',
    name: 'Pornic',
    timezone: 'Europe/Paris',
    lat: 47.1155,
    lon: -2.1046,
    created_at: '2026-09-26T00:00:00Z',
    node_count: 1,
    online: true,
    last_detection_at: '2026-09-27T14:39:01Z',
    total_detections: 4627,
    ...overrides,
  };
}

describe('siteStore (mock fetch via api/client)', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    vi.restoreAllMocks();
  });

  it("charge la liste des sites et sélectionne le premier par défaut", async () => {
    const sites = [makeSite({ slug: 'pornic' }), makeSite({ slug: 'le-mans', name: 'Le Mans' })];
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites });

    await siteStore.load();

    expect(siteStore.sites).toEqual(sites);
    expect(siteStore.selectedSlug).toBe('pornic');
    expect(siteStore.selectedSite?.name).toBe('Pornic');
    expect(siteStore.loading).toBe(false);
    expect(siteStore.error).toBeNull();
    expect(siteStore.loaded).toBe(true);
  });

  it('ne recharge pas si déjà chargé, sauf avec force=true', async () => {
    const getSitesSpy = vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });

    await siteStore.load();
    await siteStore.load();
    expect(getSitesSpy).toHaveBeenCalledTimes(1);

    await siteStore.load(true);
    expect(getSitesSpy).toHaveBeenCalledTimes(2);
  });

  it('expose une erreur lisible en cas d\'échec, sans jamais planter silencieusement', async () => {
    vi.spyOn(client, 'getSites').mockRejectedValue(
      new client.ApiRequestError('network_error', 'Impossible de joindre le serveur.', 0)
    );

    await siteStore.load();

    expect(siteStore.error).toBe('Impossible de joindre le serveur.');
    expect(siteStore.sites).toEqual([]);
    expect(siteStore.loaded).toBe(false);
    expect(siteStore.loading).toBe(false);
  });

  it('select() change le site courant et le persiste (localStorage)', async () => {
    const sites = [makeSite({ slug: 'pornic' }), makeSite({ slug: 'le-mans', name: 'Le Mans' })];
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites });
    await siteStore.load();

    siteStore.select('le-mans');

    expect(siteStore.selectedSlug).toBe('le-mans');
    expect(localStorage.getItem('bird-frame:selected-site')).toBe('le-mans');
  });
});
