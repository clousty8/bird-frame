import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import RecordingList from '../src/lib/components/species/RecordingList.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { TopClip, TopClipsResponse } from '../src/lib/api/types';

function makeClip(overrides: Partial<TopClip> = {}): TopClip {
  return {
    kept_clip_id: 88,
    detection_id: 1523,
    detected_at_utc: '2026-09-27T14:39:01Z',
    confidence: 0.72,
    rank: 1,
    audio_available: true,
    audio_url: '/api/v1/recordings/88/audio',
    spectrogram_url: '/api/v1/recordings/88/spectrogram',
    duration_s: 15,
    review: null,
    missing: false,
    predictions: [
      { scientific_name: 'Parus major', common_name_fr: 'Mésange charbonnière', confidence: 0.72, is_primary: true },
    ],
    ...overrides,
  };
}

describe('RecordingList — meilleurs enregistrements', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    siteStore.select('pornic');
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('affiche les enregistrements renvoyés pour le site sélectionné', async () => {
    vi.spyOn(client, 'getTopClips').mockResolvedValue({
      site_slug: 'pornic',
      scientific_name: 'Erithacus rubecula',
      clips: [makeClip()],
    });

    render(RecordingList, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByText('Confiance : 72 %')).toBeInTheDocument();
  });

  it("ignore la réponse d'une espèce quittée arrivée après celle de l'espèce affichée (pas de course)", async () => {
    let resolveA!: (v: TopClipsResponse) => void;
    let resolveB!: (v: TopClipsResponse) => void;
    const clipsAPromise = new Promise<TopClipsResponse>((r) => (resolveA = r));
    const clipsBPromise = new Promise<TopClipsResponse>((r) => (resolveB = r));

    const getTopClipsSpy = vi
      .spyOn(client, 'getTopClips')
      .mockImplementationOnce(() => clipsAPromise)
      .mockImplementationOnce(() => clipsBPromise);

    // Simule une navigation rapide d'une fiche espèce à l'autre (ex. via une future
    // navigation « espèces ressemblantes ») : le prop `scientificName` change avant que la
    // première requête n'ait répondu.
    const { rerender } = render(RecordingList, { scientificName: 'Erithacus rubecula' });
    expect(getTopClipsSpy).toHaveBeenCalledWith('Erithacus rubecula', 'pornic');

    await rerender({ scientificName: 'Parus major' });
    expect(getTopClipsSpy).toHaveBeenCalledWith('Parus major', 'pornic');

    // L'espèce affichée (Parus major, la plus récemment demandée) répond en premier…
    resolveB({
      site_slug: 'pornic',
      scientific_name: 'Parus major',
      clips: [makeClip({ confidence: 0.9 })],
    });
    expect(await screen.findByText('Confiance : 90 %')).toBeInTheDocument();

    // …puis l'espèce quittée (Erithacus rubecula, périmée) répond après coup.
    resolveA({
      site_slug: 'pornic',
      scientific_name: 'Erithacus rubecula',
      clips: [makeClip({ confidence: 0.5 })],
    });
    await Promise.resolve();
    await Promise.resolve();

    // Avant le correctif, cette réponse périmée écrasait `clips` : la section « Meilleurs
    // enregistrements » affichait l'audio/spectrogramme de l'ancienne espèce sous le titre
    // de la nouvelle.
    expect(screen.queryByText('Confiance : 50 %')).not.toBeInTheDocument();
    expect(screen.getByText('Confiance : 90 %')).toBeInTheDocument();
  });
});
