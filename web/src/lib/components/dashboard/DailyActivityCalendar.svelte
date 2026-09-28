<script lang="ts">
  // Composant neuf (équipe Tableau de bord, WP-05). GET /sites/{slug}/calendar (contrat §6.5) :
  // toutes les espèces du jour, sans limite (scroll si besoin), grille espèce × 24 heures.
  // S'inspire visuellement de birdnet-go-ui/frontend/.../DailySummaryCard.svelte (lecture
  // seule, contrat de données différent : composant neuf, pas une copie, cf. docs/plan.md WP-05).
  // v0.2 : chaque case non vide affiche son nombre de détections (comme BirdNET-Go), en plus
  // du code couleur (5 paliers relatifs au maximum de l'espèce, couleurs de texte choisies
  // pour un contraste ≥ 4,7:1 dans les deux thèmes, heatmap.ts). Tableau défilant à
  // l'horizontale sur mobile, noms d'espèces figés à gauche.
  import { tick } from 'svelte';
  import { getCalendar, ApiRequestError } from '../../api/client';
  import type { CalendarResponse } from '../../api/types';
  import { speciesDetailPath } from '../../router';
  import Card from '../ui/Card.svelte';
  import Button from '../ui/Button.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import SpeciesPhoto from '../SpeciesPhoto.svelte';
  import Link from '../../Link.svelte';
  import { formatCount } from '../../format';
  import { firstActiveHour, heatLevel, HOURS } from './heatmap';

  interface Props {
    /** Slug du site courant (contrat §1.5). Changer de site recharge le calendrier. */
    slug: string;
  }

  let { slug }: Props = $props();

  let response = $state<CalendarResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  /** Décale une date locale ("YYYY-MM-DD") de `days` jours, en arithmétique UTC pure (évite
   *  tout souci de DST : on ne manipule jamais l'heure, seulement le calendrier). */
  function shiftLocalDate(iso: string, days: number): string {
    const parts = iso.split('-');
    const year = Number(parts[0] ?? '0');
    const month = Number(parts[1] ?? '1');
    const day = Number(parts[2] ?? '1');
    const date = new Date(Date.UTC(year, month - 1, day));
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  }

  function formatLocalTimeOfDay(utcInstant: string, timezone: string): string | null {
    try {
      return new Intl.DateTimeFormat('fr-FR', { timeZone: timezone, hour: '2-digit', minute: '2-digit' }).format(
        new Date(utcInstant)
      );
    } catch {
      // Fuseau inconnu/mal formé côté site : jamais bloquant, on masque juste le repère.
      return null;
    }
  }

  function formatLocalDateLabel(iso: string): string {
    const parts = iso.split('-');
    const year = Number(parts[0] ?? '0');
    const month = Number(parts[1] ?? '1');
    const day = Number(parts[2] ?? '1');
    return new Intl.DateTimeFormat('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      timeZone: 'UTC',
    }).format(new Date(Date.UTC(year, month - 1, day)));
  }

  // Jeton de requête (même remède que StatsPage.svelte) : boutons Veille/Lendemain/date, et
  // changement de site, peuvent relancer `load` alors qu'un appel précédent est encore en
  // vol ; sans garde, l'ordre réseau (pas garanti) fait gagner la réponse la plus lente à
  // arriver plutôt que la plus récemment demandée.
  let loadRequestId = 0;

  /** Charge un jour donné, ou le jour par défaut du serveur (aujourd'hui côté site) si `targetDate` est omis. */
  async function load(targetDate?: string): Promise<void> {
    const requestId = ++loadRequestId;
    loading = true;
    error = null;
    try {
      const data = await getCalendar(slug, { date: targetDate });
      if (requestId !== loadRequestId) return;
      response = data;
    } catch (err) {
      if (requestId !== loadRequestId) return;
      error =
        err instanceof ApiRequestError
          ? err.message
          : "Erreur inconnue lors du chargement du calendrier d'activité.";
    } finally {
      if (requestId === loadRequestId) loading = false;
    }
  }

  // Changement de site : on repart du jour par défaut du nouveau site (pas de report d'une
  // date qui n'aurait plus de sens dans un autre fuseau).
  $effect(() => {
    void slug;
    void load(undefined);
  });

  function goToPreviousDay(): void {
    if (response) void load(shiftLocalDate(response.date, -1));
  }
  function goToNextDay(): void {
    if (response) void load(shiftLocalDate(response.date, 1));
  }
  function goToToday(): void {
    void load(undefined);
  }
  function onDateInputChange(event: Event): void {
    const value = (event.currentTarget as HTMLInputElement).value;
    if (value) void load(value);
  }

  function maxHourCount(hours: number[]): number {
    return Math.max(0, ...hours);
  }

  // Sur petit écran la grille défile à l'horizontale : on l'amène d'emblée sur la première
  // heure active à partir de 4 h (sinon on ne voit que la nuit, souvent vide ; les cris
  // nocturnes restent accessibles en faisant défiler vers la gauche).
  let scroller = $state<HTMLDivElement | null>(null);

  $effect(() => {
    const data = response;
    const element = scroller;
    if (!data || !element) return;
    const hour = firstActiveHour(
      data.species.map((row) => row.hours),
      4
    );
    void tick().then(() => {
      const target = element.querySelector<HTMLElement>(`th[data-hour="${Math.max(0, hour - 1)}"]`);
      const sticky = element.querySelector<HTMLElement>('th.species-col');
      if (!target || !sticky) return;
      element.scrollLeft = Math.max(0, target.offsetLeft - sticky.offsetWidth);
    });
  });
