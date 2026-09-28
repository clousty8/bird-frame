// Fiche espèce, section « Sources » : les liens Wikipédia FR/EN étaient suivis de la liste
// brute `sources` de la fiche, qui répète presque toujours les mêmes URLs.
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, within } from '@testing-library/svelte';
import { buildSourceLinks, sourceKey } from '../src/lib/components/species/sources';
import SourcesSection from '../src/lib/components/species/SourcesSection.svelte';
import type { WikiRef } from '../src/lib/api/types';

const WIKI_FR: WikiRef = {
  title: 'Rouge-gorge familier',
  url: 'https://fr.wikipedia.org/wiki/Rouge-gorge_familier',
  description: null,
  extract: null,
};
const WIKI_EN: WikiRef = {
  title: 'European robin',
  url: 'https://en.wikipedia.org/wiki/European_robin',
  description: null,
  extract: null,
};
// Valeur réelle de GET /api/v1/species/Erithacus%20rubecula (27/09/2026).
const REAL_SOURCES = [
  'https://fr.wikipedia.org/wiki/Rouge-gorge_familier',
  'https://en.wikipedia.org/wiki/European_robin',
  'https://www.oiseaux.net/fiche.html?id=81',
];

describe('buildSourceLinks', () => {
  it('Wikipédia FR/EN en tête avec libellé, puis seulement les autres sources, par nom d’hôte', () => {
    const links = buildSourceLinks({ fr: WIKI_FR, en: WIKI_EN }, REAL_SOURCES);
    expect(links.map((link) => link.label)).toEqual(['Wikipédia (FR)', 'Wikipédia (EN)', 'oiseaux.net']);
    expect(links[2]?.href).toBe('https://www.oiseaux.net/fiche.html?id=81');
  });

  it('dédoublonne malgré les variantes d’écriture (mobile, http, encodage, barre finale)', () => {
    const links = buildSourceLinks({ fr: WIKI_FR, en: null }, [
      'http://fr.m.wikipedia.org/wiki/Rouge-gorge%20familier/',
      'https://fr.wikipedia.org/wiki/Rouge-gorge_familier#Description',
      'https://www.oiseaux.net/fiche.html?id=81',
      'https://oiseaux.net/fiche.html?id=81',
    ]);
    expect(links.map((link) => link.label)).toEqual(['Wikipédia (FR)', 'oiseaux.net']);
    expect(sourceKey('https://fr.m.wikipedia.org/wiki/A_b')).toBe(sourceKey('https://fr.wikipedia.org/wiki/A%20b'));
  });

  it('libelle une autre page Wikipédia par son titre et distingue deux pages du même hôte', () => {
    const links = buildSourceLinks({ fr: WIKI_FR, en: null }, [
      'https://fr.wikipedia.org/wiki/Turdidae',
      'https://www.oiseaux.net/fiche.html?id=81',
      'https://www.oiseaux.net/chants.html?id=81',
    ]);
    expect(links.map((link) => link.label)).toEqual([
      'Wikipédia (FR)',
      'Wikipédia (FR) — Turdidae',
      'oiseaux.net — fiche.html?id=81',
      'oiseaux.net — chants.html?id=81',
    ]);
  });

  it("n'emploie jamais une valeur non http(s) comme lien (fiches générées par IA)", () => {
    const links = buildSourceLinks({ fr: null, en: null }, ['javascript:alert(1)', 'Livre : Guide Delachaux']);
    expect(links.every((link) => link.href === null)).toBe(true);
    expect(links.map((link) => link.label)).toEqual(['javascript:alert(1)', 'Livre : Guide Delachaux']);
  });
});

describe('SourcesSection — rendu des sources', () => {
  afterEach(() => cleanup());

  it("n'affiche plus les URLs brutes qui répètent Wikipédia", () => {
    render(SourcesSection, { links: buildSourceLinks({ fr: WIKI_FR, en: WIKI_EN }, REAL_SOURCES) });

    const list = screen.getByRole('heading', { name: 'Sources' }).parentElement;
    if (!list) throw new Error('bloc Sources introuvable');
    const links = within(list).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(['Wikipédia (FR)', 'Wikipédia (EN)', 'oiseaux.net']);
    expect(within(list).queryByText(/https:\/\//)).not.toBeInTheDocument();
  });
});
