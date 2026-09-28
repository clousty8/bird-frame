import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import StatsPage from '../src/routes/StatsPage.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type {
  ConfidenceResponse,
  DailyResponse,
  HeatmapResponse,
  HourlyResponse,
  KpisResponse,
  Site,
  SpeciesRankingResponse,
} from '../src/lib/api/types';

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

const SAMPLE_KPIS: KpisResponse = {
  site_slug: 'pornic',
  timezone: 'Europe/Paris',
  date: '2026-09-27',
  lifetime_species: 58,
  lifetime_detections: 4627,
  today_detections: 312,
  today_species: 27,
  best_day: { date: '2026-09-26', count: 1740 },
  streak_days: 2,
  // Année antérieure à `last_detection_utc` exprès : donne au moins deux options dans le
  // sélecteur d'année de la heatmap (heatmapMinYear vs. année courante), utilisé par le test
  // d'interaction plus bas.
  first_detection_utc: '2025-09-25T21:11:14Z',
  last_detection_utc: '2026-09-27T14:39:01Z',
};

// 30 jours (2026-08-29 -> 2026-09-27), tous vides sauf le dernier — sert aussi à vérifier
// l'état "vide" quand on le veut totalement à zéro.
function makeDaily(lastDayTotal: number): DailyResponse {
  const days: DailyResponse['days'] = [];
  const start = new Date(Date.UTC(2026, 7, 29));
  for (let i = 0; i < 30; i++) {
    const d = new Date(start);
    d.setUTCDate(start.getUTCDate() + i);
    const iso = d.toISOString().slice(0, 10);
    const isLast = i === 29;
    days.push({ date: iso, total: isLast ? lastDayTotal : 0, species_count: isLast ? Math.min(lastDayTotal, 5) : 0 });
  }
  return { site_slug: 'pornic', timezone: 'Europe/Paris', start: '2026-08-29', end: '2026-09-27', days };
}

const SAMPLE_HOURLY: HourlyResponse = {
  site_slug: 'pornic',
  timezone: 'Europe/Paris',
  start: '2026-08-29',
  end: '2026-09-27',
  hours: Array.from({ length: 24 }, (_, hour) => ({
    hour,
    total: hour === 7 ? 88 : 0,
    species:
      hour === 7 ? [{ scientific_name: 'Erithacus rubecula', common_name_fr: 'Rougegorge familier', count: 88 }] : [],
  })),
};

const SAMPLE_SPECIES_RANKING: SpeciesRankingResponse = {
  site_slug: 'pornic',
  timezone: 'Europe/Paris',
  start: '2026-08-29',
  end: '2026-09-27',
  total_species: 2,
  species: [
    {
      rank: 1,
      scientific_name: 'Erithacus rubecula',
      common_name_fr: 'Rougegorge familier',
      total: 412,
      days_seen: 2,
      max_confidence: 0.99,
      avg_confidence: 0.8123,
      first_utc: '2026-09-26T05:40:02Z',
      last_utc: '2026-09-27T14:31:09Z',
      photo_url: null,
    },
    {
      rank: 2,
      scientific_name: 'Turdus merula',
      common_name_fr: 'Merle noir',
      total: 88,
      days_seen: 1,
      max_confidence: 0.91,
      avg_confidence: 0.7,
      first_utc: '2026-09-27T06:00:00Z',
      last_utc: '2026-09-27T06:00:00Z',
      photo_url: null,
    },
  ],
};

function makeHeatmap(year: number): HeatmapResponse {
  return {
    site_slug: 'pornic',
    timezone: 'Europe/Paris',
    year,
    week_count: 53,
    species: [
      {
        scientific_name: 'Erithacus rubecula',
        common_name_fr: 'Rougegorge familier',
        total: 412,
        weeks: Array.from({ length: 53 }, (_, i) => (i === 38 ? 412 : 0)),
      },
    ],
  };
}

