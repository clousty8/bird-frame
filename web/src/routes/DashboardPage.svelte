<script lang="ts">
  // Propriété de l'équipe « Tableau de bord » (WP-05/WP-06). Ordre imposé par Armand,
  // haut en bas : 1) « En écoute » (+ spectrogramme live déplié), 2) petite ligne de KPIs,
  // 3) « Activité quotidienne ». Tout réagit au changement de site du SiteSelector (store).
  import { siteStore } from '../lib/stores/site.svelte';
  import CurrentlyHearingBlock from '../lib/components/dashboard/CurrentlyHearingBlock.svelte';
  import DashboardKpis from '../lib/components/dashboard/DashboardKpis.svelte';
  import DailyActivityCalendar from '../lib/components/dashboard/DailyActivityCalendar.svelte';
  import LoadingSpinner from '../lib/components/ui/LoadingSpinner.svelte';
  import ErrorAlert from '../lib/components/ui/ErrorAlert.svelte';
  import EmptyState from '../lib/components/ui/EmptyState.svelte';
</script>

<div class="flex flex-col gap-4">
  <h1 class="text-2xl font-semibold">Tableau de bord</h1>

  {#if siteStore.selectedSlug}
    <DashboardKpis slug={siteStore.selectedSlug} />
    <CurrentlyHearingBlock slug={siteStore.selectedSlug} timezone={siteStore.selectedSite?.timezone} />
    <DailyActivityCalendar slug={siteStore.selectedSlug} />
  {:else if siteStore.loading}
    <LoadingSpinner label="Chargement des sites…" size="lg" />
  {:else if siteStore.error}
    <ErrorAlert message={siteStore.error} />
  {:else}
    <EmptyState
      title="Aucun site enregistré"
      description="Enregistrez un nœud (scripts/register_node.py) pour voir apparaître son tableau de bord ici."
    />
  {/if}
</div>
