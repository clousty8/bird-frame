<script lang="ts">
  // Composant neuf (équipe Tableau de bord, WP-05). GET /sites/{slug}/calendar (contrat §6.5) :
  // toutes les espèces du jour, sans limite (scroll si besoin), grille espèce × 24 heures.
  // S'inspire visuellement de birdnet-go-ui/frontend/.../DailySummaryCard.svelte (lecture
  // seule, contrat de données différent : composant neuf, pas une copie, cf. docs/plan.md WP-05).
  import { getCalendar, ApiRequestError } from '../../api/client';
  import type { CalendarResponse } from '../../api/types';
  import { speciesDetailPath } from '../../router';
  import Card from '../ui/Card.svelte';
  import Badge from '../ui/Badge.svelte';
  import Button from '../ui/Button.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import SpeciesPhoto from '../SpeciesPhoto.svelte';
  import Link from '../../Link.svelte';
  import { formatCount } from '../../format';

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
    <div class="max-h-[32rem] overflow-y-auto flex flex-col gap-2" aria-label="Activité par espèce et par heure">
      {#each response.species as row (row.scientific_name)}
        {@const peak = maxHourCount(row.hours)}
        <!-- Mobile : nom + total sur une ligne, grille des 24 heures pleine largeur dessous
             (à 360 px, côte à côte, chaque case faisait moins d'un pixel). -->
        <div
          class="flex flex-wrap sm:flex-nowrap items-center gap-x-3 gap-y-1.5 py-1.5 border-b border-[var(--border-100)] last:border-b-0"
        >
          <Link
            to={speciesDetailPath(row.scientific_name)}
            class="flex items-center gap-2 flex-1 sm:flex-none sm:w-48 sm:shrink-0 min-w-0 hover:opacity-80"
          >
            <SpeciesPhoto
              src={row.photo_url}
              alt={row.common_name_fr ?? row.scientific_name}
              size={36}
              class="w-9 h-9 rounded-md object-cover shrink-0"
            />
            <span class="min-w-0">
              <span class="block text-sm font-medium truncate">{row.common_name_fr ?? row.scientific_name}</span>
              <span class="block text-xs text-muted">
                {row.total} · max {Math.round(row.max_confidence * 100)}%
              </span>
            </span>
          </Link>

          <div class="grid grid-cols-24 gap-0.5 order-last sm:order-none basis-full sm:basis-0 sm:flex-1 min-w-0">
            {#each row.hours as count, hour (hour)}
              {@const intensity = peak > 0 ? count / peak : 0}
              <div
                class="aspect-square rounded-sm"
                style="background-color: {count === 0
                  ? 'var(--color-base-200)'
                  : `color-mix(in srgb, var(--color-primary) ${Math.round(10 + intensity * 90)}%, var(--color-base-200))`}"
                title="{hour}h : {formatCount(count, 'détection')}"
              ></div>
            {/each}
          </div>

          <Badge variant="neutral" size="sm" class="shrink-0" text={String(row.total)} />
        </div>
      {/each}
    </div>
  {/if}
</Card>
