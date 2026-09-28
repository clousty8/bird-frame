import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import ThresholdsTab from '../src/lib/components/system/ThresholdsTab.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { DynamicThreshold } from '../src/lib/api/types';

function makeThreshold(overrides: Partial<DynamicThreshold> = {}): DynamicThreshold {
  return {
    node_id: 1,
    scientific_name: 'Prunella modularis',
    common_name_fr: 'Accenteur mouchet',
    node_species_name: 'accenteur mouchet',
    level: 3,
    current_value: 0.2,
    base_threshold: 0.6,
    high_conf_count: 19,
    trigger_count: 19,
    is_active: true,
    expires_at: '2026-09-28T14:26:19Z',
    last_triggered_at: '2026-09-27T14:39:38Z',
    first_created_at: '2026-09-27T14:39:38Z',
    reset_pending: false,
    ...overrides,
  };
}

describe('ThresholdsTab', () => {
  beforeEach(() => {
    siteStore._resetForTests();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("invite à choisir un site quand aucun n'est sélectionné", () => {
    render(ThresholdsTab);

    expect(screen.getByText('Aucun site sélectionné')).toBeInTheDocument();
  });

  it('charge et affiche les seuils dynamiques', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDynamicThresholds').mockResolvedValue({
      site_slug: 'pornic',
      snapshot_at: '2026-09-27T14:40:00Z',
      thresholds: [makeThreshold()],
    });

    render(ThresholdsTab);

    expect(await screen.findByText('Accenteur mouchet')).toBeInTheDocument();
    expect(screen.getByText('niveau 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Réinitialiser' })).toBeInTheDocument();
  });

  it('affiche un état vide sans seuil actif', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDynamicThresholds').mockResolvedValue({
      site_slug: 'pornic',
      snapshot_at: null,
      thresholds: [],
    });

    render(ThresholdsTab);

    expect(await screen.findByText('Aucun seuil dynamique actif')).toBeInTheDocument();
  });

  it('remonte une erreur de chargement (jamais avalée)', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDynamicThresholds').mockRejectedValue(
      new client.ApiRequestError('internal_error', 'Erreur serveur.', 500)
    );

    render(ThresholdsTab);

    expect(await screen.findByText('Erreur serveur.')).toBeInTheDocument();
  });

  it('réinitialise un seuil puis recharge le miroir', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDynamicThresholds')
      .mockResolvedValueOnce({ site_slug: 'pornic', snapshot_at: null, thresholds: [makeThreshold()] })
      .mockResolvedValueOnce({
        site_slug: 'pornic',
        snapshot_at: null,
        thresholds: [makeThreshold({ reset_pending: true })],
      });
    vi.spyOn(client, 'resetDynamicThreshold').mockResolvedValue({ commands: [] });

    render(ThresholdsTab);

    await screen.findByText('Accenteur mouchet');
    await fireEvent.click(screen.getByRole('button', { name: 'Réinitialiser' }));

    expect(client.resetDynamicThreshold).toHaveBeenCalledWith('pornic', 'Prunella modularis');
    expect(await screen.findByText(/Réinitialisation demandée/)).toBeInTheDocument();
    expect(await screen.findByText('réinitialisation en attente')).toBeInTheDocument();
  });

  it('n\'affiche pas de bouton pour une réinitialisation déjà en attente', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDynamicThresholds').mockResolvedValue({
      site_slug: 'pornic',
      snapshot_at: null,
      thresholds: [makeThreshold({ reset_pending: true })],
    });

    render(ThresholdsTab);

    await screen.findByText('Accenteur mouchet');
    expect(screen.queryByRole('button', { name: 'Réinitialiser' })).not.toBeInTheDocument();
    expect(screen.getByText('réinitialisation en attente')).toBeInTheDocument();
  });
});
