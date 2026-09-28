import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import SpeciesDetailPage from '../src/routes/SpeciesDetailPage.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { PresenceResponse, Site, SpeciesDetail, TopClip } from '../src/lib/api/types';

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

function makeDetail(overrides: Partial<SpeciesDetail> = {}): SpeciesDetail {
  return {
    scientific_name: 'Erithacus rubecula',
    aliases: [],
    common_name_fr: 'Rougegorge familier',
    in_france_universe: true,
    taxonomy: {
      kingdom: 'Animalia',
      phylum: 'Chordata',
      class: 'Aves',
      order: 'Passeriformes',
      family: 'Muscicapidae',
      family_common: 'Old World Flycatchers',
      genus: 'Erithacus',
      species: 'Erithacus rubecula',
    },
    photo: null,
    wikipedia: { fr: null, en: null },
    has_sheet: true,
    summary_fr: 'Un petit passereau au plastron orange vif.',
    habitat: 'Jardins et sous-bois.',
    diet: 'Insectivore, baies en hiver.',
    activity_pattern: 'diurne',
    migration: { statut: 'migrateur partiel', hiverne: 'Toute la France.', niche: 'Partout.', passage: 'Mars et octobre.' },
    seasonality_fr: "Présent toute l'année.",
    song_fr: 'Phrases fluides et mélancoliques.',
    lookalikes: [],
    rarity_note: 'Très commun.',
    fun_facts: [],
    france_universe: { max_score: 0.9939, cities: { Pornic: 0.85 }, months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] },
    sources: [],
    generated_at: '2026-09-27T16:10:00Z',
    generator_model: 'claude-haiku-4-5',
    reviewed_by_human: false,
    presence_by_site: [
      {
        site_slug: 'pornic',
        site_name: 'Pornic',
        total: 412,
        first_seen_utc: '2026-09-26T05:40:02Z',
        last_seen_utc: '2026-09-27T14:31:09Z',
        days_seen: 2,
        max_confidence: 0.99,
        months: [0, 0, 0, 0, 0, 0, 0, 0, 412, 0, 0, 0],
        rule: null,
        redirect_to_scientific_name: null,
      },
    ],
    ...overrides,
  };
}

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
      { scientific_name: 'Columba palumbus', common_name_fr: 'Pigeon ramier', confidence: 0.02, is_primary: false },
    ],
    ...overrides,
  };
}

