<script lang="ts">
  // Section « Détections par lieu » : un bloc par site, barres par mois sur 12, total, première/
  // dernière fois — c'est là qu'on voit Le Mans vs Pornic. Les données viennent déjà
  // groupées par site dans SpeciesDetail.presence_by_site (contrat §6.9) : pas d'appel
  // réseau supplémentaire ici.
  import type { PresenceBySite } from '../../api/types';
  import MiniBarChart from './MiniBarChart.svelte';
  import { MONTH_AXIS_LABELS, MONTH_NAMES } from './months';
  import { formatCount } from '../../format';

  interface Props {
    presenceBySite: PresenceBySite[];
  }

  let { presenceBySite }: Props = $props();

  function formatDate(iso: string | null): string {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
      return iso;
    }
  }
</script>

<section id="detections" class="wiki-section flex flex-col gap-3">
  <h2 class="wiki-h2">Détections par lieu</h2>
  {#if presenceBySite.length === 0}
    <p class="text-muted text-sm">L'appareil n'a encore jamais entendu cet oiseau, sur aucun lieu suivi.</p>
  {:else}
    <div class="grid gap-4 sm:grid-cols-2">
      {#each presenceBySite as site (site.site_slug)}
        <div class="rounded-lg bg-[var(--color-base-100)] p-4 shadow-sm">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="font-medium">{site.site_name}</h3>
            <span class="text-sm text-muted">{formatCount(site.total, 'détection')}</span>
          </div>
          <p class="text-xs text-muted mt-0.5">
            Du {formatDate(site.first_seen_utc)} au {formatDate(site.last_seen_utc)} · {formatCount(site.days_seen, 'jour')}
          </p>
          <div class="mt-3">
            <MiniBarChart
              values={site.months}
              axisLabels={MONTH_AXIS_LABELS}
              barLabel={(index) => MONTH_NAMES[index] ?? ''}
              colorVar="--color-primary"
              ariaLabel="Détections par mois à {site.site_name}"
            />
          </div>
        </div>
      {/each}
    </div>
  {/if}
</section>