const SAMPLE_CONFIDENCE: ConfidenceResponse = {
  site_slug: 'pornic',
  timezone: 'Europe/Paris',
  start: '2026-08-29',
  end: '2026-09-27',
  species: null,
  total: 100,
  buckets: Array.from({ length: 10 }, (_, i) => ({ min: i / 10, max: (i + 1) / 10, count: i === 9 ? 100 : 0 })),
};

/** Installe des réponses par défaut (site + 6 routes stats) pour toutes les routes sauf
 * celles explicitement surchargées par le test. */
function mockAllStats(overrides: Partial<Record<'kpis' | 'daily' | 'hourly' | 'species' | 'heatmap' | 'confidence', unknown>> = {}) {
  vi.spyOn(client, 'getStatsKpis').mockImplementation(
    () => (overrides.kpis as () => Promise<KpisResponse>)?.() ?? Promise.resolve(SAMPLE_KPIS)
  );
  vi.spyOn(client, 'getStatsDaily').mockImplementation(
    () => (overrides.daily as () => Promise<DailyResponse>)?.() ?? Promise.resolve(makeDaily(312))
  );
  vi.spyOn(client, 'getStatsHourly').mockImplementation(
    () => (overrides.hourly as () => Promise<HourlyResponse>)?.() ?? Promise.resolve(SAMPLE_HOURLY)
  );
  vi.spyOn(client, 'getStatsSpeciesRanking').mockImplementation(
    () => (overrides.species as () => Promise<SpeciesRankingResponse>)?.() ?? Promise.resolve(SAMPLE_SPECIES_RANKING)
  );
  vi.spyOn(client, 'getStatsHeatmap').mockImplementation(
    (_slug: string, params?: { year?: number }) =>
      (overrides.heatmap as () => Promise<HeatmapResponse>)?.() ?? Promise.resolve(makeHeatmap(params?.year ?? 2026))
  );
  vi.spyOn(client, 'getStatsConfidence').mockImplementation(
    () => (overrides.confidence as () => Promise<ConfidenceResponse>)?.() ?? Promise.resolve(SAMPLE_CONFIDENCE)
  );
}

