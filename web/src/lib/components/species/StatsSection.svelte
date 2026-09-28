<script lang="ts">
  // Section « Statistiques » : répartition par heure et par mois (contrat §6.12,
  // GET /species/{name}/presence?site=), sur le site actuellement sélectionné dans le
  // sélecteur global.
  import { siteStore } from '../../stores/site.svelte';
  import { getSpeciesPresence, ApiRequestError } from '../../api/client';
  import type { PresenceResponse } from '../../api/types';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import MiniBarChart from './MiniBarChart.svelte';
  import { MONTH_AXIS_LABELS, MONTH_NAMES } from './months';

  interface Props {
    scientificName: string;
  }

  let { scientificName }: Props = $props();

  let presence = $state<PresenceResponse | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);

  // Jeton de requête (même remède que StatsPage.svelte) : un changement d'espèce ou de site
  // pendant qu'une requête de présence est encore en vol peut faire répondre un appel plus
  // ancien après un plus récent ; sans garde, cette section affiche les données d'une autre
  // espèce/site que le reste de la page.
  let loadRequestId = 0;

  async function load(name: string, site: string | null): Promise<void> {
    const requestId = ++loadRequestId;
    loading = true;
    error = null;
    try {
      const data = await getSpeciesPresence(name, { site: site ?? undefined });
      if (requestId !== loadRequestId) return;
      presence = data;
    } catch (err) {
      if (requestId !== loadRequestId) return;
      error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des statistiques.';
      presence = null;
    } finally {
      if (requestId === loadRequestId) loading = false;
    }
  }

  $effect(() => {
    void load(scientificName, siteStore.selectedSlug);
  });

  // Une étiquette toutes les 4 heures sous le graphique horaire (24 barres).
  const HOUR_AXIS_LABELS = Array.from({ length: 24 }, (_, hour) => (hour % 4 === 0 ? `${hour}h` : null));
</script>

<section id="statistiques" class="wiki-section flex flex-col gap-3">
  <h2 class="wiki-h2">Statistiques</h2>

  {#if loading}
    <LoadingSpinner label="Chargement des statistiques…" />
  {:else if error}
    <ErrorAlert message={error} />
  {:else if !presence || presence.total === 0}
    <p class="text-muted italic text-sm">
      Aucune détection pour cette espèce{siteStore.selectedSlug ? ' sur ce site' : ''}.
    </p>
  {:else}
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="rounded-lg bg-[var(--color-base-100)] p-4 shadow-sm min-w-0">
        <h3 class="font-medium mb-2">Par mois</h3>
        <MiniBarChart
          values={presence.months}
          axisLabels={MONTH_AXIS_LABELS}
          barLabel={(index) => MONTH_NAMES[index] ?? ''}
          colorVar="--color-accent"
          ariaLabel="Détections par mois"
          heightPx={80}
        />
      </div>
      <div class="rounded-lg bg-[var(--color-base-100)] p-4 shadow-sm min-w-0">
        <h3 class="font-medium mb-2">Par heure</h3>
        <MiniBarChart
          values={presence.hours}
          axisLabels={HOUR_AXIS_LABELS}
          barLabel={(index) => `${index}h`}
          colorVar="--color-secondary"
          ariaLabel="Détections par heure locale"
          heightPx={80}
        />
      </div>
    </div>
  {/if}
</section>