</script>

<Card>
  {#snippet header()}
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <div>
        <h2 class="text-lg font-semibold">Activité quotidienne</h2>
        {#if response}
          <p class="text-sm text-muted first-letter:uppercase">
            {formatLocalDateLabel(response.date)} · {formatCount(response.total_detections, 'détection')}
            {#if response.sunrise_utc || response.sunset_utc}
              {@const sunrise = response.sunrise_utc ? formatLocalTimeOfDay(response.sunrise_utc, response.timezone) : null}
              {@const sunset = response.sunset_utc ? formatLocalTimeOfDay(response.sunset_utc, response.timezone) : null}
              {#if sunrise || sunset}
                · Lever {sunrise ?? '—'} · Coucher {sunset ?? '—'}
              {/if}
            {/if}
          </p>
        {/if}
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <Button variant="ghost" size="sm" class="whitespace-nowrap" onclick={goToPreviousDay} title="Jour précédent">← Veille</Button>
        <input
          type="date"
          class="input input-sm w-[10.5rem]"
          value={response?.date ?? ''}
          onchange={onDateInputChange}
          aria-label="Choisir une date"
        />
        <Button variant="ghost" size="sm" class="whitespace-nowrap" onclick={goToNextDay} title="Jour suivant">Lendemain →</Button>
        <Button variant="default" size="sm" class="whitespace-nowrap" onclick={goToToday}>Aujourd'hui</Button>
      </div>
    </div>
  {/snippet}

  {#if loading}
    <LoadingSpinner label="Chargement du calendrier d'activité…" size="md" />
  {:else if error}
    <ErrorAlert>
      {error}
      <Button variant="ghost" size="xs" class="ml-2" onclick={() => void load(response?.date)}>Réessayer</Button>
    </ErrorAlert>
  {:else if !response || response.species.length === 0}
    <EmptyState title="Aucune détection ce jour-là" description="Aucune espèce détectée pour la date sélectionnée." />
  {:else}
    <!-- Tableau espèce × heure : défile dans les deux sens, en-tête des heures et colonne des
         espèces figés. Chaque case non vide affiche son nombre de détections. -->
    <div
      class="calendar-scroll"
      bind:this={scroller}
      role="region"
      aria-label="Activité par espèce et par heure"
      tabindex="-1"
    >
      <table class="calendar-table">
        <thead>
          <tr>
            <th scope="col" class="species-col corner"><span class="sr-only">Espèce</span></th>
            {#each HOURS as hour (hour)}
              <th scope="col" class="hour-head" data-hour={hour}><span class="sr-only">{hour} h</span><span aria-hidden="true">{hour}</span></th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each response.species as row (row.scientific_name)}
            {@const peak = maxHourCount(row.hours)}
            <tr>
              <th scope="row" class="species-col">
                <Link to={speciesDetailPath(row.scientific_name)} class="species-link hover:opacity-80">
                  <SpeciesPhoto
                    src={row.photo_url}
                    alt={row.common_name_fr ?? row.scientific_name}
                    size={36}
                    class="hidden sm:block w-8 h-8 rounded-md object-cover shrink-0"
                  />
                  <span class="min-w-0">
                    <span class="species-name">{row.common_name_fr ?? row.scientific_name}</span>
                    <span class="block text-xs text-muted font-normal">
                      {row.total} · max {Math.round(row.max_confidence * 100)}%
                    </span>
                  </span>
                </Link>
              </th>
              {#each row.hours as count, hour (hour)}
                <td class="hour-cell heat-{heatLevel(count, peak)}" title="{hour}h : {formatCount(count, 'détection')}">
                  {count > 0 ? count : ''}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</Card>

<style>
  .calendar-scroll {
    max-height: 32rem;
    overflow: auto;
    overscroll-behavior-x: contain;
  }

  .calendar-table {
    width: 100%;
    min-width: calc(7.25rem + 24 * 1.875rem);
    table-layout: fixed;
    border-collapse: separate;
    border-spacing: 2px;
  }

  @media (min-width: 640px) {
    .calendar-table {
      min-width: calc(13rem + 24 * 1.875rem);
    }
  }

  /* Colonne des espèces figée à gauche, fond opaque (les cases défilent dessous). */
  .species-col {
    position: sticky;
    left: 0;
    z-index: 1;
    width: 7.25rem;
    padding: 0.25rem 0.5rem 0.25rem 0;
    text-align: left;
    font-weight: 500;
    background-color: var(--color-base-100);
  }

  @media (min-width: 640px) {
    .species-col {
      width: 13rem;
    }
  }

  thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background-color: var(--color-base-100);
  }

  thead .corner {
    z-index: 2;
  }

  .hour-head {
    padding: 0.125rem 0 0.25rem;
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--text-muted);
    text-align: center;
    font-variant-numeric: tabular-nums;
  }

  :global(.species-link) {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  .species-name {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    font-size: 0.8125rem;
    line-height: 1.2;
    overflow-wrap: anywhere;
  }

  @media (min-width: 640px) {
    .species-name {
      font-size: 0.875rem;
    }
  }

  .hour-cell {
    height: 2rem;
    padding: 0;
    border-radius: 0.1875rem;
    text-align: center;
    vertical-align: middle;
    font-size: 0.75rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  /* Paliers de couleur (relatifs au maximum horaire de l'espèce) et couleur du nombre :
     contraste texte/fond ≥ 4,7:1 dans les deux thèmes (voir heatmap.ts). */
  .heat-0 {
    background-color: var(--color-base-200);
  }
  .heat-1 {
    background-color: #e1e8f6;
    color: #1f2937;
  }
  .heat-2 {
    background-color: #c3d2f3;
    color: #1f2937;
  }
  .heat-3 {
    background-color: #a1baf2;
    color: #1f2937;
  }
  .heat-4 {
    background-color: #6f96ee;
    color: #111827;
  }
  .heat-5 {
    background-color: #2563eb;
    color: #ffffff;
  }

  :global([data-theme='dark']) .heat-0 {
    background-color: #020617;
  }
  :global([data-theme='dark']) .heat-1 {
    background-color: #0a1a45;
    color: #f1f5f9;
  }
  :global([data-theme='dark']) .heat-2 {
    background-color: #0f2a66;
    color: #f1f5f9;
  }
  :global([data-theme='dark']) .heat-3 {
    background-color: #143786;
    color: #f1f5f9;
  }
  :global([data-theme='dark']) .heat-4 {
    background-color: #1c4ab8;
    color: #f1f5f9;
  }
  :global([data-theme='dark']) .heat-5 {
    background-color: #2563eb;
    color: #f8fafc;
  }
</style>
