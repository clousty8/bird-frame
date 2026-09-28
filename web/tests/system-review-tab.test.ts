import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import ReviewTab from '../src/lib/components/system/ReviewTab.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { DetectionsResponse, ReviewDetection } from '../src/lib/api/types';

function makeDetection(overrides: Partial<ReviewDetection> = {}): ReviewDetection {
  return {
    detection_id: 1523,
    node_id: 1,
    node_local_id: 4627,
    detected_at_utc: '2026-09-27T14:39:01Z',
    local_date: '2026-09-27',
    scientific_name: 'Parus major',
    common_name_fr: 'Mésange charbonnière',
    effective_scientific_name: 'Parus major',
    effective_common_name_fr: 'Mésange charbonnière',
    confidence: 0.72,
    source_display_name: 'Sound Card 1',
    has_clip: true,
    kept_clip_id: 88,
    audio_url: '/api/v1/recordings/88/audio',
    spectrogram_url: '/api/v1/recordings/88/spectrogram',
    review: null,
    review_note: null,
    rule: null,
    predictions: [
      { scientific_name: 'Parus major', common_name_fr: 'Mésange charbonnière', confidence: 0.72, is_primary: true },
      { scientific_name: 'Columba palumbus', common_name_fr: 'Pigeon ramier', confidence: 0.0242, is_primary: false },
    ],
    ...overrides,
  };
}

describe('ReviewTab', () => {
  beforeEach(() => {
    siteStore._resetForTests();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("invite à choisir un site quand aucun n'est sélectionné", () => {
    render(ReviewTab);

    expect(screen.getByText('Aucun site sélectionné')).toBeInTheDocument();
  });

  it('charge et affiche les détections avec leurs prédictions secondaires', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDetections').mockResolvedValue({
      detections: [makeDetection()],
      total: 1,
      limit: 25,
      offset: 0,
    });

    render(ReviewTab);

    expect(await screen.findByText('Mésange charbonnière')).toBeInTheDocument();
    expect(screen.getByText('72 %')).toBeInTheDocument();
    expect(screen.getByText('Pigeon ramier 2 %', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('non revue')).toBeInTheDocument();
  });

  it('affiche un état vide sans détections', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDetections').mockResolvedValue({ detections: [], total: 0, limit: 25, offset: 0 });

    render(ReviewTab);

    expect(await screen.findByText('Aucune détection')).toBeInTheDocument();
  });

  it('remonte une erreur de chargement (jamais avalée)', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDetections').mockRejectedValue(
      new client.ApiRequestError('internal_error', 'Erreur serveur.', 500)
    );

    render(ReviewTab);

    expect(await screen.findByText('Erreur serveur.')).toBeInTheDocument();
  });

  it('confirme une détection puis recharge la liste', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDetections')
      .mockResolvedValueOnce({ detections: [makeDetection()], total: 1, limit: 25, offset: 0 })
      .mockResolvedValueOnce({
        detections: [makeDetection({ review: 'correct' })],
        total: 1,
        limit: 25,
        offset: 0,
      });
    vi.spyOn(client, 'postReview').mockResolvedValue({
      review: {
        review_id: 17,
        detection_id: 1523,
        kind: 'correct',
        note: null,
        created_at: '2026-09-27T15:10:00Z',
        created_by: null,
        synced_to_node_at: null,
        command_status: null,
        detection: {
          scientific_name: 'Parus major',
          common_name_fr: 'Mésange charbonnière',
          confidence: 0.72,
          detected_at_utc: '2026-09-27T14:39:01Z',
        },
      },
      command_id: null,
    });

    render(ReviewTab);

    await screen.findByText('Mésange charbonnière');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));

    expect(client.postReview).toHaveBeenCalledWith('pornic', {
      detection_id: 1523,
      kind: 'correct',
      note: undefined,
    });
    expect(await screen.findByText('confirmée')).toBeInTheDocument();
  });

  it('ignore la réponse la plus ancienne pour un filtre suivi d\'un "Réinitialiser" rapide (pas de course)', async () => {
    // Note : les boutons de pagination "Précédent"/"Suivant" sont démontés pendant le
    // chargement (bloc `{#if loading}` qui masque tout le corps du tableau), donc deux vrais
    // clics rapides sur "Suivant" sont impossibles via l'UI — en revanche le formulaire de
    // filtres (avec "Réinitialiser") reste affiché pendant le chargement : c'est le second
    // scénario décrit par le constat, littéralement reproductible.
    siteStore.select('pornic');

    let resolveFiltered!: (v: DetectionsResponse) => void;
    let resolveReset!: (v: DetectionsResponse) => void;
    const filteredPromise = new Promise<DetectionsResponse>((r) => (resolveFiltered = r));
    const resetPromise = new Promise<DetectionsResponse>((r) => (resolveReset = r));

    const getDetectionsSpy = vi
      .spyOn(client, 'getDetections')
      .mockResolvedValueOnce({ detections: [makeDetection()], total: 1, limit: 25, offset: 0 })
      .mockImplementationOnce(() => filteredPromise)
      .mockImplementationOnce(() => resetPromise);

    render(ReviewTab);
    await screen.findByText('Mésange charbonnière');

    await fireEvent.click(screen.getByRole('button', { name: 'Filtrer' }));
    // Avant que la réponse filtrée ne revienne, l'utilisateur clique "Réinitialiser".
    await fireEvent.click(screen.getByRole('button', { name: 'Réinitialiser' }));

    expect(getDetectionsSpy).toHaveBeenCalledTimes(3);

    // La réinitialisation (la plus récemment demandée) répond en premier…
    resolveReset({
      detections: [makeDetection({ detection_id: 999, common_name_fr: 'Merle noir', scientific_name: 'Turdus merula' })],
      total: 1,
      limit: 25,
      offset: 0,
    });
    expect(await screen.findByText('Merle noir')).toBeInTheDocument();

    // …puis la requête filtrée (périmée) répond après coup.
    resolveFiltered({
      detections: [
        makeDetection({ detection_id: 998, common_name_fr: 'Pinson des arbres', scientific_name: 'Fringilla coelebs' }),
      ],
      total: 1,
      limit: 25,
      offset: 0,
    });
    await Promise.resolve();
    await Promise.resolve();

    // Avant le correctif, cette réponse périmée aurait écrasé l'affichage après coup avec les
    // résultats du filtre pourtant annulé par "Réinitialiser".
    expect(screen.queryByText('Pinson des arbres')).not.toBeInTheDocument();
    expect(screen.getByText('Merle noir')).toBeInTheDocument();
  });

  it('désactive la pagination "Précédent" sur la première page', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getDetections').mockResolvedValue({
      detections: [makeDetection()],
      total: 50,
      limit: 25,
      offset: 0,
    });

    render(ReviewTab);

    await screen.findByText('Mésange charbonnière');
    expect(screen.getByRole('button', { name: 'Précédent' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Suivant' })).not.toBeDisabled();
  });
});