describe('SpeciesDetailPage — fiche espèce', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    vi.spyOn(client, 'getTopClips').mockResolvedValue({ site_slug: 'pornic', scientific_name: 'Erithacus rubecula', clips: [] });
    vi.spyOn(client, 'getSpeciesPresence').mockResolvedValue(makePresence());
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('affiche un indicateur de chargement pendant la requête', () => {
    vi.spyOn(client, 'getSpeciesDetail').mockImplementation(() => new Promise(() => {}));

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('affiche la fiche complète avec nom, taxonomie et présence par site', async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(makeDetail());

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByRole('heading', { name: 'Rougegorge familier' })).toBeInTheDocument();
    expect(screen.getByText('Erithacus rubecula')).toBeInTheDocument();
    expect(screen.getByText('Passeriformes')).toBeInTheDocument();
    expect(screen.getByText('412 détections')).toBeInTheDocument();
  });

  it('affiche une erreur lisible si le serveur échoue, sans planter', async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockRejectedValue(new client.ApiRequestError('species_not_found', 'Espèce inconnue.', 404));

    render(SpeciesDetailPage, { scientificName: 'Oiseau inconnu' });

    expect(await screen.findByText('Espèce inconnue.')).toBeInTheDocument();
  });

  it('affiche le badge « généré par IA » quand la fiche a has_sheet et n\'a pas été relue', async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(makeDetail({ has_sheet: true, reviewed_by_human: false }));

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByText('Fiche générée par IA, à vérifier')).toBeInTheDocument();
  });

  it("ne montre pas le badge IA quand la fiche a été relue par un humain", async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(makeDetail({ reviewed_by_human: true }));

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    await screen.findByRole('heading', { name: 'Rougegorge familier' });
    expect(screen.queryByText('Fiche générée par IA, à vérifier')).not.toBeInTheDocument();
  });

  it("affiche « fiche en cours de rédaction » quand la fiche n'a pas de partie rédactionnelle", async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(
      makeDetail({
        has_sheet: false,
        summary_fr: null,
        habitat: null,
        diet: null,
        activity_pattern: null,
        migration: null,
        seasonality_fr: null,
        song_fr: null,
        rarity_note: null,
        sources: [],
      })
    );

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByText('Fiche en cours de rédaction.')).toBeInTheDocument();
  });

  it("affiche l'extrait Wikipédia en secours quand la fiche n'a pas de résumé rédigé", async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(
      makeDetail({
        has_sheet: false,
        summary_fr: null,
        wikipedia: {
          fr: { title: 'Rouge-gorge familier', url: 'https://fr.wikipedia.org/wiki/Rouge-gorge_familier', description: null, extract: "Extrait de secours issu de Wikipédia." },
          en: null,
        },
      })
    );

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByText('Extrait de secours issu de Wikipédia.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Wikipédia (FR)' })).toHaveAttribute(
      'href',
      'https://fr.wikipedia.org/wiki/Rouge-gorge_familier'
    );
  });

  it("affiche « aucun enregistrement » quand le site n'a pas de clip pour l'espèce", async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(makeDetail());

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByText('Aucun enregistrement')).toBeInTheDocument();
  });

  it('affiche un enregistrement avec ses labels multi-espèces (primaire + secondaires ≥ 5 %)', async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(makeDetail());
    vi.spyOn(client, 'getTopClips').mockResolvedValue({
      site_slug: 'pornic',
      scientific_name: 'Erithacus rubecula',
      clips: [makeClip()],
    });

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByText('Mésange charbonnière 72 %')).toBeInTheDocument();
    // Pigeon ramier est à 2 % (< 5 %) : ne doit pas apparaître (contrat §« afficher les
    // secondaires ≥ 5 % »).
    expect(screen.queryByText(/Pigeon ramier/)).not.toBeInTheDocument();
  });

  it('affiche la plausibilité ici (france_universe) avec le score maximal', async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(makeDetail());

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    expect(await screen.findByText('Plausibilité ici')).toBeInTheDocument();
    expect(screen.getByText('Score maximal (France)', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('Score à Pornic', { exact: false })).toBeInTheDocument();
  });

  it("affiche les statistiques heure/mois du site courant (GET .../presence?site=)", async () => {
    vi.spyOn(client, 'getSpeciesDetail').mockResolvedValue(makeDetail());
    const presenceSpy = vi.spyOn(client, 'getSpeciesPresence').mockResolvedValue(makePresence());

    render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });

    await screen.findByRole('heading', { name: 'Rougegorge familier' });
    await vi.waitFor(() => expect(presenceSpy).toHaveBeenCalledWith('Erithacus rubecula', { site: 'pornic' }));
  });

  it("ignore la réponse d'une espèce quittée arrivée après celle de l'espèce affichée (pas de course)", async () => {
    let resolveA!: (v: SpeciesDetail) => void;
    let resolveB!: (v: SpeciesDetail) => void;
    const detailAPromise = new Promise<SpeciesDetail>((r) => (resolveA = r));
    const detailBPromise = new Promise<SpeciesDetail>((r) => (resolveB = r));

    const getSpeciesDetailSpy = vi
      .spyOn(client, 'getSpeciesDetail')
      .mockImplementationOnce(() => detailAPromise)
      .mockImplementationOnce(() => detailBPromise);

    const { rerender } = render(SpeciesDetailPage, { scientificName: 'Erithacus rubecula' });
    expect(getSpeciesDetailSpy).toHaveBeenCalledWith('Erithacus rubecula');

    // L'utilisateur clique vers une autre espèce avant que la réponse de la première ne
    // revienne (ex. depuis les puces « Dernières détections » du tableau de bord).
    await rerender({ scientificName: 'Parus major' });
    expect(getSpeciesDetailSpy).toHaveBeenCalledWith('Parus major');

    // La réponse pour l'espèce affichée (Parus major, la plus récemment demandée) revient
    // en premier…
    resolveB(makeDetail({ scientific_name: 'Parus major', common_name_fr: 'Mésange charbonnière' }));
    expect(await screen.findByRole('heading', { name: 'Mésange charbonnière' })).toBeInTheDocument();

    // …puis celle de l'espèce quittée (Erithacus rubecula, périmée) répond après coup.
    resolveA(makeDetail({ scientific_name: 'Erithacus rubecula', common_name_fr: 'Rougegorge familier' }));
    await Promise.resolve();
    await Promise.resolve();

    // Avant le correctif, cette réponse périmée écrasait `detail` : l'URL affichait
    // /species/Parus%20major mais la page montrait la fiche du Rougegorge.
    expect(screen.queryByRole('heading', { name: 'Rougegorge familier' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Mésange charbonnière' })).toBeInTheDocument();
  });
});
