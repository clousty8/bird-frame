// Client HTTP typé vers le serveur bird-frame (routes navigateur, contrat §6).
// Une fonction par route, gestion d'erreur uniforme (ApiRequestError, jamais une erreur
// avalée en silence), + un helper SSE pour le flux "en écoute" (contrat §6.4).

import type {
  ApiError,
  CalendarResponse,
  CommandsResponse,
  ConfidenceResponse,
  DailyResponse,
  DeleteSpeciesRuleResponse,
  DetectionsResponse,
  DynamicThresholdsResponse,
  FalseNegativesResponse,
  HealthResponse,
  HeatmapResponse,
  HourlyResponse,
  KpisResponse,
  NodesResponse,
  NowResponse,
  PostFalseNegativeBody,
  PostFalseNegativeResponse,
  PostReviewBody,
  PostReviewResponse,
  PresenceResponse,
  PutSpeciesRuleBody,
  PutSpeciesRuleResponse,
  RecentDetectionsResponse,
  ResetDynamicThresholdResponse,
  ReviewKind,
  ReviewsResponse,
  SiteSpeciesResponse,
  SitesResponse,
  SpeciesListResponse,
  SpeciesRulesResponse,
  SpeciesDetail,
  SseDetectionEvent,
  SseHeartbeatEvent,
  SsePendingEvent,
  SpeciesRankingResponse,
  TopClipsResponse,
} from './types';

/** Base des routes API navigateur (contrat §2.3). Proxifiée par Vite en dev (vite.config.ts). */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api/v1';

/** Erreur levée par toute fonction de ce module — jamais avalée, toujours à afficher/gérer par l'appelant. */
export class ApiRequestError extends Error {
  /** Code machine stable (catalogue contrat §1.8), ou 'network_error'/'invalid_response' côté client. */
  readonly code: string;
  /** Statut HTTP, 0 pour une erreur réseau (le serveur n'a pas répondu). */
  readonly status: number;
  readonly details: unknown;

  constructor(code: string, message: string, status: number, details: unknown = null) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

type QueryValue = string | number | boolean | undefined | null | string[];

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  query?: Record<string, QueryValue>;
  /** Base alternative (ex. hors /api/v1, pour /health). Défaut : API_BASE. */
  base?: string;
}

