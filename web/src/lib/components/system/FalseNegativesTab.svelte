<script lang="ts">
  // Sous-onglet « Faux négatifs » (contrat §6.27-§6.28). Composant neuf.
  // Contrairement à un faux positif, BirdNET-Go n'a aucune notion de faux négatif — c'est
  // un enregistrement 100% côté serveur, sans commande vers un nœud (architecture.md §7.5).
  import { siteStore } from '../../stores/site.svelte';
  import { authStore } from '../../stores/auth.svelte';
  import { getFalseNegatives, postFalseNegative, ApiRequestError } from '../../api/client';
  import type { FalseNegative, UniverseSpecies } from '../../api/types';
  import Badge from '../ui/Badge.svelte';
  import Button from '../ui/Button.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import AuthRequiredNotice from '../AuthRequiredNotice.svelte';
  import SpeciesSearchInput from './SpeciesSearchInput.svelte';
  import { formatInstant } from './format';
  import { formatCount } from '../../format';

  const PAGE_SIZE = 25;

  let reports = $state<FalseNegative[]>([]);
  let total = $state(0);
  let offset = $state(0);
  let loading = $state(true);
  let loadError = $state<string | null>(null);

  // ---- Formulaire ---------------------------------------------------------------
  let formSpeciesName = $state<string | null>(null);
  let formSpeciesCommon = $state<string | null>(null);
  let formFreeTextSpecies = $state(''); // repli si l'espèce n'est trouvée dans aucune recherche
  let formApproxTime = $state(''); // <input type="datetime-local">
  let formNotes = $state('');
  let formSubmitting = $state(false);
  let formError = $state<string | null>(null);
  let formSuccess = $state<string | null>(null);

  async function load(): Promise<void> {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    loading = true;
    loadError = null;
    try {
      const response = await getFalseNegatives(slug, { limit: PAGE_SIZE, offset });
      reports = response.false_negatives;
      total = response.total;
    } catch (err) {
      loadError = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des signalements.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const slug = siteStore.selectedSlug;
    if (slug) void load();
  });

  function selectFormSpecies(species: UniverseSpecies): void {
    formSpeciesName = species.scientific_name;
    formSpeciesCommon = species.common_name_fr;
    formFreeTextSpecies = '';
    formError = null;
  }

  function goToPage(direction: 1 | -1): void {
    const next = offset + direction * PAGE_SIZE;
    if (next < 0 || next >= total) return;
    offset = next;
    void load();
  }

  async function submitForm(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const slug = siteStore.selectedSlug;
    if (!slug) return;

    const scientificName = formSpeciesName ?? formFreeTextSpecies.trim();
    if (!scientificName) {
      formError = "Indiquez l'espèce entendue ou vue (recherchez-la, ou saisissez son nom scientifique).";
      return;
    }

    formSubmitting = true;
    formError = null;
    formSuccess = null;
    try {
      const response = await postFalseNegative(slug, {
        scientific_name: scientificName,
        approx_time_utc: formApproxTime ? new Date(formApproxTime).toISOString() : null,
        notes: formNotes.trim() !== '' ? formNotes.trim() : null,
      });
      formSuccess = `Signalement enregistré pour ${response.false_negative.common_name_fr ?? response.false_negative.scientific_name}.`;
      formSpeciesName = null;
      formSpeciesCommon = null;
      formFreeTextSpecies = '';
      formApproxTime = '';
      formNotes = '';
      offset = 0;
      await load();
    } catch (err) {
      formError = err instanceof ApiRequestError ? err.message : "Erreur inconnue lors de l'enregistrement du signalement.";
    } finally {
      formSubmitting = false;
    }
  }

</script>