describe('StatsPage', () => {
  beforeEach(() => {
    siteStore._resetForTests();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("affiche un état vide quand aucun site n'est enregistré", async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [] });
    await siteStore.load();

    render(StatsPage);

    expect(screen.getByRole('heading', { name: 'Statistiques' })).toBeInTheDocument();
    expect(screen.getByText('Aucun site enregistré')).toBeInTheDocument();
  });

  it('affiche un indicateur de chargement pendant que les indicateurs clés arrivent', async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();

    let resolveKpis: (v: KpisResponse) => void = () => {};
    const pending = new Promise<KpisResponse>((resolve) => {
      resolveKpis = resolve;
    });
    mockAllStats({ kpis: () => pending });

    render(StatsPage);

    expect(screen.getByLabelText('Chargement des indicateurs…')).toBeInTheDocument();

    resolveKpis(SAMPLE_KPIS);
    expect(await screen.findByText('Espèces à vie')).toBeInTheDocument();
  });

  it('affiche les six sections avec des données réelles', async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();
    mockAllStats();

    render(StatsPage);

    expect(await screen.findByText('Espèces à vie')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Indicateurs clés' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Détections par jour' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Répartition horaire' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Classement des espèces' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Heatmap saisonnière' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Histogramme de confiance' })).toBeInTheDocument();

    // Classement : les deux espèces mockées apparaissent, sous forme de lien vers la fiche.
    expect(await screen.findByRole('link', { name: 'Rougegorge familier' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Merle noir' })).toBeInTheDocument();
  });

  it('affiche une erreur avec un bouton "Réessayer" quand une route échoue, sans bloquer les autres sections', async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();
    mockAllStats({
      daily: () => Promise.reject(new client.ApiRequestError('internal_error', 'Erreur serveur.', 500)),
    });

    render(StatsPage);

    expect(await screen.findByText('Erreur serveur.')).toBeInTheDocument();
    // Les indicateurs clés, eux, se sont chargés normalement (l'échec est isolé à la section).
    expect(await screen.findByText('Espèces à vie')).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: 'Réessayer' });
    const dailySpy = vi.spyOn(client, 'getStatsDaily').mockResolvedValue(makeDaily(312));
    await fireEvent.click(retryButton);

    await waitFor(() => expect(dailySpy).toHaveBeenCalled());
  });

  it('affiche un état vide pour une section sans détection sur la période', async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();
    mockAllStats({ daily: () => Promise.resolve(makeDaily(0)) });

    render(StatsPage);

    expect(await screen.findByText('Aucune détection sur cette période')).toBeInTheDocument();
  });

  it('recharge les graphiques "sur plage" avec la bonne fenêtre quand on change de période', async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();
    mockAllStats();

    render(StatsPage);
    await screen.findByText('Espèces à vie');

    const dailySpy = vi.spyOn(client, 'getStatsDaily').mockResolvedValue(makeDaily(312));

    await fireEvent.click(screen.getByRole('tab', { name: '90 jours' }));

    await waitFor(() =>
      expect(dailySpy).toHaveBeenCalledWith('pornic', expect.objectContaining({ start: '2026-06-30', end: '2026-09-27' }))
    );
  });

  it('recharge uniquement la heatmap quand on change d\'année', async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();
    mockAllStats();

    render(StatsPage);
    await screen.findByText('Espèces à vie');

    const dailySpy = vi.spyOn(client, 'getStatsDaily');
    const heatmapSpy = vi.spyOn(client, 'getStatsHeatmap').mockResolvedValue(makeHeatmap(2025));
    dailySpy.mockClear();

    const yearSelect = screen.getByLabelText('Année') as HTMLSelectElement;
    await fireEvent.change(yearSelect, { target: { value: '2025' } });

    await waitFor(() => expect(heatmapSpy).toHaveBeenCalledWith('pornic', expect.objectContaining({ year: 2025 })));
    // Le changement d'année ne doit pas redéclencher les graphiques "sur plage".
    expect(dailySpy).not.toHaveBeenCalled();
  });

  it('affiche la date de première détection dans le fuseau local du site, pas le jour calendaire UTC (contrat §1.3-§1.4)', async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();
    mockAllStats({
      kpis: () =>
        Promise.resolve({
          ...SAMPLE_KPIS,
          // 22h30 UTC fin septembre = 00h30 le LENDEMAIN à Pornic (Europe/Paris, UTC+2 l'été) :
          // tronquer l'UtcInstant donnerait à tort le 25.
          first_detection_utc: '2026-09-25T22:30:00Z',
        }),
    });

    render(StatsPage);

    expect(await screen.findByText(/Depuis la première détection le/)).toHaveTextContent('26 sept. 2026');
  });

  it("initialise l'année de la heatmap sur l'année locale du site, pas l'année calendaire UTC (contrat §1.3-§1.4)", async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    await siteStore.load();
    mockAllStats({
      kpis: () =>
        Promise.resolve({
          ...SAMPLE_KPIS,
          // 23h15 UTC le 31 décembre = 00h15 le 1er JANVIER SUIVANT à Pornic (Europe/Paris,
          // UTC+1 l'hiver) : tronquer l'UtcInstant donnerait à tort 2026.
          last_detection_utc: '2026-12-31T23:15:00Z',
          first_detection_utc: '2026-01-01T10:00:00Z',
        }),
    });
    const heatmapSpy = vi
      .spyOn(client, 'getStatsHeatmap')
      .mockImplementation((_slug: string, params?: { year?: number }) => Promise.resolve(makeHeatmap(params?.year ?? 2026)));

    render(StatsPage);
    await screen.findByText('Espèces à vie');

    await waitFor(() => expect(heatmapSpy).toHaveBeenCalledWith('pornic', expect.objectContaining({ year: 2027 })));
  });
});
