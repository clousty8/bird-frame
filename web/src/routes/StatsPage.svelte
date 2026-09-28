<script lang="ts">
  // Propriété de l'équipe « Statistiques ». Voir web/README.md.
  //
  // Orchestre les 6 routes /sites/{slug}/stats/* du contrat (§6.14-6.19) : un sélecteur de
  // site (store partagé, pas de logique ici) + un sélecteur de période commun aux 4 premiers
  // graphiques, la heatmap ayant son propre sélecteur d'année (exigence du lot). Chaque
  // graphique gère son état chargement/erreur/vide indépendamment : l'échec d'une route ne
  // bloque jamais les autres.
  import { onMount, untrack } from 'svelte';
  import { siteStore } from '../lib/stores/site.svelte';
  import {
    getStatsKpis,
    getStatsDaily,
    getStatsHourly,
    getStatsSpeciesRanking,
    getStatsHeatmap,
    getStatsConfidence,
    ApiRequestError,
  } from '../lib/api/client';
  import type {
    KpisResponse,
    DailyResponse,
    HourlyResponse,
    SpeciesRankingResponse,
    HeatmapResponse,
    ConfidenceResponse,
  } from '../lib/api/types';
  import Card from '../lib/components/ui/Card.svelte';
  import LoadingSpinner from '../lib/components/ui/LoadingSpinner.svelte';
  import ErrorAlert from '../lib/components/ui/ErrorAlert.svelte';
  import EmptyState from '../lib/components/ui/EmptyState.svelte';
  import Button from '../lib/components/ui/Button.svelte';
  import PeriodControls from '../lib/components/stats/PeriodControls.svelte';
  import KpiCards from '../lib/components/stats/KpiCards.svelte';
  import DailyActivityChart from '../lib/components/stats/DailyActivityChart.svelte';
  import HourlyDistributionChart from '../lib/components/stats/HourlyDistributionChart.svelte';
  import SpeciesRankingChart from '../lib/components/stats/SpeciesRankingChart.svelte';
  import SeasonalHeatmap from '../lib/components/stats/SeasonalHeatmap.svelte';
  import ConfidenceHistogram from '../lib/components/stats/ConfidenceHistogram.svelte';
  import { presetToRange, utcInstantToLocalDate, type PeriodPreset, type DateRange } from '../lib/components/stats/period';

  const SPECIES_RANKING_LIMIT = 25;

  interface Resource<T> {
    loading: boolean;
    error: string | null;
    data: T | null;
  }

  function initialResource<T>(): Resource<T> {
    return { loading: true, error: null, data: null };
  }

  function errorMessage(err: unknown): string {
    if (err instanceof ApiRequestError) return err.message;
    return 'Erreur inconnue.';
  }

  // Période commune aux 4 graphiques "sur plage" (jours/heures/classement/confiance).
  let preset = $state<PeriodPreset>('30d');
  let customRange = $state<DateRange | null>(null);
  // Date locale "aujourd'hui" du site (contrat §1.4), connue seulement une fois /stats/kpis
  // chargé — jamais déduite de l'horloge du navigateur.
  let todayLocal = $state<string | null>(null);
  const range = $derived(todayLocal ? presetToRange(preset, todayLocal, customRange) : null);

  // Année de la heatmap : contrôle indépendant (exigence du lot), initialisée depuis les
  // KPIs du site (année de la dernière détection) une fois chargés.
  let heatmapYear = $state<number | null>(null);
  let heatmapMinYear = $state<number>(new Date().getFullYear());

  let kpis = $state<Resource<KpisResponse>>(initialResource());
  let daily = $state<Resource<DailyResponse>>(initialResource());
  let hourly = $state<Resource<HourlyResponse>>(initialResource());
  let speciesRanking = $state<Resource<SpeciesRankingResponse>>(initialResource());
  let confidence = $state<Resource<ConfidenceResponse>>(initialResource());
  let heatmap = $state<Resource<HeatmapResponse>>(initialResource());

  // Jetons de requête : ignorent une réponse arrivée après qu'un changement plus récent
  // (site, période, année) a déjà relancé un chargement — évite d'afficher une réponse
  // périmée qui arriverait en retard.
  let kpisRequestId = 0;
  let rangeRequestId = 0;
  let heatmapRequestId = 0;

  async function loadKpis(slug: string): Promise<void> {
    const requestId = ++kpisRequestId;
    // `untrack()` : ce chargement est invoqué depuis un $effect (ci-dessous) ; lire `kpis.data`
    // pour le conserver pendant le rechargement, puis écrire `kpis` juste après, ferait sinon
    // de `kpis` une dépendance de CET effect (lu ET écrit dans son exécution synchrone), qui
    // se redéclencherait alors indéfiniment (Svelte "effect_update_depth_exceeded").
    kpis = { loading: true, error: null, data: untrack(() => kpis.data) };
    try {
      const data = await getStatsKpis(slug);
      if (requestId !== kpisRequestId) return;
      kpis = { loading: false, error: null, data };
      todayLocal = data.date;
      // Année LOCALE (fuseau du site, contrat §1.3-§1.4), jamais l'année calendaire UTC : une
      // détection à 23h15 UTC en décembre en Europe/Paris (UTC+1) est déjà le 1er janvier de
      // l'année suivante localement — tronquer l'UtcInstant l'aurait fait rater d'un an.
      const detectedYear = data.last_detection_utc
        ? Number(utcInstantToLocalDate(data.last_detection_utc, data.timezone).slice(0, 4))
        : new Date().getFullYear();
      const firstYear = data.first_detection_utc
        ? Number(utcInstantToLocalDate(data.first_detection_utc, data.timezone).slice(0, 4))
        : detectedYear;
      heatmapMinYear = Number.isFinite(firstYear) ? firstYear : detectedYear;
      if (heatmapYear === null) heatmapYear = Number.isFinite(detectedYear) ? detectedYear : new Date().getFullYear();
    } catch (err) {
      if (requestId !== kpisRequestId) return;
      kpis = { loading: false, error: errorMessage(err), data: null };
      todayLocal = null;
    }
  }

  async function loadRangeDependent(slug: string, r: DateRange): Promise<void> {
    const requestId = ++rangeRequestId;
    // untrack() : voir le commentaire de loadKpis — même piège avec l'effect qui appelle
    // cette fonction (dépend de `range`, pas de ces quatre ressources).
    daily = { loading: true, error: null, data: untrack(() => daily.data) };
    hourly = { loading: true, error: null, data: untrack(() => hourly.data) };
    speciesRanking = { loading: true, error: null, data: untrack(() => speciesRanking.data) };
    confidence = { loading: true, error: null, data: untrack(() => confidence.data) };

    const [dailyResult, hourlyResult, speciesResult, confidenceResult] = await Promise.allSettled([
      getStatsDaily(slug, r),
      getStatsHourly(slug, r),
      getStatsSpeciesRanking(slug, { ...r, limit: SPECIES_RANKING_LIMIT }),
      getStatsConfidence(slug, r),
    ]);
    if (requestId !== rangeRequestId) return;

    daily =
      dailyResult.status === 'fulfilled'
        ? { loading: false, error: null, data: dailyResult.value }
        : { loading: false, error: errorMessage(dailyResult.reason), data: null };
    hourly =
      hourlyResult.status === 'fulfilled'
        ? { loading: false, error: null, data: hourlyResult.value }
        : { loading: false, error: errorMessage(hourlyResult.reason), data: null };
    speciesRanking =
      speciesResult.status === 'fulfilled'
        ? { loading: false, error: null, data: speciesResult.value }
        : { loading: false, error: errorMessage(speciesResult.reason), data: null };
    confidence =
      confidenceResult.status === 'fulfilled'
        ? { loading: false, error: null, data: confidenceResult.value }
        : { loading: false, error: errorMessage(confidenceResult.reason), data: null };
  }

  async function loadHeatmap(slug: string, y: number): Promise<void> {
    const requestId = ++heatmapRequestId;
    // untrack() : voir le commentaire de loadKpis — même piège avec l'effect qui appelle
    // cette fonction (dépend de `heatmapYear`, pas de `heatmap`).
    heatmap = { loading: true, error: null, data: untrack(() => heatmap.data) };
    try {
      const data = await getStatsHeatmap(slug, { year: y });
      if (requestId !== heatmapRequestId) return;
      heatmap = { loading: false, error: null, data };
    } catch (err) {
      if (requestId !== heatmapRequestId) return;
      heatmap = { loading: false, error: errorMessage(err), data: null };
    }
  }

  // Site sélectionné : (re)lance tout depuis zéro (KPIs d'abord, qui donnent la date locale
  // "aujourd'hui" nécessaire aux autres routes, et remettent à zéro l'année de la heatmap).
  $effect(() => {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    heatmapYear = null;
    todayLocal = null;
    void loadKpis(slug);
  });

  // Période (préréglage ou plage personnalisée) : ne recharge que les 4 graphiques "sur
  // plage", jamais les KPIs ni la heatmap.
  $effect(() => {
    const slug = siteStore.selectedSlug;
    const r = range;
    if (!slug || !r) return;
    void loadRangeDependent(slug, r);
  });

  // Année de la heatmap : ne recharge que la heatmap.
  $effect(() => {
    const slug = siteStore.selectedSlug;
    const y = heatmapYear;
    if (!slug || y === null) return;
    void loadHeatmap(slug, y);
  });

  onMount(() => {
    void siteStore.load();
  });

  function handlePresetChange(next: PeriodPreset): void {
    preset = next;
    if (next !== 'custom') customRange = null;
  }

  function handleCustomChange(start: string, end: string): void {
    customRange = { start, end };
  }

  function handleHeatmapYearChange(y: number): void {
    heatmapYear = y;
  }

  function retryKpis(): void {
    if (siteStore.selectedSlug) void loadKpis(siteStore.selectedSlug);
  }

  function retryRangeDependent(): void {
    if (siteStore.selectedSlug && range) void loadRangeDependent(siteStore.selectedSlug, range);
  }

  function retryHeatmap(): void {
    if (siteStore.selectedSlug && heatmapYear !== null) void loadHeatmap(siteStore.selectedSlug, heatmapYear);
  }
