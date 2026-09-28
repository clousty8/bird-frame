<script lang="ts">
  // Sous-onglet « Revue » (faux positifs/confirmations, contrat §6.25-§6.26 et §6.30).
  // Composant neuf ; ergonomie des actions inspirée de la lecture de
  // birdnet-go-ui/frontend/src/lib/desktop/components/ui/ActionMenu.svelte (motif
  // « confirmer / faux positif » avec badge de statut), réécrite ici en boutons inline
  // plutôt qu'un menu déroulant flottant (plus simple, pas de copie de code : le
  // contrat/payload diffèrent entièrement de BirdNET-Go, cf. docs/architecture.md §7.5).
  import { siteStore } from '../../stores/site.svelte';
  import { authStore } from '../../stores/auth.svelte';
  import { getDetections, postReview, ApiRequestError } from '../../api/client';
  import type { ReviewDetection, ReviewKind } from '../../api/types';
  import Badge from '../ui/Badge.svelte';
  import Button from '../ui/Button.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import AuthRequiredNotice from '../AuthRequiredNotice.svelte';
  import { formatInstant, formatConfidence } from './format';
  import { formatCount } from '../../format';

  const PAGE_SIZE = 25;

  let detections = $state<ReviewDetection[]>([]);
  let total = $state(0);
  let offset = $state(0);
  let loading = $state(true);
  let loadError = $state<string | null>(null);

  // ---- Filtres ----------------------------------------------------------------
  let filterDate = $state('');
  let filterSpecies = $state('');
  let filterMinConfidence = $state('');
  let filterUnreviewedOnly = $state(false);

  // ---- Actions par ligne --------------------------------------------------------
  let noteDraft = $state<Record<number, string>>({});
  let submittingFor = $state<number | null>(null);
  let actionError = $state<string | null>(null);
  let editingReviewFor = $state<number | null>(null);

  // Jeton de requête (même remède que StatsPage.svelte) : un double clic sur « Suivant », ou
  // un changement de filtre suivi d'un « Réinitialiser » avant la fin du premier chargement,
  // peut faire arriver la réponse la plus ancienne en dernier et écraser l'affichage avec une
  // page qui ne correspond plus à l'état de pagination affiché par les boutons.
  let loadRequestId = 0;

  async function load(): Promise<void> {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    const requestId = ++loadRequestId;
    loading = true;
    loadError = null;
    try {
      const minConfidence = filterMinConfidence.trim() !== '' ? Number(filterMinConfidence) : undefined;
      const response = await getDetections(slug, {
        date: filterDate || undefined,
        species: filterSpecies || undefined,
        minConfidence: minConfidence !== undefined && !Number.isNaN(minConfidence) ? minConfidence : undefined,
        review: filterUnreviewedOnly ? 'none' : undefined,
        limit: PAGE_SIZE,
        offset,
      });
      if (requestId !== loadRequestId) return;
      detections = response.detections;
      total = response.total;
    } catch (err) {
      if (requestId !== loadRequestId) return;
      loadError = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des détections.';
    } finally {
      if (requestId === loadRequestId) loading = false;
    }
  }

  $effect(() => {
    const slug = siteStore.selectedSlug;
    if (slug) void load();
  });

  function applyFilters(event: SubmitEvent): void {
    event.preventDefault();
    offset = 0;
    void load();
  }

  function resetFilters(): void {
    filterDate = '';
    filterSpecies = '';
    filterMinConfidence = '';
    filterUnreviewedOnly = false;
    offset = 0;
    void load();
  }

  function goToPage(direction: 1 | -1): void {
    const next = offset + direction * PAGE_SIZE;
    if (next < 0 || next >= total) return;
    offset = next;
    void load();
  }

  async function submitReview(detection: ReviewDetection, kind: ReviewKind): Promise<void> {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    submittingFor = detection.detection_id;
    actionError = null;
    const note = noteDraft[detection.detection_id]?.trim();
    try {
      await postReview(slug, { detection_id: detection.detection_id, kind, note: note ? note : undefined });
      editingReviewFor = null;
      delete noteDraft[detection.detection_id];
      await load();
    } catch (err) {
      actionError = err instanceof ApiRequestError ? err.message : "Erreur inconnue lors de l'enregistrement de la revue.";
    } finally {
      submittingFor = null;
    }
  }

  const REVIEW_BADGE: Record<'correct' | 'false_positive', { variant: 'success' | 'error'; label: string }> = {
    correct: { variant: 'success', label: 'confirmée' },
    false_positive: { variant: 'error', label: 'faux positif' },
  };
</script>

