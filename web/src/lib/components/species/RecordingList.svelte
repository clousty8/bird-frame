<script lang="ts">
  // Section « Meilleurs enregistrements » : jusqu'à 5 enregistrements du site sélectionné
  // pour cette section (contrat §6.11 : GET /species/{name}/sites/{slug}/top-clips),
  // avec possibilité de changer de site sans changer le site global du dashboard.
  import { untrack } from 'svelte';
  import { siteStore } from '../../stores/site.svelte';
  import { getTopClips, ApiRequestError } from '../../api/client';
  import type { TopClip } from '../../api/types';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import RecordingItem from './RecordingItem.svelte';

  interface Props {
    scientificName: string;
  }

  let { scientificName }: Props = $props();

  let siteSlug = $state<string | null>(untrack(() => siteStore.selectedSlug));
  let clips = $state<TopClip[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);

  // Tant que l'utilisateur n'a pas choisi explicitement un autre site pour cette section,
  // elle suit le site global (utile le temps que siteStore.load() se termine).
  let followsGlobalSite = $state(true);

  $effect(() => {
    const globalSlug = siteStore.selectedSlug;
    if (followsGlobalSite && globalSlug) siteSlug = globalSlug;
  });

  // Jeton de requête (même remède que StatsPage.svelte) : une navigation rapide entre fiches
  // espèce (ou un changement de site pour cette section) peut faire répondre un appel plus
  // ancien après un plus récent ; sans garde, la section affiche l'audio/spectrogramme d'une
  // autre espèce sous le titre de la nouvelle.
  let loadRequestId = 0;

  async function load(name: string, slug: string): Promise<void> {
    const requestId = ++loadRequestId;
    loading = true;
    error = null;
    try {
      const response = await getTopClips(name, slug);
      if (requestId !== loadRequestId) return;
      clips = response.clips;
    } catch (err) {
      if (requestId !== loadRequestId) return;
      error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des enregistrements.';
      clips = [];
    } finally {
      if (requestId === loadRequestId) loading = false;
    }
  }

  $effect(() => {
    const slug = siteSlug;
    const name = scientificName;
    if (!slug) return;
    void load(name, slug);
  });

  function handleSiteChange(event: Event): void {
    followsGlobalSite = false;
    siteSlug = (event.target as HTMLSelectElement).value;
  }
</script>

<section class="flex flex-col gap-3">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <h2 class="text-xl font-semibold">Meilleurs enregistrements</h2>
    {#if siteStore.sites.length > 1}
      <label class="flex items-center gap-2 text-sm">
        Site
        <select class="select select-sm" value={siteSlug ?? ''} onchange={handleSiteChange} aria-label="Site des enregistrements">
          {#each siteStore.sites as site (site.slug)}
            <option value={site.slug}>{site.name}</option>
          {/each}
        </select>
      </label>
    {/if}
  </div>

  {#if !siteSlug}
    <EmptyState title="Aucun site sélectionné" description="Choisissez un site pour voir ses enregistrements." />
  {:else if loading}
    <LoadingSpinner label="Chargement des enregistrements…" />
  {:else if error}
    <ErrorAlert message={error} />
  {:else if clips.length === 0}
    <EmptyState title="Aucun enregistrement" description="Pas encore d'enregistrement conservé pour cette espèce sur ce site." />
  {:else}
    <div class="flex flex-col gap-3">
      {#each clips as clip (clip.kept_clip_id)}
        <RecordingItem {clip} />
      {/each}
    </div>
  {/if}
</section>
