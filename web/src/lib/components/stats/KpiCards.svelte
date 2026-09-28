<script lang="ts">
  // Composant neuf. Quatre indicateurs clés (contrat §6.14 GET /stats/kpis) : espèces à vie,
  // détections aujourd'hui, meilleur jour, série de jours consécutifs. Simples tuiles HTML,
  // pas de D3 : ce sont des nombres, pas une visualisation.
  import type { KpisResponse } from '../../api/types';
  import { formatLocalDateFr, utcInstantToLocalDate } from './period';
  import { formatCount, formatNumber } from '../../format';

  interface Props {
    data: KpisResponse;
  }

  let { data }: Props = $props();

  interface Tile {
    label: string;
    value: string;
    hint?: string;
  }

  const tiles = $derived.by((): Tile[] => [
    { label: 'Espèces à vie', value: formatNumber(data.lifetime_species) },
    {
      label: "Détections aujourd'hui",
      value: formatNumber(data.today_detections),
      hint: formatCount(data.today_species, 'espèce'),
    },
    {
      label: 'Meilleur jour',
      value: data.best_day ? formatNumber(data.best_day.count) : '—',
      hint: data.best_day ? formatLocalDateFr(data.best_day.date) : 'Aucune détection',
    },
    {
      label: 'Jours consécutifs',
      value: formatNumber(data.streak_days),
      hint: data.streak_days > 0 ? 'avec au moins une détection' : 'aucune série en cours',
    },
  ]);
</script>

<div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
  {#each tiles as tile (tile.label)}
    <div class="rounded-lg bg-[var(--color-base-200)] p-4">
      <p class="text-xs text-muted uppercase tracking-wide">{tile.label}</p>
      <p class="text-2xl font-semibold mt-1">{tile.value}</p>
      {#if tile.hint}
        <p class="text-xs text-muted mt-1">{tile.hint}</p>
      {/if}
    </div>
  {/each}
</div>
<p class="text-xs text-muted mt-3">
  Depuis la première détection le {data.first_detection_utc
    ? formatLocalDateFr(utcInstantToLocalDate(data.first_detection_utc, data.timezone))
    : '—'}.
</p>
