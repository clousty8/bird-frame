<script lang="ts">
  // Propriété de l'équipe « Espèces ». Voir web/README.md.
  //
  // Liste (/species) : par défaut les espèces DÉTECTÉES sur le site courant
  // (GET /sites/{slug}/species, contrat §6.7), avec recherche texte et tri ; bascule
  // « Toutes les espèces de France (368) » vers GET /species?site= (contrat §6.8), avec
  // indication déjà détectée ici / ailleurs / jamais.
  import { onMount } from 'svelte';
  import { siteStore } from '../lib/stores/site.svelte';
  import { getSiteSpecies, getSpeciesList, ApiRequestError } from '../lib/api/client';
  import type { SiteSpecies, UniverseSpecies } from '../lib/api/types';
  import SpeciesCard from '../lib/components/species/SpeciesCard.svelte';
  import LoadingSpinner from '../lib/components/ui/LoadingSpinner.svelte';
  import ErrorAlert from '../lib/components/ui/ErrorAlert.svelte';
  import EmptyState from '../lib/components/ui/EmptyState.svelte';
  import { matchesQuery } from '../lib/components/species/normalize';
  import type { SpeciesCardBadge } from '../lib/components/species/types';
  import { formatCount, formatNumber } from '../lib/format';

  type SiteSort = 'total' | 'last_seen' | 'common_name';
  type UniverseSort = 'common_name' | 'france_max_score' | 'detections';

  // Décision hors contrat (le contrat est muet sur la recherche texte de la vue « site
  // courant ») : recherche client-side dans ce mode ; en mode univers France, la recherche
  // passe par le paramètre `q` de GET /species (contrat §6.8), débattue pour éviter une
  // requête par frappe.
  const UNIVERSE_SEARCH_DEBOUNCE_MS = 250;

  let showAllFrance = $state(false);
  let query = $state('');
  let siteSort = $state<SiteSort>('total');
  let universeSort = $state<UniverseSort>('common_name');

  let siteSpecies = $state<SiteSpecies[]>([]);
  let universeSpecies = $state<UniverseSpecies[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);

  onMount(() => {
    void siteStore.load();
  });

  let debounceHandle: ReturnType<typeof setTimeout> | undefined;

  // Jetons de requête (même remède que StatsPage.svelte) : un changement rapide de site, de
  // tri ou de recherche relance un fetch sans annuler le précédent ; sans ça, la réponse la
  // plus lente à revenir écrase l'affichage même si elle ne correspond plus au site/tri/
  // recherche courants.
  let siteSpeciesRequestId = 0;
  let universeSpeciesRequestId = 0;

  async function loadSiteSpecies(slug: string, sort: SiteSort): Promise<void> {
    const requestId = ++siteSpeciesRequestId;
    error = null;
    try {
      const response = await getSiteSpecies(slug, { sort });
      if (requestId !== siteSpeciesRequestId) return;
      siteSpecies = response.species;
    } catch (err) {
      if (requestId !== siteSpeciesRequestId) return;
      error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des espèces.';
      siteSpecies = [];
    } finally {
      if (requestId === siteSpeciesRequestId) loading = false;
    }
  }

  async function loadUniverseSpecies(slug: string | null, q: string, sort: UniverseSort): Promise<void> {
    const requestId = ++universeSpeciesRequestId;
    error = null;
    try {
      const response = await getSpeciesList({ site: slug ?? undefined, q: q.trim() || undefined, sort, limit: 500 });
      if (requestId !== universeSpeciesRequestId) return;
      universeSpecies = response.species;
    } catch (err) {
      if (requestId !== universeSpeciesRequestId) return;
      error = err instanceof ApiRequestError ? err.message : "Erreur inconnue lors du chargement de l'univers France.";
      universeSpecies = [];
    } finally {
      if (requestId === universeSpeciesRequestId) loading = false;
    }
  }

  $effect(() => {
    const slug = siteStore.selectedSlug;
    if (!slug) return;

    if (showAllFrance) {
      const currentQuery = query;
      const currentSort = universeSort;
      loading = true;
      clearTimeout(debounceHandle);
      debounceHandle = setTimeout(() => void loadUniverseSpecies(slug, currentQuery, currentSort), UNIVERSE_SEARCH_DEBOUNCE_MS);
    } else {
      loading = true;
      void loadSiteSpecies(slug, siteSort);
    }

    return () => clearTimeout(debounceHandle);
  });

  let filteredSiteSpecies = $derived(siteSpecies.filter((s) => matchesQuery(query, s.common_name_fr, s.scientific_name)));

  function ruleBadge(rule: SiteSpecies['rule'], redirectTo: string | null): SpeciesCardBadge[] {
    if (rule === 'present') return [{ text: 'Présente ici', variant: 'success' }];
    if (rule === 'impossible') return [{ text: 'Impossible ici', variant: 'error' }];
    if (rule === 'redirect') return [{ text: `Redirigée${redirectTo ? ' → ' + redirectTo : ''}`, variant: 'warning' }];
    return [];
  }

  function universeBadge(species: UniverseSpecies): SpeciesCardBadge[] {
    if (siteStore.selectedSlug && species.site_total !== null && species.site_total > 0) {
      return [{ text: 'Déjà détectée ici', variant: 'success' }];
    }
    if (species.total_detections > 0) {
      return [{ text: 'Détectée ailleurs', variant: 'info' }];
    }
    return [{ text: 'Jamais détectée', variant: 'neutral' }];
  }

  function formatDateTime(iso: string): string {
    try {
      return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });
    } catch {
      return iso;
    }
  }
