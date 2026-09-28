import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import DailyActivityCalendar from '../src/lib/components/dashboard/DailyActivityCalendar.svelte';
import * as client from '../src/lib/api/client';
import { ApiRequestError } from '../src/lib/api/client';
import type { CalendarResponse, CalendarSpecies } from '../src/lib/api/types';

function makeSpecies(overrides: Partial<CalendarSpecies> = {}): CalendarSpecies {
  return {
    scientific_name: 'Erithacus rubecula',
    common_name_fr: 'Rougegorge familier',
    total: 58,
    max_confidence: 0.98,
    first_utc: '2026-09-27T05:12:44Z',
    last_utc: '2026-09-27T14:31:09Z',
    hours: [0, 0, 0, 0, 0, 0, 0, 4, 9, 6, 5, 3, 2, 4, 6, 5, 8, 6, 0, 0, 0, 0, 0, 0],
    photo_url: '/api/v1/species/Erithacus%20rubecula/photo?size=320',
    ...overrides,
  };
}

function makeCalendar(overrides: Partial<CalendarResponse> = {}): CalendarResponse {
  return {
    site_slug: 'pornic',
    date: '2026-09-27',
    timezone: 'Europe/Paris',
    sunrise_utc: '2026-09-27T05:51:00Z',
    sunset_utc: '2026-09-27T17:43:00Z',
    total_detections: 312,
    species: [makeSpecies()],
    ...overrides,
  };
}

