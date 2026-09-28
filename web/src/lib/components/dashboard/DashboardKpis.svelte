<script lang="ts">
  // Composant neuf (équipe Tableau de bord). Petite ligne de KPIs sous le titre
  // (contrat §6.14, GET /sites/{slug}/stats/kpis). Optionnelle par nature (demande d'Armand :
  // « si tu la juges utile ») : une erreur ici reste locale et ne bloque jamais le reste du
  // tableau de bord (bloc « en écoute » + calendrier restent indépendants).
  import { getStatsKpis, ApiRequestError } from '../../api/client';
  import type { KpisResponse } from '../../api/types';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import { formatCount, formatLocalDate, formatNumber, pluralize } from '../../format';

  interface Props {
    slug: string;
  }

  let { slug }: Props = $props();

  let kpis = $state<KpisResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  $effect(() => {
    const currentSlug = slug;
    let cancelled = false;
    loading = true;
    error = null;
    kpis = null;

    getStatsKpis(currentSlug)
      .then((result) => {
        if (!cancelled) kpis = result;
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des indicateurs.';
      })
      .finally(() => {
        if (!cancelled) loading = false;
      });

    return () => {
      cancelled = true;
    };
  });

  interface Tile {
    label: string;
    value: string;
    /** Précision sous la valeur (ex. date du meilleur jour) : jamais tronquée. */
    hint?: string;
  }

  // Valeurs courtes (un nombre) + précision sur une seconde ligne : à 375 px de large, une
  // tuile fait ~150 px et « 2678 le 2026-09-27 » y était tronqué en « 2678 le 2026-… ».
  let tiles = $derived<Tile[]>(
    kpis
      ? [
          { label: 'Espèces (total)', value: formatNumber(kpis.lifetime_species) },
          { label: 'Détections (total)', value: formatNumber(kpis.lifetime_detections) },
          {
            label: "Aujourd'hui",
            value: formatNumber(kpis.today_detections),
            hint: `${pluralize(kpis.today_detections, 'détection')} · ${formatCount(kpis.today_species, 'espèce')}`,
          },
          {
            label: 'Meilleur jour',
            value: kpis.best_day ? formatNumber(kpis.best_day.count) : '—',
            hint: kpis.best_day
              ? `${pluralize(kpis.best_day.count, 'détection')} le ${formatLocalDate(kpis.best_day.date)}`
              : undefined,
          },
          { label: 'Série en cours', value: formatCount(kpis.streak_days, 'jour') },
        ]
      : []
  );
</script>

{#if loading}
  <div class="flex items-center gap-2 text-sm text-muted">
    <LoadingSpinner size="xs" label="Chargement des indicateurs…" />
    Chargement des indicateurs…
  </div>
{:else if error}
  <p class="text-sm text-muted" role="alert">Indicateurs indisponibles : {error}</p>
{:else if kpis}
  <div class="grid grid-cols-2 xs:grid-cols-3 md:grid-cols-5 gap-2">
    {#each tiles as tile (tile.label)}
      <div class="rounded-lg bg-[var(--color-base-100)] shadow-xs px-3 py-2">
        <div class="text-xs text-muted">{tile.label}</div>
        <div class="text-lg font-semibold leading-snug break-words">{tile.value}</div>
        {#if tile.hint}
          <div class="text-xs text-muted">{tile.hint}</div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