</script>

<div class="flex flex-col gap-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-2xl font-semibold">Espèces</h1>
    <label class="flex items-center gap-2 text-sm">
      <input type="checkbox" class="checkbox checkbox-sm" bind:checked={showAllFrance} />
      Toutes les espèces de France (368)
    </label>
  </div>

  <div class="flex flex-wrap gap-3">
    <input
      type="search"
      class="input flex-1 min-w-[200px]"
      placeholder="Rechercher une espèce…"
      bind:value={query}
      aria-label="Rechercher une espèce"
    />
    {#if showAllFrance}
      <select class="select" bind:value={universeSort} aria-label="Trier par">
        <option value="common_name">Alphabétique</option>
        <option value="france_max_score">Score France</option>
        <option value="detections">Détections</option>
      </select>
    {:else}
      <select class="select" bind:value={siteSort} aria-label="Trier par">
        <option value="total">Total</option>
        <option value="last_seen">Récence</option>
        <option value="common_name">Alphabétique</option>
      </select>
    {/if}
  </div>

  {#if !siteStore.selectedSlug}
    <EmptyState title="Aucun site sélectionné" description="Choisissez un site pour voir ses espèces détectées." />
  {:else if loading}
    <LoadingSpinner label="Chargement des espèces…" />
  {:else if error}
    <ErrorAlert message={error} />
  {:else if showAllFrance}
    {#if universeSpecies.length === 0}
      <EmptyState title="Aucune espèce trouvée" description="Essayez une autre recherche." />
    {:else}
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {#each universeSpecies as species (species.scientific_name)}
          <SpeciesCard
            scientificName={species.scientific_name}
            commonNameFr={species.common_name_fr}
            photoUrl={species.photo_url}
            statLine={species.site_total !== null
              ? `${formatCount(species.site_total, 'détection')} ici · ${formatNumber(species.total_detections)} en France`
              : `${formatCount(species.total_detections, 'détection')} en France`}
            badges={universeBadge(species)}
          />
        {/each}
      </div>
    {/if}
  {:else if filteredSiteSpecies.length === 0}
    <EmptyState
      title="Aucune espèce trouvée"
      description="Essayez une autre recherche, ou basculez sur « Toutes les espèces de France »."
    />
  {:else}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each filteredSiteSpecies as species (species.scientific_name)}
        <SpeciesCard
          scientificName={species.scientific_name}
          commonNameFr={species.common_name_fr}
          photoUrl={species.photo_url}
          statLine={`${formatCount(species.total, 'détection')} · dernière le ${formatDateTime(species.last_seen_utc)}`}
          badges={ruleBadge(species.rule, species.redirect_to_scientific_name)}
        />
      {/each}
    </div>
  {/if}
</div>
