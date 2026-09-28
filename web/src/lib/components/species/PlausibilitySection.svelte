<script lang="ts">
  // Section « Plausibilité ici » : france_universe présenté comme aide au jugement d'une
  // fausse détection (score max, mois où l'espèce passe le filtre de zone BirdNET, score de
  // la ville la plus proche du site si déductible). Le contrat ne précise pas de
  // correspondance formelle site → clé de `france_universe.cities` : rapprochement simple
  // par nom de ville (insensible à la casse), en secours seulement — décision hors contrat.
  import type { FranceUniverse } from '../../api/types';
  import { siteStore } from '../../stores/site.svelte';

  interface Props {
    franceUniverse: FranceUniverse | null;
  }

  let { franceUniverse }: Props = $props();

  const MONTH_NAMES = [
    'janvier',
    'février',
    'mars',
    'avril',
    'mai',
    'juin',
    'juillet',
    'août',
    'septembre',
    'octobre',
    'novembre',
    'décembre',
  ];

  let nearestCityScore = $derived.by((): { city: string; score: number } | null => {
    if (!franceUniverse) return null;
    const siteName = siteStore.selectedSite?.name;
    if (!siteName) return null;
    const normalizedSiteName = siteName.toLowerCase();
    for (const [city, score] of Object.entries(franceUniverse.cities)) {
      if (city.toLowerCase() === normalizedSiteName) return { city, score };
    }
    return null;
  });
</script>

<section class="flex flex-col gap-3">
  <h2 class="text-xl font-semibold">Plausibilité ici</h2>
  <p class="text-sm text-muted">
    Aide au jugement d'une détection possiblement erronée : une espèce absente du filtre de
    zone à cette période, ou avec un score très faible ici, est plus susceptible d'être une
    fausse détection que de refléter une vraie présence.
  </p>

  {#if !franceUniverse}
    <p class="text-muted italic text-sm">Aucune donnée de plausibilité disponible pour cette espèce.</p>
  {:else}
    <div class="flex flex-wrap gap-x-6 gap-y-1 text-sm">
      <div><span class="font-medium">Score maximal (France)</span> : {(franceUniverse.max_score * 100).toFixed(1)} %</div>
      {#if nearestCityScore}
        <div><span class="font-medium">Score à {nearestCityScore.city}</span> : {(nearestCityScore.score * 100).toFixed(1)} %</div>
      {/if}
    </div>
    <div>
      <p class="text-sm font-medium mb-1">Mois où l'espèce passe le filtre de zone</p>
      {#if franceUniverse.months.length === 0}
        <p class="text-muted italic text-sm">Aucun mois recensé.</p>
      {:else}
        <div class="flex flex-wrap gap-1.5">
          {#each franceUniverse.months as month (month)}
            <span class="badge-status-info px-2 py-0.5 rounded-full text-xs">{MONTH_NAMES[month - 1] ?? month}</span>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</section>