describe('DailyActivityCalendar', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('affiche un état de chargement puis la grille espèce × heure, toutes espèces sans limite', async () => {
    const many = Array.from({ length: 35 }, (_, i) => makeSpecies({ scientific_name: `Species ${i}`, common_name_fr: `Espèce ${i}` }));
    vi.spyOn(client, 'getCalendar').mockResolvedValue(makeCalendar({ species: many }));

    render(DailyActivityCalendar, { slug: 'pornic' });

    expect(screen.getByText("Chargement du calendrier d'activité…")).toBeInTheDocument();

    expect(await screen.findByText('Espèce 0')).toBeInTheDocument();
    // Aucune troncature à 30 espèces (contrat §6.5, cf. la limite native BirdNET-Go écartée).
    expect(screen.getByText('Espèce 34')).toBeInTheDocument();
  });

  it('affiche un état vide quand aucune détection ce jour-là', async () => {
    vi.spyOn(client, 'getCalendar').mockResolvedValue(makeCalendar({ species: [], total_detections: 0 }));

    render(DailyActivityCalendar, { slug: 'pornic' });

    expect(await screen.findByText('Aucune détection ce jour-là')).toBeInTheDocument();
  });

  it('affiche une erreur lisible sans planter si le calendrier échoue', async () => {
    vi.spyOn(client, 'getCalendar').mockRejectedValue(
      new ApiRequestError('site_not_found', 'Aucun site avec le slug « pornic ».', 404)
    );

    render(DailyActivityCalendar, { slug: 'pornic' });

    expect(await screen.findByText('Aucun site avec le slug « pornic ».')).toBeInTheDocument();
  });

  it('affiche le lever/coucher du soleil et un lien vers la fiche espèce', async () => {
    vi.spyOn(client, 'getCalendar').mockResolvedValue(makeCalendar());

    render(DailyActivityCalendar, { slug: 'pornic' });

    await screen.findByText('Rougegorge familier');
    expect(screen.getByText(/Lever 0?7:51/)).toBeInTheDocument();
    expect(screen.getByText(/Coucher 1?9:43/)).toBeInTheDocument();

    const link = screen.getByRole('link', { name: /Rougegorge familier/ });
    expect(link).toHaveAttribute('href', '/species/Erithacus%20rubecula');
  });

  it('navigue au jour précédent et au jour suivant', async () => {
    const getCalendarSpy = vi.spyOn(client, 'getCalendar').mockResolvedValue(makeCalendar());

    render(DailyActivityCalendar, { slug: 'pornic' });
    await screen.findByText('Rougegorge familier');

    getCalendarSpy.mockResolvedValueOnce(makeCalendar({ date: '2026-09-26' }));
    await fireEvent.click(screen.getByRole('button', { name: '← Veille' }));
    expect(getCalendarSpy).toHaveBeenLastCalledWith('pornic', { date: '2026-09-26' });

    getCalendarSpy.mockResolvedValueOnce(makeCalendar({ date: '2026-09-27' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Lendemain →' }));
    expect(getCalendarSpy).toHaveBeenLastCalledWith('pornic', { date: '2026-09-27' });
  });

  it('recharge le jour choisi dans le sélecteur de date', async () => {
    const getCalendarSpy = vi.spyOn(client, 'getCalendar').mockResolvedValue(makeCalendar());

    render(DailyActivityCalendar, { slug: 'pornic' });
    await screen.findByText('Rougegorge familier');

    getCalendarSpy.mockResolvedValueOnce(makeCalendar({ date: '2026-09-20' }));
    await fireEvent.change(screen.getByLabelText('Choisir une date'), { target: { value: '2026-09-20' } });

    expect(getCalendarSpy).toHaveBeenLastCalledWith('pornic', { date: '2026-09-20' });
  });

  it('recharge le jour par défaut du serveur quand le site change', async () => {
    const getCalendarSpy = vi.spyOn(client, 'getCalendar').mockResolvedValue(makeCalendar());

    const { rerender } = render(DailyActivityCalendar, { slug: 'pornic' });
    await screen.findByText('Rougegorge familier');
    expect(getCalendarSpy).toHaveBeenCalledWith('pornic', { date: undefined });

    await rerender({ slug: 'le-mans' });

    expect(getCalendarSpy).toHaveBeenLastCalledWith('le-mans', { date: undefined });
  });

  it('ignore la réponse la plus ancienne après deux changements rapides de date (pas de course)', async () => {
    let resolveFirst!: (v: CalendarResponse) => void;
    let resolveSecond!: (v: CalendarResponse) => void;
    const firstPromise = new Promise<CalendarResponse>((r) => (resolveFirst = r));
    const secondPromise = new Promise<CalendarResponse>((r) => (resolveSecond = r));

    const getCalendarSpy = vi
      .spyOn(client, 'getCalendar')
      .mockResolvedValueOnce(makeCalendar())
      .mockImplementationOnce(() => firstPromise)
      .mockImplementationOnce(() => secondPromise);

    render(DailyActivityCalendar, { slug: 'pornic' });
    await screen.findByText('Rougegorge familier');

    // Deux changements rapides de date (le 20, puis le 15) avant qu'aucune des deux réponses
    // ne soit revenue (même mécanisme que deux clics rapides sur "Veille").
    const dateInput = screen.getByLabelText('Choisir une date');
    await fireEvent.change(dateInput, { target: { value: '2026-09-20' } });
    await fireEvent.change(dateInput, { target: { value: '2026-09-15' } });

    expect(getCalendarSpy).toHaveBeenCalledTimes(3);
    expect(getCalendarSpy).toHaveBeenNthCalledWith(2, 'pornic', { date: '2026-09-20' });
    expect(getCalendarSpy).toHaveBeenNthCalledWith(3, 'pornic', { date: '2026-09-15' });

    // La réponse pour le 15 (la plus récemment demandée) revient en premier…
    resolveSecond(makeCalendar({ date: '2026-09-15', species: [makeSpecies({ common_name_fr: 'Merle noir' })] }));
    expect(await screen.findByText('Merle noir')).toBeInTheDocument();

    // …puis celle pour le 20 (périmée, réseau plus lent ce jour-là) répond après coup.
    resolveFirst(makeCalendar({ date: '2026-09-20', species: [makeSpecies({ common_name_fr: 'Pinson des arbres' })] }));
    await Promise.resolve();
    await Promise.resolve();

    // Avant le correctif, cette réponse périmée écrasait l'affichage après coup, sans aucun
    // indice visuel d'incohérence.
    expect(screen.queryByText('Pinson des arbres')).not.toBeInTheDocument();
    expect(screen.getByText('Merle noir')).toBeInTheDocument();
    expect(dateInput).toHaveValue('2026-09-15');
  });

  it('ignore le calendrier périmé du site quitté après un changement rapide de site (pas de course)', async () => {
    let resolvePornic!: (v: CalendarResponse) => void;
    let resolveLeMans!: (v: CalendarResponse) => void;
    const pornicPromise = new Promise<CalendarResponse>((r) => (resolvePornic = r));
    const leMansPromise = new Promise<CalendarResponse>((r) => (resolveLeMans = r));

    const getCalendarSpy = vi.spyOn(client, 'getCalendar').mockImplementation((slug) => {
      return slug === 'pornic' ? pornicPromise : leMansPromise;
    });

    const { rerender } = render(DailyActivityCalendar, { slug: 'pornic' });
    expect(getCalendarSpy).toHaveBeenCalledWith('pornic', { date: undefined });

    await rerender({ slug: 'le-mans' });
    expect(getCalendarSpy).toHaveBeenCalledWith('le-mans', { date: undefined });

    // Le Mans (site actuel, réponse rapide) répond en premier…
    resolveLeMans(makeCalendar({ site_slug: 'le-mans', species: [makeSpecies({ common_name_fr: 'Merle noir' })] }));
    expect(await screen.findByText('Merle noir')).toBeInTheDocument();

    // …puis Pornic (site quitté, réponse lente) répond après coup.
    resolvePornic(makeCalendar({ site_slug: 'pornic', species: [makeSpecies({ common_name_fr: 'Rougegorge familier' })] }));
    await Promise.resolve();
    await Promise.resolve();

    expect(screen.queryByText('Rougegorge familier')).not.toBeInTheDocument();
    expect(screen.getByText('Merle noir')).toBeInTheDocument();
  });
});
