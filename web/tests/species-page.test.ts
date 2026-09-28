import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import SpeciesPage from '../src/routes/SpeciesPage.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { Site, SiteSpecies, UniverseSpecies } from '../src/lib/api/types';

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

function makeSiteSpecies(overrides: Partial<SiteSpecies> = {}): SiteSpecies {
  return {
    scientific_name: 'Erithacus rubecula',
    common_name_fr: 'Rougegorge familier',
    total: 412,
    first_seen_utc: '2026-09-26T05:40:02Z',
    last_seen_utc: '2026-09-27T14:31:09Z',
    max_confidence: 0.99,
    days_seen: 2,
    photo_url: null,
    has_sheet: true,
    in_france_universe: true,
    rule: null,
    redirect_to_scientific_name: null,
    ...overrides,
  };
}

function makeUniverseSpecies(overrides: Partial<UniverseSpecies> = {}): UniverseSpecies {
  return {
    scientific_name: 'Larus argentatus',
    common_name_fr: 'Goéland argenté',
    order: 'Charadriiformes',
    family: 'Laridae',
    in_france_universe: true,
    france_max_score: 0.9,
    detected_sites: [],
    total_detections: 0,
    site_total: 0,
    photo_url: null,
    has_sheet: false,
    ...overrides,
  };
}

