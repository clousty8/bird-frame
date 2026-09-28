<script lang="ts">
  // Propriété de l'équipe « Espèces ». Voir web/README.md.
  // Route dédiée /species/:name, deep-linkable (architecture.md §8.2 : fiche espèce
  // partageable, pas une modale). Sections : en-tête (grande photo + taxonomie), présence
  // par site, meilleurs enregistrements, à propos (trivia rédactionnel), plausibilité ici
  // (france_universe), statistiques (heure/mois) — contrat §6.9.
  import { onMount } from 'svelte';
  import { siteStore } from '../lib/stores/site.svelte';
  import { getSpeciesDetail, ApiRequestError } from '../lib/api/client';
  import type { SpeciesDetail } from '../lib/api/types';
  import LoadingSpinner from '../lib/components/ui/LoadingSpinner.svelte';
  import ErrorAlert from '../lib/components/ui/ErrorAlert.svelte';
  import Badge from '../lib/components/ui/Badge.svelte';
  import RecordingList from '../lib/components/species/RecordingList.svelte';
  import PresenceBySiteSection from '../lib/components/species/PresenceBySiteSection.svelte';
  import AboutSection from '../lib/components/species/AboutSection.svelte';
  import PlausibilitySection from '../lib/components/species/PlausibilitySection.svelte';
  import StatsSection from '../lib/components/species/StatsSection.svelte';

  interface Props {
    scientificName: string;
  }

  let { scientificName }: Props = $props();

  let detail = $state<SpeciesDetail | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let photoFailed = $state(false);

  onMount(() => {
    void siteStore.load();
  });

  // Jeton de requête (même remède que StatsPage.svelte/CurrentlyHearingBlock.svelte) : un
  // clic rapide d'une espèce A vers une espèce B avant la résolution de la requête de A ne
  // doit pas laisser la réponse de A (si elle revient après celle de B) écraser la fiche de B.
  let loadRequestId = 0;

  async function load(name: string): Promise<void> {
    const requestId = ++loadRequestId;
    loading = true;
    error = null;
    detail = null;
    photoFailed = false;
    try {
      const data = await getSpeciesDetail(name);
      if (requestId !== loadRequestId) return;
      detail = data;
    } catch (err) {
      if (requestId !== loadRequestId) return;
      error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement de la fiche.';
    } finally {
      if (requestId === loadRequestId) loading = false;
    }
  }

  $effect(() => {
    void load(scientificName);
  });
</script>

{#if loading}
  <LoadingSpinner label="Chargement de la fiche…" />
{:else if error}
  <ErrorAlert message={error} />
{:else if detail}
  {@const currentDetail = detail}
  <article class="flex flex-col gap-8">
    <header class="flex flex-col gap-3">
      <div class="rounded-lg overflow-hidden bg-[var(--color-base-100)] aspect-video max-h-96 flex items-center justify-center">
        {#if currentDetail.photo && !photoFailed}
          <img
            src={currentDetail.photo.url_1600}
            alt={currentDetail.common_name_fr ?? currentDetail.scientific_name}
            class="w-full h-full object-cover"
            onerror={() => (photoFailed = true)}
          />
        {:else}
          <svg class="size-16 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <circle cx="8.5" cy="9.5" r="1.5" />
            <path d="M21 16l-5.5-5.5a1 1 0 0 0-1.4 0L6 19" />
          </svg>
        {/if}
      </div>
      {#if currentDetail.photo && !photoFailed && (currentDetail.photo.author || currentDetail.photo.license)}
        <p class="text-xs text-muted">
          Photo{currentDetail.photo.author ? ` : ${currentDetail.photo.author}` : ''}{currentDetail.photo.license
            ? ` — ${currentDetail.photo.license}`
            : ''}
        </p>
      {/if}

      <div class="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 class="text-2xl font-semibold">{currentDetail.common_name_fr ?? currentDetail.scientific_name}</h1>
          <p class="italic text-muted">{currentDetail.scientific_name}</p>
        </div>
        {#if currentDetail.has_sheet && !currentDetail.reviewed_by_human}
          <Badge variant="warning" text="Fiche générée par IA, à vérifier" />
        {/if}
      </div>

      {#if currentDetail.taxonomy}
        <div class="flex flex-wrap gap-1.5">
          {#if currentDetail.taxonomy.order}<Badge variant="neutral" outline text={currentDetail.taxonomy.order} />{/if}
          {#if currentDetail.taxonomy.family}<Badge variant="neutral" outline text={currentDetail.taxonomy.family} />{/if}
          {#if currentDetail.taxonomy.genus}<Badge variant="neutral" outline text={currentDetail.taxonomy.genus} />{/if}
        </div>
      {/if}
    </header>

    <PresenceBySiteSection presenceBySite={currentDetail.presence_by_site} />

    <RecordingList scientificName={currentDetail.scientific_name} />

    <AboutSection detail={currentDetail} />

    <PlausibilitySection franceUniverse={currentDetail.france_universe} />

    <StatsSection scientificName={currentDetail.scientific_name} />
  </article>
{/if}