<div class="space-y-4">
  {#if !siteStore.selectedSlug}
    <EmptyState title="Aucun site sélectionné" description="Choisissez un site en haut de page pour revoir ses détections." />
  {:else}
    <form class="flex flex-wrap items-end gap-3" onsubmit={applyFilters}>
      <div>
        <label for="review-date" class="block text-xs font-medium mb-1">Date</label>
        <input id="review-date" type="date" class="input input-bordered input-sm" bind:value={filterDate} />
      </div>
      <div>
        <label for="review-species" class="block text-xs font-medium mb-1">Espèce (nom scientifique)</label>
        <input
          id="review-species"
          type="text"
          class="input input-bordered input-sm"
          placeholder="ex. Erithacus rubecula"
          bind:value={filterSpecies}
        />
      </div>
      <div>
        <label for="review-min-confidence" class="block text-xs font-medium mb-1">Confiance min.</label>
        <input
          id="review-min-confidence"
          type="number"
          min="0"
          max="1"
          step="0.05"
          class="input input-bordered input-sm w-24"
          placeholder="0.0"
          bind:value={filterMinConfidence}
        />
      </div>
      <label class="flex items-center gap-2 text-sm pb-2">
        <input type="checkbox" class="checkbox" bind:checked={filterUnreviewedOnly} />
        Non revues seulement
      </label>
      <Button type="submit" variant="primary" size="sm">Filtrer</Button>
      <Button type="button" variant="ghost" size="sm" onclick={resetFilters}>Réinitialiser</Button>
    </form>

    <AuthRequiredNotice action="confirmer une détection ou la marquer en faux positif" />

    {#if actionError}
      <ErrorAlert type="error" message={actionError} dismissible onDismiss={() => (actionError = null)} />
    {/if}

    {#if loading}
      <LoadingSpinner label="Chargement des détections…" />
    {:else if loadError}
      <div class="space-y-2">
        <ErrorAlert type="error" message={loadError} />
        <Button variant="default" onclick={load}>Réessayer</Button>
      </div>
    {:else if detections.length === 0}
      <EmptyState title="Aucune détection" description="Aucune détection ne correspond à ces filtres." />
    {:else}
      <div class="overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            <tr>
              <th>Heure</th>
              <th>Espèce</th>
              <th>Confiance</th>
              <th>Prédictions secondaires</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each detections as detection (detection.detection_id)}
              <tr>
                <td class="text-sm whitespace-nowrap">{formatInstant(detection.detected_at_utc)}</td>
                <td>
                  <div class="font-medium">{detection.common_name_fr ?? detection.scientific_name}</div>
                  <div class="text-xs text-muted italic">{detection.scientific_name}</div>
                </td>
                <td class="text-sm">{formatConfidence(detection.confidence)}</td>
                <td>
                  <div class="flex flex-wrap gap-1">
                    {#each detection.predictions.filter((p) => !p.is_primary) as prediction (prediction.scientific_name)}
                      <Badge variant="ghost" size="xs" text="{prediction.common_name_fr ?? prediction.scientific_name} {formatConfidence(prediction.confidence)}" />
                    {:else}
                      <span class="text-xs text-muted">—</span>
                    {/each}
                  </div>
                </td>
                <td>
                  {#if detection.review}
                    <Badge variant={REVIEW_BADGE[detection.review].variant} text={REVIEW_BADGE[detection.review].label} />
                    {#if detection.review_note}
                      <p class="text-xs text-muted mt-0.5">{detection.review_note}</p>
                    {/if}
                  {:else}
                    <Badge variant="neutral" text="non revue" />
                  {/if}
                </td>
                <td class="whitespace-nowrap">
                  {#if editingReviewFor === detection.detection_id || !detection.review}
                    <!-- Déconnecté (contrat §2.2) : le <fieldset disabled> désactive note et boutons. -->
                    <fieldset class="flex items-center gap-1.5 min-w-0" disabled={!authStore.unlocked}>
                      <input
                        type="text"
                        class="input input-bordered input-xs w-32"
                        placeholder="Note (optionnel)"
                        bind:value={
                          () => noteDraft[detection.detection_id] ?? '',
                          (value) => (noteDraft[detection.detection_id] = value)
                        }
                      />
                      <Button
                        variant="success"
                        size="xs"
                        disabled={submittingFor === detection.detection_id}
                        onclick={() => submitReview(detection, 'correct')}
                      >
                        Confirmer
                      </Button>
                      <Button
                        variant="error"
                        size="xs"
                        disabled={submittingFor === detection.detection_id}
                        onclick={() => submitReview(detection, 'false_positive')}
                      >
                        Faux positif
                      </Button>
                    </fieldset>
                  {:else}
                    <Button
                      variant="ghost"
                      size="xs"
                      disabled={!authStore.unlocked}
                      onclick={() => (editingReviewFor = detection.detection_id)}
                    >
                      Modifier
                    </Button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between text-sm">
        <span class="text-muted">
          {formatCount(total, 'détection')} — {offset + 1}–{Math.min(offset + PAGE_SIZE, total)}
        </span>
        <div class="flex gap-2">
          <Button variant="default" size="sm" disabled={offset === 0} onclick={() => goToPage(-1)}>Précédent</Button>
          <Button variant="default" size="sm" disabled={offset + PAGE_SIZE >= total} onclick={() => goToPage(1)}>
            Suivant
          </Button>
        </div>
      </div>
    {/if}
  {/if}
</div>
