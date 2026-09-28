import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';
import StatsSection from '../src/lib/components/species/StatsSection.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { PresenceResponse } from '../src/lib/api/types';

function makePresence(overrides: Partial<PresenceResponse> = {}): PresenceResponse {
  return {
    scientific_name: 'Erithacus rubecula',
    site_slug: 'pornic',
    total: 412,
    first_seen_utc: '2026-09-26T05:40:02Z',
    last_seen_utc: '2026-09-27T14:31:09Z',
    months: [0, 0, 0, 0, 0, 0, 0, 0, 412, 0, 0, 0],
    hours: new Array(24).fill(0) as number[],
    by_day: null,
    ...overrides,
  };
}

describe('StatsSection — statistiques heure/mois de la fiche espèce', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    siteStore.select('pornic');
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('affiche la présence pour le site sélectionné', async () => {
    vi.spyOn(client, 'getSpeciesPresence').mockResolvedValue(makePresence());

    render(StatsSection, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByTitle('septembre : 412')).toBeInTheDocument();
  });

  it("ignore la réponse de l'ancien site arrivée après un changement de site (pas de course)", async () => {
    let resolvePornic!: (v: PresenceResponse) => void;
    let resolveLeMans!: (v: PresenceResponse) => void;
    const pornicPromise = new Promise<PresenceResponse>((r) => (resolvePornic = r));
    const leMansPromise = new Promise<PresenceResponse>((r) => (resolveLeMans = r));

    const getSpeciesPresenceSpy = vi
      .spyOn(client, 'getSpeciesPresence')
      .mockImplementationOnce(() => pornicPromise)
      .mockImplementationOnce(() => leMansPromise);

    render(StatsSection, { scientificName: 'Erithacus rubecula' });
    expect(getSpeciesPresenceSpy).toHaveBeenCalledWith('Erithacus rubecula', { site: 'pornic' });

    // L'utilisateur change de site (SiteSelector global) avant que la requête pour Pornic
    // n'ait répondu.
    siteStore.select('le-mans');
    await waitFor(() => expect(getSpeciesPresenceSpy).toHaveBeenCalledWith('Erithacus rubecula', { site: 'le-mans' }));

    // Le Mans (site actuel, réponse rapide) répond en premier…
    resolveLeMans(makePresence({ site_slug: 'le-mans', months: [10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] }));
    expect(await screen.findByTitle('janvier : 10')).toBeInTheDocument();

    // …puis Pornic (site quitté, réponse lente) répond après coup.
    resolvePornic(makePresence({ site_slug: 'pornic' })); // months par défaut : septembre = 412
    await Promise.resolve();
    await Promise.resolve();

    // Avant le correctif, cette réponse tardive écrasait `presence` : la section aurait
    // affiché la répartition de Pornic alors que le reste de la page (Présence par site,
    // calendrier) reflète déjà Le Mans.
    expect(screen.queryByTitle('septembre : 412')).not.toBeInTheDocument();
    expect(screen.getByTitle('janvier : 10')).toBeInTheDocument();
  });
});