</script>

<div class="flex flex-col gap-6">
  <div>
    <h1 class="text-2xl font-semibold mb-1">Statistiques</h1>
    <p class="text-muted text-sm">Vue d'ensemble de l'activité du site sélectionné, dans l'esprit des analyses de BirdNET-Go.</p>
  </div>

  {#if siteStore.loading && !siteStore.selectedSlug}
    <LoadingSpinner label="Chargement des sites…" />
  {:else if siteStore.error}
    <ErrorAlert message={siteStore.error} />
  {:else if !siteStore.selectedSlug}
    <EmptyState title="Aucun site enregistré" description="Enregistrez un nœud pour voir apparaître ses statistiques ici." />
  {:else}
    <PeriodControls
      {preset}
      customStart={customRange?.start ?? null}
      customEnd={customRange?.end ?? null}
      onPresetChange={handlePresetChange}
      onCustomChange={handleCustomChange}
    />

    <Card title="Indicateurs clés" description="Vue d'ensemble depuis la première détection de ce site.">
      {#if kpis.loading}
        <LoadingSpinner label="Chargement des indicateurs…" />
      {:else if kpis.error}
        <div class="flex flex-col gap-2">
          <ErrorAlert message={kpis.error} />
          <Button size="sm" onclick={retryKpis}>Réessayer</Button>
        </div>
      {:else if kpis.data && kpis.data.lifetime_detections === 0}
        <EmptyState title="Aucune détection" description="Ce site n'a encore aucune détection enregistrée." />
      {:else if kpis.data}
        <KpiCards data={kpis.data} />
      {/if}
    </Card>

    <Card title="Détections par jour" description="Nombre de détections (barres) et d'espèces distinctes (ligne) chaque jour de la période.">
      {#if daily.loading}
        <LoadingSpinner label="Chargement de l'activité quotidienne…" />
      {:else if daily.error}
        <div class="flex flex-col gap-2">
          <ErrorAlert message={daily.error} />
          <Button size="sm" onclick={retryRangeDependent}>Réessayer</Button>
        </div>
      {:else if daily.data && daily.data.days.every(d => d.total === 0)}
        <EmptyState title="Aucune détection sur cette période" description="Essayez une période plus large." />
      {:else if daily.data}
        <DailyActivityChart data={daily.data} />
      {/if}
    </Card>

    <Card title="Répartition horaire" description="Détections par heure de la journée, empilées par espèce (10 principales par heure), sur la période.">
      {#if hourly.loading}
        <LoadingSpinner label="Chargement de la répartition horaire…" />
      {:else if hourly.error}
        <div class="flex flex-col gap-2">
          <ErrorAlert message={hourly.error} />
          <Button size="sm" onclick={retryRangeDependent}>Réessayer</Button>
        </div>
      {:else if hourly.data && hourly.data.hours.every(h => h.total === 0)}
        <EmptyState title="Aucune détection sur cette période" description="Essayez une période plus large." />
      {:else if hourly.data}
        <HourlyDistributionChart data={hourly.data} />
      {/if}
    </Card>

    <Card title="Classement des espèces" description="Les 25 espèces les plus détectées sur la période, par nombre de détections.">
      {#if speciesRanking.loading}
        <LoadingSpinner label="Chargement du classement…" />
      {:else if speciesRanking.error}
        <div class="flex flex-col gap-2">
          <ErrorAlert message={speciesRanking.error} />
          <Button size="sm" onclick={retryRangeDependent}>Réessayer</Button>
        </div>
      {:else if speciesRanking.data && speciesRanking.data.species.length === 0}
        <EmptyState title="Aucune espèce détectée sur cette période" description="Essayez une période plus large." />
      {:else if speciesRanking.data}
        <SpeciesRankingChart data={speciesRanking.data} />
      {/if}
    </Card>

    <Card title="Heatmap saisonnière" description="Détections par espèce (40 principales) et par semaine, pour l'année sélectionnée.">
      {#if heatmap.loading}
        <LoadingSpinner label="Chargement de la heatmap…" />
      {:else if heatmap.error}
        <div class="flex flex-col gap-2">
          <ErrorAlert message={heatmap.error} />
          <Button size="sm" onclick={retryHeatmap}>Réessayer</Button>
        </div>
      {:else if heatmap.data && heatmap.data.species.length === 0}
        <EmptyState title="Aucune détection cette année-là" description="Choisissez une autre année." />
      {:else if heatmap.data}
        <SeasonalHeatmap data={heatmap.data} year={heatmap.data.year} minYear={heatmapMinYear} onYearChange={handleHeatmapYearChange} />
      {/if}
    </Card>

    <Card title="Histogramme de confiance" description="Répartition des détections de la période selon le score de confiance du modèle.">
      {#if confidence.loading}
        <LoadingSpinner label="Chargement de l'histogramme…" />
      {:else if confidence.error}
        <div class="flex flex-col gap-2">
          <ErrorAlert message={confidence.error} />
          <Button size="sm" onclick={retryRangeDependent}>Réessayer</Button>
        </div>
      {:else if confidence.data && confidence.data.total === 0}
        <EmptyState title="Aucune détection sur cette période" description="Essayez une période plus large." />
      {:else if confidence.data}
        <ConfidenceHistogram data={confidence.data} />
      {/if}
    </Card>
  {/if}
</div>
