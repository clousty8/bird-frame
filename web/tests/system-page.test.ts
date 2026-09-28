import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import SystemPage from '../src/routes/SystemPage.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';

// Mock de toutes les routes appelées par les cinq sous-onglets : cette page mère ne
// possède pas ses propres appels réseau, seul le routage vers le bon composant est
// à vérifier ici (le contenu de chaque onglet est testé isolément, voir
// tests/system-{nodes,rules,review,false-negatives,thresholds}-tab.test.ts).
describe('SystemPage — routage des sous-onglets', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    siteStore.select('pornic');
    vi.spyOn(client, 'getNodes').mockResolvedValue({ nodes: [] });
    vi.spyOn(client, 'getSpeciesRules').mockResolvedValue({ site_slug: 'pornic', rules: [] });
    vi.spyOn(client, 'getDetections').mockResolvedValue({ detections: [], total: 0, limit: 25, offset: 0 });
    vi.spyOn(client, 'getFalseNegatives').mockResolvedValue({ false_negatives: [], total: 0, limit: 25, offset: 0 });
    vi.spyOn(client, 'getDynamicThresholds').mockResolvedValue({ site_slug: 'pornic', snapshot_at: null, thresholds: [] });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('affiche le titre et les cinq sous-onglets de navigation', () => {
    render(SystemPage, { tab: 'nodes' });

    expect(screen.getByRole('heading', { name: 'Système' })).toBeInTheDocument();
    for (const label of ['Nœuds', 'Règles par espèce', 'Revue', 'Faux négatifs', 'Seuils dynamiques']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('monte NodesTab sur /system/nodes', async () => {
    render(SystemPage, { tab: 'nodes' });

    expect(await screen.findByText('Aucun nœud enregistré')).toBeInTheDocument();
  });

  it('monte RulesTab sur /system/rules', async () => {
    render(SystemPage, { tab: 'rules' });

    expect(await screen.findByText('Aucune règle')).toBeInTheDocument();
  });

  it('monte ReviewTab sur /system/review', async () => {
    render(SystemPage, { tab: 'review' });

    expect(await screen.findByText('Aucune détection')).toBeInTheDocument();
  });

  it('monte FalseNegativesTab sur /system/false-negatives', async () => {
    render(SystemPage, { tab: 'false-negatives' });

    expect(await screen.findByText('Aucun signalement')).toBeInTheDocument();
  });

  it('monte ThresholdsTab sur /system/thresholds', async () => {
    render(SystemPage, { tab: 'thresholds' });

    expect(await screen.findByText('Aucun seuil dynamique actif')).toBeInTheDocument();
  });

  it('retombe sur le premier onglet pour une valeur de tab inconnue', async () => {
    render(SystemPage, { tab: 'ceci-nexiste-pas' });

    expect(await screen.findByText('Aucun nœud enregistré')).toBeInTheDocument();
  });
});