<div class="space-y-6">
  {#if !siteStore.selectedSlug}
    <EmptyState title="Aucun site sélectionné" description="Choisissez un site en haut de page pour signaler un faux négatif." />
  {:else}
    <AuthRequiredNotice action="signaler une espèce non détectée" />

    <!-- Déconnecté (contrat §2.2) : le <fieldset disabled> désactive tout le formulaire. -->
    <form class="max-w-xl" onsubmit={submitForm}>
      <fieldset class="space-y-3 min-w-0" disabled={!authStore.unlocked}>
        <h2 class="text-lg font-semibold">J'ai entendu ou vu une espèce non détectée</h2>

        {#if formSpeciesName}
          <SpeciesSearchInput
            id="fn-species"
            label="Espèce"
            selectedScientificName={formSpeciesName}
            selectedCommonName={formSpeciesCommon}
            onSelect={selectFormSpecies}
            onClear={() => {
              formSpeciesName = null;
              formSpeciesCommon = null;
            }}
          />
        {:else}
          <SpeciesSearchInput id="fn-species" label="Espèce" onSelect={selectFormSpecies} />
          <div>
            <label for="fn-species-freetext" class="block text-xs text-muted mb-1">
              Introuvable dans la recherche ? Saisissez le nom scientifique directement :
            </label>
            <input
              id="fn-species-freetext"
              type="text"
              class="input input-bordered w-full"
              placeholder="ex. Strix aluco"
              bind:value={formFreeTextSpecies}
            />
          </div>
        {/if}

        <div>
          <label for="fn-time" class="block text-sm font-medium mb-1">Heure approximative (optionnel)</label>
          <input id="fn-time" type="datetime-local" class="input input-bordered" bind:value={formApproxTime} />
        </div>

        <div>
          <label for="fn-notes" class="block text-sm font-medium mb-1">Notes (optionnel)</label>
          <textarea
            id="fn-notes"
            class="textarea textarea-bordered w-full"
            rows="2"
            maxlength="1000"
            bind:value={formNotes}
            placeholder="ex. Hulotte entendue vers 23 h 30"
          ></textarea>
        </div>

        {#if formError}
          <ErrorAlert type="error" message={formError} />
        {/if}
        {#if formSuccess}
          <p role="status" class="text-sm text-[var(--color-success)]">{formSuccess}</p>
        {/if}

        <Button type="submit" variant="primary" disabled={formSubmitting}>
          {formSubmitting ? 'Enregistrement…' : 'Signaler'}
        </Button>
      </fieldset>
    </form>

    <div>
      <h2 class="text-lg font-semibold mb-3">Signalements</h2>

      {#if loading}
        <LoadingSpinner label="Chargement des signalements…" />
      {:else if loadError}
        <div class="space-y-2">
          <ErrorAlert type="error" message={loadError} />
          <Button variant="default" onclick={load}>Réessayer</Button>
        </div>
      {:else if reports.length === 0}
        <EmptyState title="Aucun signalement" description="Aucun faux négatif n'a encore été signalé sur ce site." />
      {:else}
        <div class="overflow-x-auto">
          <table class="table table-zebra w-full">
            <thead>
              <tr>
                <th>Signalé le</th>
                <th>Espèce</th>
                <th>Heure approximative</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {#each reports as report (report.id)}
                <tr>
                  <td class="text-sm whitespace-nowrap">{formatInstant(report.reported_at)}</td>
                  <td>
                    <div class="font-medium">{report.common_name_fr ?? report.scientific_name}</div>
                    <div class="text-xs text-muted italic">{report.scientific_name}</div>
                    {#if !report.known_species}
                      <Badge variant="warning" size="xs" text="hors univers connu" />
                    {/if}
                  </td>
                  <td class="text-sm whitespace-nowrap">{formatInstant(report.approx_time_utc)}</td>
                  <td class="text-sm max-w-[20rem]">{report.notes ?? '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-between text-sm mt-3">
          <span class="text-muted">
            {formatCount(total, 'signalement')} — {offset + 1}–{Math.min(offset + PAGE_SIZE, total)}
          </span>
          <div class="flex gap-2">
            <Button variant="default" size="sm" disabled={offset === 0} onclick={() => goToPage(-1)}>Précédent</Button>
            <Button variant="default" size="sm" disabled={offset + PAGE_SIZE >= total} onclick={() => goToPage(1)}>
              Suivant
            </Button>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>