function buildQueryString(query: Record<string, QueryValue> | undefined): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const base = options.base ?? API_BASE;
  const url = `${base}${path}${buildQueryString(options.query)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (networkError) {
    // Serveur injoignable, CORS, etc. : toujours remonté à l'appelant, jamais avalé.
    throw new ApiRequestError(
      'network_error',
      "Impossible de joindre le serveur bird-frame. Vérifiez qu'il est démarré.",
      0,
      networkError instanceof Error ? networkError.message : String(networkError)
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text.length > 0) {
    try {
      payload = JSON.parse(text);
    } catch {
      throw new ApiRequestError(
        'invalid_response',
        `Réponse JSON invalide reçue du serveur (HTTP ${response.status}).`,
        response.status,
        text
      );
    }
  }

  if (!response.ok) {
    const err = (payload ?? {}) as Partial<ApiError>;
    throw new ApiRequestError(
      err.error ?? 'unknown_error',
      err.message ?? `Erreur HTTP ${response.status}.`,
      response.status,
      err.details ?? null
    );
  }

  return payload as T;
}

// ---- Santé --------------------------------------------------------------------

/** GET /health (hors /api/v1, contrat §1.12). */
export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health', { base: '' });
}

// ---- Sites et nœuds (contrat §6.2) --------------------------------------------

export function getSites(): Promise<SitesResponse> {
  return apiFetch<SitesResponse>('/sites');
}

export function getNodes(params?: { includeDecommissioned?: boolean }): Promise<NodesResponse> {
  return apiFetch<NodesResponse>('/nodes', {
    query: { include_decommissioned: params?.includeDecommissioned },
  });
}

// ---- Dashboard (contrat §6.3-§6.7) ---------------------------------------------

export function getSiteNow(slug: string): Promise<NowResponse> {
  return apiFetch<NowResponse>(`/sites/${encodeURIComponent(slug)}/now`);
}

export function getCalendar(slug: string, params?: { date?: string }): Promise<CalendarResponse> {
  return apiFetch<CalendarResponse>(`/sites/${encodeURIComponent(slug)}/calendar`, {
    query: { date: params?.date },
  });
}

/** Route transitoire WP-04 (contrat §6.6), remplacée fonctionnellement par getSiteNow. */
export function getRecentDetections(slug: string, params?: { limit?: number }): Promise<RecentDetectionsResponse> {
  return apiFetch<RecentDetectionsResponse>(`/sites/${encodeURIComponent(slug)}/recent-detections`, {
    query: { limit: params?.limit },
  });
}

export function getSiteSpecies(
  slug: string,
  params?: { sort?: 'total' | 'last_seen' | 'common_name' }
): Promise<SiteSpeciesResponse> {
  return apiFetch<SiteSpeciesResponse>(`/sites/${encodeURIComponent(slug)}/species`, {
    query: { sort: params?.sort },
  });
}

// ---- Espèces (contrat §6.8-§6.12) ----------------------------------------------

export function getSpeciesList(params?: {
  site?: string;
  q?: string;
  detectedOnly?: boolean;
  sort?: 'common_name' | 'france_max_score' | 'detections';
  limit?: number;
  offset?: number;
}): Promise<SpeciesListResponse> {
  return apiFetch<SpeciesListResponse>('/species', {
    query: {
      site: params?.site,
      q: params?.q,
      detected_only: params?.detectedOnly,
      sort: params?.sort,
      limit: params?.limit,
      offset: params?.offset,
    },
  });
}

export function getSpeciesDetail(scientificName: string): Promise<SpeciesDetail> {
  return apiFetch<SpeciesDetail>(`/species/${encodeURIComponent(scientificName)}`);
}

/** Construit l'URL de la photo (contrat §6.10). La plupart des pages utilisent plutôt
 *  le `photo_url`/`photo.url` déjà renvoyé par le serveur ; cet helper sert quand on n'a
 *  que le nom scientifique. */
export function speciesPhotoUrl(scientificName: string, size: 320 | 1600 = 320): string {
  return `${API_BASE}/species/${encodeURIComponent(scientificName)}/photo?size=${size}`;
}

/** Contrat §1.6 : "Le frontend construit la variante HD en remplaçant size=320 par size=1600". */
export function toHighResPhotoUrl(photoUrl: string): string {
  return photoUrl.replace('size=320', 'size=1600');
}

export function getTopClips(
  scientificName: string,
  slug: string,
  params?: { includeMissing?: boolean }
): Promise<TopClipsResponse> {
  return apiFetch<TopClipsResponse>(
    `/species/${encodeURIComponent(scientificName)}/sites/${encodeURIComponent(slug)}/top-clips`,
    { query: { include_missing: params?.includeMissing } }
  );
}

export function getSpeciesPresence(
  scientificName: string,
  params?: { site?: string; includeByDay?: boolean }
): Promise<PresenceResponse> {
  return apiFetch<PresenceResponse>(`/species/${encodeURIComponent(scientificName)}/presence`, {
    query: { site: params?.site, include_by_day: params?.includeByDay },
  });
}

// ---- Enregistrements (contrat §6.13) -------------------------------------------

export function recordingAudioUrl(keptClipId: number): string {
  return `${API_BASE}/recordings/${keptClipId}/audio`;
}

export function recordingSpectrogramUrl(keptClipId: number): string {
  return `${API_BASE}/recordings/${keptClipId}/spectrogram`;
}

// ---- Statistiques (contrat §6.14-§6.19) ----------------------------------------

interface StatsRangeParams {
  start?: string;
  end?: string;
}

export function getStatsKpis(slug: string): Promise<KpisResponse> {
  return apiFetch<KpisResponse>(`/sites/${encodeURIComponent(slug)}/stats/kpis`);
}

export function getStatsDaily(slug: string, params?: StatsRangeParams): Promise<DailyResponse> {
  return apiFetch<DailyResponse>(`/sites/${encodeURIComponent(slug)}/stats/daily`, {
    query: { start: params?.start, end: params?.end },
  });
}

export function getStatsHourly(slug: string, params?: StatsRangeParams): Promise<HourlyResponse> {
  return apiFetch<HourlyResponse>(`/sites/${encodeURIComponent(slug)}/stats/hourly`, {
    query: { start: params?.start, end: params?.end },
  });
}

export function getStatsSpeciesRanking(
  slug: string,
  params?: StatsRangeParams & { limit?: number }
): Promise<SpeciesRankingResponse> {
  return apiFetch<SpeciesRankingResponse>(`/sites/${encodeURIComponent(slug)}/stats/species`, {
    query: { start: params?.start, end: params?.end, limit: params?.limit },
  });
}

export function getStatsHeatmap(
  slug: string,
  params?: { year?: number; species?: string[] }
): Promise<HeatmapResponse> {
  return apiFetch<HeatmapResponse>(`/sites/${encodeURIComponent(slug)}/stats/heatmap`, {
    query: { year: params?.year, species: params?.species },
  });
}

export function getStatsConfidence(
  slug: string,
  params?: StatsRangeParams & { species?: string }
): Promise<ConfidenceResponse> {
  return apiFetch<ConfidenceResponse>(`/sites/${encodeURIComponent(slug)}/stats/confidence`, {
    query: { start: params?.start, end: params?.end, species: params?.species },
  });
}

// ---- Système : règles par espèce (contrat §6.20-§6.22) -------------------------

export function getSpeciesRules(slug: string): Promise<SpeciesRulesResponse> {
  return apiFetch<SpeciesRulesResponse>(`/sites/${encodeURIComponent(slug)}/species-rules`);
}

export function putSpeciesRule(
  slug: string,
  scientificName: string,
  body: PutSpeciesRuleBody
): Promise<PutSpeciesRuleResponse> {
  return apiFetch<PutSpeciesRuleResponse>(
    `/sites/${encodeURIComponent(slug)}/species-rules/${encodeURIComponent(scientificName)}`,
    { method: 'PUT', body }
  );
}

export function deleteSpeciesRule(slug: string, scientificName: string): Promise<DeleteSpeciesRuleResponse> {
  return apiFetch<DeleteSpeciesRuleResponse>(
    `/sites/${encodeURIComponent(slug)}/species-rules/${encodeURIComponent(scientificName)}`,
    { method: 'DELETE' }
  );
}

// ---- Système : seuils dynamiques (contrat §6.23-§6.24) -------------------------

export function getDynamicThresholds(slug: string): Promise<DynamicThresholdsResponse> {
  return apiFetch<DynamicThresholdsResponse>(`/sites/${encodeURIComponent(slug)}/dynamic-thresholds`);
}

export function resetDynamicThreshold(slug: string, scientificName: string): Promise<ResetDynamicThresholdResponse> {
  return apiFetch<ResetDynamicThresholdResponse>(
    `/sites/${encodeURIComponent(slug)}/dynamic-thresholds/${encodeURIComponent(scientificName)}`,
    { method: 'DELETE' }
  );
}

// ---- Système : revue faux positif / faux négatif (contrat §6.25-§6.28) --------

export function postReview(slug: string, body: PostReviewBody): Promise<PostReviewResponse> {
  return apiFetch<PostReviewResponse>(`/sites/${encodeURIComponent(slug)}/reviews`, { method: 'POST', body });
}

export function getReviews(
  slug: string,
  params?: { limit?: number; offset?: number; kind?: ReviewKind }
): Promise<ReviewsResponse> {
  return apiFetch<ReviewsResponse>(`/sites/${encodeURIComponent(slug)}/reviews`, { query: params });
}

export function postFalseNegative(slug: string, body: PostFalseNegativeBody): Promise<PostFalseNegativeResponse> {
  return apiFetch<PostFalseNegativeResponse>(`/sites/${encodeURIComponent(slug)}/false-negatives`, {
    method: 'POST',
    body,
  });
}

export function getFalseNegatives(
  slug: string,
  params?: { limit?: number; offset?: number }
): Promise<FalseNegativesResponse> {
  return apiFetch<FalseNegativesResponse>(`/sites/${encodeURIComponent(slug)}/false-negatives`, { query: params });
}

// ---- Système : audit des commandes (contrat §6.29) -----------------------------

type CommandsQueryStatus = 'pending' | 'delivered' | 'applied' | 'failed' | 'expired';

export function getCommands(
  slug: string,
  params?: { status?: CommandsQueryStatus; kind?: string; limit?: number; offset?: number }
): Promise<CommandsResponse> {
  return apiFetch<CommandsResponse>(`/sites/${encodeURIComponent(slug)}/commands`, { query: params });
}

// ---- Revue des détections (contrat §6.30) --------------------------------------

export function getDetections(
  slug: string,
  params?: {
    date?: string;
    species?: string;
    minConfidence?: number;
    review?: ReviewKind | 'none';
    limit?: number;
    offset?: number;
  }
): Promise<DetectionsResponse> {
  return apiFetch<DetectionsResponse>(`/sites/${encodeURIComponent(slug)}/detections`, {
    query: {
      date: params?.date,
      species: params?.species,
      min_confidence: params?.minConfidence,
      review: params?.review,
      limit: params?.limit,
      offset: params?.offset,
    },
  });
}

// ---- SSE : bloc "en écoute" (contrat §6.4) -------------------------------------

export interface PendingStreamHandlers {
  onPending?: (event: SsePendingEvent) => void;
  onHeartbeat?: (event: SseHeartbeatEvent) => void;
  onDetection?: (event: SseDetectionEvent) => void;
  /** Appelé sur toute erreur de connexion (EventSource se reconnecte de lui-même ensuite). */
  onError?: (error: Event) => void;
}

/**
 * S'abonne à GET /sites/{slug}/pending/stream (SSE, contrat §6.4).
 * Retourne une fonction de désabonnement qui ferme la connexion.
 */
export function subscribeToPending(slug: string, handlers: PendingStreamHandlers): () => void {
  const url = `${API_BASE}/sites/${encodeURIComponent(slug)}/pending/stream`;
  const source = new EventSource(url);

  function parse<T>(event: MessageEvent<string>): T | null {
    try {
      return JSON.parse(event.data) as T;
    } catch {
      // Un événement mal formé ne doit jamais faire planter le flux : on le journalise
      // et on ignore cet événement précis, la connexion SSE continue.
      console.error('[bird-frame] événement SSE "pending" illisible', event.data);
      return null;
    }
  }

  if (handlers.onPending) {
    source.addEventListener('pending', (event) => {
      const data = parse<SsePendingEvent>(event as MessageEvent<string>);
      if (data) handlers.onPending?.(data);
    });
  }
  if (handlers.onHeartbeat) {
    source.addEventListener('heartbeat', (event) => {
      const data = parse<SseHeartbeatEvent>(event as MessageEvent<string>);
      if (data) handlers.onHeartbeat?.(data);
    });
  }
  if (handlers.onDetection) {
    source.addEventListener('detection', (event) => {
      const data = parse<SseDetectionEvent>(event as MessageEvent<string>);
      if (data) handlers.onDetection?.(data);
    });
  }
  // Quand l'utilisateur quitte la page (rechargement, fermeture d'onglet, lien sortant), le
  // navigateur coupe lui-même le flux APRÈS `beforeunload` et AVANT `pagehide`, en émettant
  // un `error` (readyState CLOSED) : ce n'est pas une panne, on ne le remonte pas (il
  // polluait la console, et les journaux Vite, à chaque rechargement). Si la navigation
  // n'aboutit pas (ex. lien vers un fichier téléchargé), le drapeau retombe après 1 s.
  let leavingPage = false;
  const onBeforeUnload = (): void => {
    leavingPage = true;
    setTimeout(() => {
      leavingPage = false;
    }, 1000);
  };
  window.addEventListener('beforeunload', onBeforeUnload);

  if (handlers.onError) {
    source.addEventListener('error', (event) => {
      if (leavingPage) return;
      handlers.onError?.(event);
    });
  }

  return () => {
    window.removeEventListener('beforeunload', onBeforeUnload);
    source.close();
  };
}