describe('SpeciesPage — liste des espèces', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("affiche un état vide tant qu'aucun site n'est sélectionné", () => {
    vi.spyOn(client, 'getSites').mockImplementation(() => new Promise(() => {}));

    render(SpeciesPage);

    expect(screen.getByText('Aucun site sélectionné')).toBeInTheDocument();
  });

  it('charge et affiche les espèces détectées sur le site courant (contrat §6.7)', async () => {
    const getSiteSpeciesSpy = vi
      .spyOn(client, 'getSiteSpecies')
      .mockResolvedValue({ site_slug: 'pornic', species: [makeSiteSpecies()] });

    render(SpeciesPage);

    expect(await screen.findByText('Rougegorge familier')).toBeInTheDocument();
    expect(screen.getByText('Erithacus rubecula')).toBeInTheDocument();
    expect(getSiteSpeciesSpy).toHaveBeenCalledWith('pornic', { sort: 'total' });
  });

  it('affiche une erreur lisible sans planter si le serveur échoue', async () => {
    vi.spyOn(client, 'getSiteSpecies').mockRejectedValue(
      new client.ApiRequestError('site_not_found', 'Aucun site avec ce slug.', 404)
    );

    render(SpeciesPage);

    expect(await screen.findByText('Aucun site avec ce slug.')).toBeInTheDocument();
  });

  it("affiche un état vide quand le site n'a aucune espèce", async () => {
    vi.spyOn(client, 'getSiteSpecies').mockResolvedValue({ site_slug: 'pornic', species: [] });

    render(SpeciesPage);

    expect(await screen.findByText('Aucune espèce trouvée')).toBeInTheDocument();
  });

  it('affiche le badge de règle (impossible ici)', async () => {
    vi.spyOn(client, 'getSiteSpecies').mockResolvedValue({
      site_slug: 'pornic',
      species: [makeSiteSpecies({ rule: 'impossible' })],
    });

    render(SpeciesPage);

    expect(await screen.findByText('Impossible ici')).toBeInTheDocument();
  });

  it('filtre localement par texte de recherche (accents/casse ignorés, contrat muet sur ce point pour §6.7)', async () => {
    vi.spyOn(client, 'getSiteSpecies').mockResolvedValue({
      site_slug: 'pornic',
      species: [makeSiteSpecies(), makeSiteSpecies({ scientific_name: 'Turdus merula', common_name_fr: 'Merle noir' })],
    });

    render(SpeciesPage);
    await screen.findByText('Rougegorge familier');
    expect(screen.getByText('Merle noir')).toBeInTheDocument();

    const search = screen.getByLabelText('Rechercher une espèce');
    await fireEvent.input(search, { target: { value: 'MÉRLE' } });

    expect(screen.getByText('Merle noir')).toBeInTheDocument();
    expect(screen.queryByText('Rougegorge familier')).not.toBeInTheDocument();
  });

  it('change de tri (site courant) et relance la requête serveur', async () => {
    const getSiteSpeciesSpy = vi
      .spyOn(client, 'getSiteSpecies')
      .mockResolvedValue({ site_slug: 'pornic', species: [makeSiteSpecies()] });

    render(SpeciesPage);
    await screen.findByText('Rougegorge familier');

    const sortSelect = screen.getByLabelText('Trier par');
    await fireEvent.change(sortSelect, { target: { value: 'last_seen' } });

    await waitFor(() => expect(getSiteSpeciesSpy).toHaveBeenLastCalledWith('pornic', { sort: 'last_seen' }));
  });

  it('bascule vers « Toutes les espèces de France » et interroge /species avec site=', async () => {
    vi.spyOn(client, 'getSiteSpecies').mockResolvedValue({ site_slug: 'pornic', species: [makeSiteSpecies()] });
    const getSpeciesListSpy = vi.spyOn(client, 'getSpeciesList').mockResolvedValue({
      species: [makeUniverseSpecies()],
      total: 1,
      limit: 500,
      offset: 0,
    });

    render(SpeciesPage);
    await screen.findByText('Rougegorge familier');

    const toggle = screen.getByLabelText('Toutes les espèces de France (368)');
    await fireEvent.click(toggle);

    expect(await screen.findByText('Goéland argenté')).toBeInTheDocument();
    expect(screen.getByText('Jamais détectée')).toBeInTheDocument();
    await waitFor(() => expect(getSpeciesListSpy).toHaveBeenCalledWith(expect.objectContaining({ site: 'pornic' })));
  });

  it('indique « déjà détectée ici » quand site_total > 0 en mode univers France', async () => {
    vi.spyOn(client, 'getSiteSpecies').mockResolvedValue({ site_slug: 'pornic', species: [] });
    vi.spyOn(client, 'getSpeciesList').mockResolvedValue({
      species: [makeUniverseSpecies({ site_total: 3, total_detections: 3 })],
      total: 1,
      limit: 500,
      offset: 0,
    });

    render(SpeciesPage);
    await screen.findByText('Aucune espèce trouvée');

    await fireEvent.click(screen.getByLabelText('Toutes les espèces de France (368)'));

    expect(await screen.findByText('Déjà détectée ici')).toBeInTheDocument();
  });

  it("ignore la réponse tardive d'un site quitté après un changement rapide de site (pas de course)", async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({
      sites: [makeSite(), makeSite({ slug: 'le-mans', name: 'Le Mans' })],
    });

    let resolvePornic!: (v: { site_slug: string; species: SiteSpecies[] }) => void;
    let resolveLeMans!: (v: { site_slug: string; species: SiteSpecies[] }) => void;
    const pornicPromise = new Promise<{ site_slug: string; species: SiteSpecies[] }>((r) => (resolvePornic = r));
    const leMansPromise = new Promise<{ site_slug: string; species: SiteSpecies[] }>((r) => (resolveLeMans = r));

    const getSiteSpeciesSpy = vi
      .spyOn(client, 'getSiteSpecies')
      .mockImplementation((slug) => (slug === 'pornic' ? pornicPromise : leMansPromise));

    render(SpeciesPage);
    await waitFor(() => expect(getSiteSpeciesSpy).toHaveBeenCalledWith('pornic', { sort: 'total' }));

    siteStore.select('le-mans');
    await waitFor(() => expect(getSiteSpeciesSpy).toHaveBeenCalledWith('le-mans', { sort: 'total' }));

    // Le Mans (site actuel, réponse rapide) répond en premier…
    resolveLeMans({
      site_slug: 'le-mans',
      species: [makeSiteSpecies({ scientific_name: 'Turdus merula', common_name_fr: 'Merle noir' })],
    });
    expect(await screen.findByText('Merle noir')).toBeInTheDocument();

    // …puis Pornic (site quitté, réponse lente) répond après coup.
    resolvePornic({ site_slug: 'pornic', species: [makeSiteSpecies()] });
    await Promise.resolve();
    await Promise.resolve();

    // Avant le correctif, cette réponse tardive écrasait silencieusement la liste affichée
    // par celle de Pornic, alors que le site sélectionné est toujours « Le Mans ».
    expect(screen.queryByText('Rougegorge familier')).not.toBeInTheDocument();
    expect(screen.getByText('Merle noir')).toBeInTheDocument();
  });

  it("ignore la réponse tardive d'une recherche « Toutes les espèces de France » périmée", async () => {
    vi.spyOn(client, 'getSiteSpecies').mockResolvedValue({ site_slug: 'pornic', species: [] });

    let resolveFirst!: (v: { species: UniverseSpecies[]; total: number; limit: number; offset: number }) => void;
    let resolveSecond!: (v: { species: UniverseSpecies[]; total: number; limit: number; offset: number }) => void;
    const firstPromise = new Promise<{ species: UniverseSpecies[]; total: number; limit: number; offset: number }>(
      (r) => (resolveFirst = r)
    );
    const secondPromise = new Promise<{ species: UniverseSpecies[]; total: number; limit: number; offset: number }>(
      (r) => (resolveSecond = r)
    );

    const getSpeciesListSpy = vi
      .spyOn(client, 'getSpeciesList')
      .mockImplementationOnce(() => firstPromise)
      .mockImplementationOnce(() => secondPromise);

    render(SpeciesPage);
    await screen.findByText('Aucune espèce trouvée');

    await fireEvent.click(screen.getByLabelText('Toutes les espèces de France (368)'));
    await waitFor(() => expect(getSpeciesListSpy).toHaveBeenCalledTimes(1));

    const sortSelect = screen.getByLabelText('Trier par');
    await fireEvent.change(sortSelect, { target: { value: 'detections' } });
    await waitFor(() => expect(getSpeciesListSpy).toHaveBeenCalledTimes(2));

    // La seconde requête (la plus récente) répond en premier…
    resolveSecond({
      species: [makeUniverseSpecies({ scientific_name: 'Turdus merula', common_name_fr: 'Merle noir' })],
      total: 1,
      limit: 500,
      offset: 0,
    });
    expect(await screen.findByText('Merle noir')).toBeInTheDocument();

    // …puis la première (périmée) répond après coup.
    resolveFirst({ species: [makeUniverseSpecies()], total: 1, limit: 500, offset: 0 });
    await Promise.resolve();
    await Promise.resolve();

    expect(screen.queryByText('Rougegorge familier')).not.toBeInTheDocument();
    expect(screen.getByText('Merle noir')).toBeInTheDocument();
  });
});
