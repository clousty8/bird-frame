import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import SpeciesSearchInput from '../src/lib/components/system/SpeciesSearchInput.svelte';
import * as client from '../src/lib/api/client';
import type { UniverseSpecies } from '../src/lib/api/types';

function makeSpecies(overrides: Partial<UniverseSpecies> = {}): UniverseSpecies {
  return {
    scientific_name: 'Erithacus rubecula',
    common_name_fr: 'Rougegorge familier',
    order: 'Passeriformes',
    family: 'Muscicapidae',
    in_france_universe: true,
    france_max_score: 0.99,
    detected_sites: ['pornic'],
    total_detections: 10,
    site_total: null,
    photo_url: null,
    has_sheet: true,
    ...overrides,
  };
}

describe('SpeciesSearchInput', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('cherche après un court délai (debounce) et affiche les résultats', async () => {
    vi.useFakeTimers();
    vi.spyOn(client, 'getSpeciesList').mockResolvedValue({
      species: [makeSpecies()],
      total: 1,
      limit: 8,
      offset: 0,
    });

    render(SpeciesSearchInput, { id: 'sp', label: 'Espèce', onSelect: vi.fn() });

    const input = screen.getByLabelText('Espèce');
    await fireEvent.input(input, { target: { value: 'roug' } });
    expect(client.getSpeciesList).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(350);

    expect(client.getSpeciesList).toHaveBeenCalledWith({ q: 'roug', limit: 8 });
    expect(await screen.findByRole('option', { name: /Rougegorge familier/ })).toBeInTheDocument();
  });

  it("n'interroge pas le serveur pour moins de 2 caractères", async () => {
    vi.useFakeTimers();
    vi.spyOn(client, 'getSpeciesList').mockResolvedValue({ species: [], total: 0, limit: 8, offset: 0 });

    render(SpeciesSearchInput, { id: 'sp2', label: 'Espèce', onSelect: vi.fn() });

    await fireEvent.input(screen.getByLabelText('Espèce'), { target: { value: 'r' } });
    await vi.advanceTimersByTimeAsync(350);

    expect(client.getSpeciesList).not.toHaveBeenCalled();
  });

  it("appelle onSelect avec l'espèce choisie et vide le champ", async () => {
    vi.useFakeTimers();
    vi.spyOn(client, 'getSpeciesList').mockResolvedValue({
      species: [makeSpecies()],
      total: 1,
      limit: 8,
      offset: 0,
    });
    const onSelect = vi.fn();

    render(SpeciesSearchInput, { id: 'sp3', label: 'Espèce', onSelect });

    await fireEvent.input(screen.getByLabelText('Espèce'), { target: { value: 'roug' } });
    await vi.advanceTimersByTimeAsync(350);
    await fireEvent.click(await screen.findByRole('option', { name: /Rougegorge familier/ }));

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ scientific_name: 'Erithacus rubecula' }));
  });

  it('affiche une espèce déjà sélectionnée en lecture avec un bouton « Changer »', () => {
    render(SpeciesSearchInput, {
      id: 'sp4',
      label: 'Espèce',
      onSelect: vi.fn(),
      selectedScientificName: 'Erithacus rubecula',
      selectedCommonName: 'Rougegorge familier',
      onClear: vi.fn(),
    });

    expect(screen.getByText('Rougegorge familier')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Changer' })).toBeInTheDocument();
  });

  it("ignore une réponse périmée arrivée après celle d'une frappe plus récente (pas de course)", async () => {
    vi.useFakeTimers();
    let resolveFirst!: (v: { species: UniverseSpecies[]; total: number; limit: number; offset: number }) => void;
    let resolveSecond!: (v: { species: UniverseSpecies[]; total: number; limit: number; offset: number }) => void;
    const firstPromise = new Promise<{ species: UniverseSpecies[]; total: number; limit: number; offset: number }>(
      (r) => (resolveFirst = r)
    );
    const secondPromise = new Promise<{ species: UniverseSpecies[]; total: number; limit: number; offset: number }>(
      (r) => (resolveSecond = r)
    );
    vi.spyOn(client, 'getSpeciesList')
      .mockImplementationOnce(() => firstPromise)
      .mockImplementationOnce(() => secondPromise);

    render(SpeciesSearchInput, { id: 'sp6', label: 'Espèce', onSelect: vi.fn() });

    const input = screen.getByLabelText('Espèce');
    // Tape « mesan » (recherche lancée après le debounce)…
    await fireEvent.input(input, { target: { value: 'mesan' } });
    await vi.advanceTimersByTimeAsync(300);
    // … puis complète en « mesange char » avant que la première réponse ne revienne.
    await fireEvent.input(input, { target: { value: 'mesange char' } });
    await vi.advanceTimersByTimeAsync(300);

    expect(client.getSpeciesList).toHaveBeenCalledTimes(2);

    // La réponse la plus récente (« mesange char ») arrive d'abord…
    resolveSecond({
      species: [makeSpecies({ scientific_name: 'Parus major', common_name_fr: 'Mésange charbonnière' })],
      total: 1,
      limit: 8,
      offset: 0,
    });
    expect(await screen.findByRole('option', { name: /Mésange charbonnière/ })).toBeInTheDocument();

    // … puis celle de « mesan » (périmée) répond après coup.
    resolveFirst({
      species: [makeSpecies({ scientific_name: 'Erithacus rubecula', common_name_fr: 'Rougegorge familier' })],
      total: 1,
      limit: 8,
      offset: 0,
    });
    await Promise.resolve();
    await Promise.resolve();

    // Avant le correctif, cette réponse périmée écrasait la liste : l'utilisateur pouvait
    // alors cliquer sur une suggestion qui ne correspond pas à ce qu'il a réellement tapé.
    expect(screen.queryByRole('option', { name: /Rougegorge familier/ })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Mésange charbonnière/ })).toBeInTheDocument();
  });

  it('remonte une erreur de recherche sans la faire disparaître silencieusement', async () => {
    vi.useFakeTimers();
    vi.spyOn(client, 'getSpeciesList').mockRejectedValue(
      new client.ApiRequestError('internal_error', 'Recherche indisponible.', 500)
    );

    render(SpeciesSearchInput, { id: 'sp5', label: 'Espèce', onSelect: vi.fn() });

    await fireEvent.input(screen.getByLabelText('Espèce'), { target: { value: 'roug' } });
    await vi.advanceTimersByTimeAsync(350);

    expect(await screen.findByText('Recherche indisponible.')).toBeInTheDocument();
  });
});
