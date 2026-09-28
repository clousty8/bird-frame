import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import DashboardPage from '../src/routes/DashboardPage.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { CalendarResponse, KpisResponse, NowResponse, Site } from '../src/lib/api/types';

// jsdom n'implémente pas EventSource (cf. src/test/setup.ts) : stub minimal, le composant
// « en écoute » s'y abonne dès son montage.
class FakeEventSource {
  addEventListener(): void {}
  close(): void {}
}

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

const EMPTY_NOW: NowResponse = {
  site_slug: 'pornic',
  server_time_utc: '2026-09-27T14:39:05Z',
  pending: [],
  node_status: null,
  recent: [],
};

const EMPTY_CALENDAR: CalendarResponse = {
  site_slug: 'pornic',
  date: '2026-09-27',
  timezone: 'Europe/Paris',
  sunrise_utc: null,
  sunset_utc: null,
  total_detections: 0,
  species: [],
};

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
  first_detection_utc: '2026-09-25T21:11:14Z',
  last_detection_utc: '2026-09-27T14:39:01Z',
};

describe('DashboardPage', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    vi.stubGlobal('EventSource', FakeEventSource);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("affiche un état vide quand aucun site n'est enregistré", async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [] });
    await siteStore.load();

    render(DashboardPage);

    expect(screen.getByRole('heading', { name: 'Tableau de bord' })).toBeInTheDocument();
    expect(screen.getByText('Aucun site enregistré')).toBeInTheDocument();
  });

  it("assemble les trois blocs dans l'ordre imposé pour le site sélectionné", async () => {
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [makeSite()] });
    vi.spyOn(client, 'getSiteNow').mockResolvedValue(EMPTY_NOW);
    vi.spyOn(client, 'getCalendar').mockResolvedValue(EMPTY_CALENDAR);
    vi.spyOn(client, 'getStatsKpis').mockResolvedValue(SAMPLE_KPIS);
    await siteStore.load();

    render(DashboardPage);

    // 1) « En écoute » avant tout, avec son accordéon spectrogramme replié.
    expect(await screen.findByText("Rien en cours d'écoute pour l'instant.")).toBeInTheDocument();
    // 2) ligne de KPIs.
    expect(await screen.findByText('Espèces (total)')).toBeInTheDocument();
    // 3) calendrier d'activité quotidienne.
    expect(await screen.findByText('Aucune détection ce jour-là')).toBeInTheDocument();

    // Pas de grand bloc « détections récentes » séparé (supprimé, cf. docs/architecture.md §8.3).
    expect(screen.queryByRole('heading', { name: /détections récentes/i })).not.toBeInTheDocument();

    const headings = screen.getAllByRole('heading').map((h) => h.textContent);
    expect(headings.indexOf('En écoute')).toBeLessThan(headings.indexOf('Activité quotidienne'));
  });
});
