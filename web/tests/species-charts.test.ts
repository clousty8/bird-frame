// Fiche espèce : graphiques « Présence » (par mois, par site) et « Statistiques » (par mois,
// par heure). Défaut corrigé : les barres portaient `height: N%` dans une colonne sans
// hauteur définie (rangée flex `items-end`) ; le pourcentage se résolvait en `auto`, soit
// 0 px — sections vides alors que l'API renvoyait les données. jsdom ne fait pas de mise en
// page : on vérifie donc que chaque barre a une hauteur ABSOLUE en pixels, proportionnelle
// aux données, et jamais un pourcentage qui dépendrait du parent.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import PresenceBySiteSection from '../src/lib/components/species/PresenceBySiteSection.svelte';
import StatsSection from '../src/lib/components/species/StatsSection.svelte';
import { barHeightsPx, MIN_VISIBLE_BAR_PX } from '../src/lib/components/species/barChart';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { PresenceBySite, PresenceResponse } from '../src/lib/api/types';

const SEPTEMBER_ONLY = [0, 0, 0, 0, 0, 0, 0, 0, 2436, 0, 0, 0];

function barHeights(container: HTMLElement): string[] {
  return [...container.querySelectorAll<HTMLElement>('[data-testid="mini-bar"]')].map((bar) => bar.style.height);
}

function pixels(height: string): number {
  const match = /^(\d+(?:\.\d+)?)px$/.exec(height);
  if (!match || !match[1]) throw new Error(`hauteur non exprimée en px : « ${height} »`);
  return Number(match[1]);
}

describe('barHeightsPx', () => {
  it('donne toute la hauteur au maximum, 0 aux valeurs nulles', () => {
    expect(barHeightsPx(SEPTEMBER_ONLY, 64)).toEqual([0, 0, 0, 0, 0, 0, 0, 0, 64, 0, 0, 0]);
  });

  it('garde visible une petite valeur face à un très grand maximum', () => {
    const [small, big] = barHeightsPx([1, 10_000], 80);
    expect(small).toBe(MIN_VISIBLE_BAR_PX);
    expect(big).toBe(80);
  });

  it('série entièrement nulle → barres à 0 sans division par zéro', () => {
    expect(barHeightsPx([0, 0, 0], 64)).toEqual([0, 0, 0]);
  });
});

describe('PresenceBySiteSection — barres par mois', () => {
  afterEach(() => cleanup());

  it('dessine la barre de septembre à pleine hauteur, en pixels (données réelles de Pornic)', () => {
    const site: PresenceBySite = {
      site_slug: 'pornic',
      site_name: 'Pornic',
      total: 2436,
      first_seen_utc: '2026-09-26T05:40:02Z',
      last_seen_utc: '2026-09-27T14:31:09Z',
      days_seen: 2,
      max_confidence: 0.99,
      months: SEPTEMBER_ONLY,
      rule: null,
      redirect_to_scientific_name: null,
    };
    const { container } = render(PresenceBySiteSection, { presenceBySite: [site] });

    const heights = barHeights(container);
    expect(heights).toHaveLength(12);
    const px = heights.map(pixels);
    expect(px[8]).toBe(64);
    expect(px.filter((_value, index) => index !== 8).every((value) => value === 0)).toBe(true);

    const track = container.querySelector<HTMLElement>('[data-testid="mini-bar-chart-track"]');
    expect(track?.style.height).toBe('64px');

    // Pluriel correct et infobulle lisible.
    expect(screen.getByText(/2\s436 détections/u)).toBeInTheDocument();
    expect(screen.getByText(/2 jours/)).toBeInTheDocument();
    expect(container.querySelectorAll('[data-testid="mini-bar"]')[8]).toHaveAttribute('title', 'septembre : 2436');
  });

  it('accorde « 1 détection · 1 jour » au singulier', () => {
    const site: PresenceBySite = {
      site_slug: 'pornic',
      site_name: 'Pornic',
      total: 1,
      first_seen_utc: '2026-09-26T05:40:02Z',
      last_seen_utc: '2026-09-26T05:40:02Z',
      days_seen: 1,
      max_confidence: 0.8,
      months: [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
      rule: null,
      redirect_to_scientific_name: null,
    };
    render(PresenceBySiteSection, { presenceBySite: [site] });
    expect(screen.getByText('1 détection')).toBeInTheDocument();
    expect(screen.getByText(/· 1 jour$/)).toBeInTheDocument();
  });
});

describe('StatsSection — par mois et par heure', () => {
  beforeEach(() => {
    siteStore._resetForTests();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('dessine des barres non vides, en pixels, pour les mois et les heures', async () => {
    const hours = new Array(24).fill(0) as number[];
    hours[7] = 120;
    hours[8] = 274;
    hours[20] = 3;
    const presence: PresenceResponse = {
      scientific_name: 'Erithacus rubecula',
      site_slug: 'pornic',
      total: 397,
      first_seen_utc: '2026-09-26T05:40:02Z',
      last_seen_utc: '2026-09-27T14:31:09Z',
      months: [0, 0, 0, 0, 0, 0, 0, 0, 397, 0, 0, 0],
      hours,
      by_day: null,
    };
    vi.spyOn(client, 'getSpeciesPresence').mockResolvedValue(presence);

    const { container } = render(StatsSection, { scientificName: 'Erithacus rubecula' });
    await screen.findByText('Par heure');

    const heights = barHeights(container).map(pixels);
    expect(heights).toHaveLength(12 + 24);
    const months = heights.slice(0, 12);
    const hourBars = heights.slice(12);
    expect(months[8]).toBe(80);
    expect(hourBars[8]).toBe(80);
    expect(hourBars[7]).toBe(Math.round((120 / 274) * 80));
    expect(hourBars[20]).toBeGreaterThanOrEqual(MIN_VISIBLE_BAR_PX);
    expect(hourBars[0]).toBe(0);
  });
});
