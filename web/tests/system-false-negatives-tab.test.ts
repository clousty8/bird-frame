import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import FalseNegativesTab from '../src/lib/components/system/FalseNegativesTab.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { FalseNegative } from '../src/lib/api/types';

function makeReport(overrides: Partial<FalseNegative> = {}): FalseNegative {
  return {
    id: 3,
    scientific_name: 'Strix aluco',
    common_name_fr: 'Chouette hulotte',
    known_species: true,
    approx_time_utc: '2026-09-26T21:30:00Z',
    notes: 'Hulotte entendue vers 23 h 30',
    reported_at: '2026-09-27T15:12:00Z',
    reported_by: null,
    ...overrides,
  };
}

describe('FalseNegativesTab', () => {
  beforeEach(() => {
    siteStore._resetForTests();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("invite à choisir un site quand aucun n'est sélectionné", () => {
    render(FalseNegativesTab);

    expect(screen.getByText('Aucun site sélectionné')).toBeInTheDocument();
  });

  it('charge et affiche les signalements existants', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getFalseNegatives').mockResolvedValue({
      false_negatives: [makeReport()],
      total: 1,
      limit: 25,
      offset: 0,
    });

    render(FalseNegativesTab);

    expect(await screen.findByText('Chouette hulotte')).toBeInTheDocument();
    expect(screen.getByText('Hulotte entendue vers 23 h 30')).toBeInTheDocument();
  });

  it('affiche un état vide sans signalement', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getFalseNegatives').mockResolvedValue({
      false_negatives: [],
      total: 0,
      limit: 25,
      offset: 0,
    });

    render(FalseNegativesTab);

    expect(await screen.findByText('Aucun signalement')).toBeInTheDocument();
  });

  it('remonte une erreur de chargement (jamais avalée)', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getFalseNegatives').mockRejectedValue(
      new client.ApiRequestError('internal_error', 'Erreur serveur.', 500)
    );

    render(FalseNegativesTab);

    expect(await screen.findByText('Erreur serveur.')).toBeInTheDocument();
  });

  it('envoie un signalement via le champ de repli en texte libre', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getFalseNegatives')
      .mockResolvedValueOnce({ false_negatives: [], total: 0, limit: 25, offset: 0 })
      .mockResolvedValueOnce({ false_negatives: [makeReport()], total: 1, limit: 25, offset: 0 });
    vi.spyOn(client, 'postFalseNegative').mockResolvedValue({ false_negative: makeReport() });

    render(FalseNegativesTab);

    await screen.findByText('Aucun signalement');

    const freeText = screen.getByLabelText('Introuvable dans la recherche ? Saisissez le nom scientifique directement :');
    await fireEvent.input(freeText, { target: { value: 'Strix aluco' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Signaler' }));

    expect(client.postFalseNegative).toHaveBeenCalledWith('pornic', {
      scientific_name: 'Strix aluco',
      approx_time_utc: null,
      notes: null,
    });
    expect(await screen.findByText(/Signalement enregistré/)).toBeInTheDocument();
  });

  it('refuse un envoi sans espèce renseignée', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getFalseNegatives').mockResolvedValue({ false_negatives: [], total: 0, limit: 25, offset: 0 });
    const postSpy = vi.spyOn(client, 'postFalseNegative');

    render(FalseNegativesTab);
    await screen.findByText('Aucun signalement');

    await fireEvent.click(screen.getByRole('button', { name: 'Signaler' }));

    expect(postSpy).not.toHaveBeenCalled();
    expect(await screen.findByText(/Indiquez l'espèce/)).toBeInTheDocument();
  });
});
