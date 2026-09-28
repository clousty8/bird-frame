// Types de réponses/requêtes de l'API navigateur bird-frame.
// Repris tel quel de docs/api-contract.md §11 (annexe normative) — ne pas diverger sans
// mettre à jour le contrat en premier (règle de préséance §10.1 : le contrat fait foi).

// ---- Primitives -------------------------------------------------------------
export type UtcInstant = string; // "2026-09-27T14:39:01Z"
export type LocalDate = string; // "2026-09-27" (fuseau du site)
export type SpeciesRuleKind = 'present' | 'impossible' | 'redirect';
export type ReviewKind = 'correct' | 'false_positive';
export type PendingStatus = 'active' | 'approved' | 'rejected';
export type CommandStatus = 'pending' | 'delivered' | 'applied' | 'failed' | 'expired';
export type CommandKind =
  | 'set_species_threshold'
  | 'exclude_species'
  | 'unexclude_species'
  | 'include_species'
  | 'uninclude_species'
  | 'reset_dynamic_threshold'
  | 'set_main_name'
  | 'mark_detection_reviewed'
  | 'start_live'
  | 'live_heartbeat'
  | 'stop_live';
export type ActivityPattern = 'diurne' | 'nocturne' | 'crépusculaire' | 'mixte';
export type MigrationStatut =
  | 'sédentaire'
  | 'migrateur partiel'
  | 'migrateur'
  | 'hivernant'
  | 'estivant'
  | 'de passage';

export interface ApiError {
  error: string;
  message: string;
  details: unknown | null;
}

// ---- Session navigateur (contrat §2.2) ------------------------------------------
// GET /auth/me, réponse de POST /auth/login et POST /auth/logout.
export interface AuthStatus {
  authenticated: boolean;
  auth_enabled: boolean;
}
export interface LoginBody {
  password: string;
}
export interface Page {
  total: number;
  limit: number;
  offset: number;
}

// ---- Objets partagés --------------------------------------------------------
export interface NodeStatus {
  node_id: number;
  node_name: string;
  site_slug: string;
  site_name: string;
  online: boolean;
  last_seen_at: UtcInstant | null;
  last_sync_at: UtcInstant | null;
  last_heartbeat_at: UtcInstant | null;
  last_detection_at: UtcInstant | null;
  mic_device_name: string | null;
  mic_healthy: boolean | null;
  disk_free_pct: number | null;
  birdnet_go_reachable: boolean | null;
  birdnet_go_pid_alive: boolean | null;
  birdnet_go_version: string | null;
  bridge_version: string | null;
  synced_up_to_id: number;
  node_db_max_id: number | null;
  sync_lag: number | null;
  decommissioned_at: UtcInstant | null;
}
export interface PendingItem {
  node_id: number;
  scientific_name: string;
  common_name_fr: string | null;
  status: PendingStatus;
  hit_count: number;
  confidence_hint: number | null;
  first_detected_unix: number;
  last_updated_unix: number;
  source_id: string | null;
  photo_url: string | null;
}
export interface Prediction {
  scientific_name: string;
  common_name_fr: string | null;
  confidence: number;
  is_primary: boolean;
}
export interface RecentDetection {
  detection_id: number;
  scientific_name: string;
  common_name_fr: string | null;
  confidence: number;
  detected_at_utc: UtcInstant;
  photo_url: string | null;
}
export interface CommandInfo {
  command_id: number;
  node_id: number;
  kind: CommandKind;
  payload: Record<string, unknown>;
  status: CommandStatus;
  created_at: UtcInstant;
  delivered_at: UtcInstant | null;
  applied_at: UtcInstant | null;
  expires_at: UtcInstant | null;
  error_message: string | null;
  result: Record<string, unknown> | null;
}

// ---- Sites / nœuds ----------------------------------------------------------
export interface Site {
  slug: string;
  name: string;
  timezone: string;
  lat: number | null;
  lon: number | null;
  created_at: UtcInstant;
  node_count: number;
  online: boolean;
  last_detection_at: UtcInstant | null;
  total_detections: number;
}
export interface SitesResponse {
  sites: Site[];
}
export interface NodesResponse {
  nodes: NodeStatus[];
}

// ---- Dashboard --------------------------------------------------------------
export interface NowResponse {
  site_slug: string;
  server_time_utc: UtcInstant;
  pending: PendingItem[];
  node_status: NodeStatus | null;
  recent: RecentDetection[];
}
export interface SsePendingEvent {
  site_slug: string;
  updated_at_utc: UtcInstant;
  pending: PendingItem[];
}
export interface SseHeartbeatEvent {
  server_time_utc: UtcInstant;
  node_online: boolean;
}
export type SseDetectionEvent = RecentDetection;

export interface CalendarSpecies {
  scientific_name: string;
  common_name_fr: string | null;
  total: number;
  max_confidence: number;
  first_utc: UtcInstant;
  last_utc: UtcInstant;
  hours: number[] /* 24 */;
  photo_url: string | null;
}
export interface CalendarResponse {
  site_slug: string;
  date: LocalDate;
  timezone: string;
  sunrise_utc: UtcInstant | null;
  sunset_utc: UtcInstant | null;
  total_detections: number;
  species: CalendarSpecies[];
}
export interface RecentDetectionsResponse {
  detections: RecentDetection[];
}

// ---- Espèces ----------------------------------------------------------------
export interface SiteSpecies {
  scientific_name: string;
  common_name_fr: string | null;
  total: number;
  first_seen_utc: UtcInstant;
  last_seen_utc: UtcInstant;
  max_confidence: number;
  days_seen: number;
  photo_url: string | null;
  has_sheet: boolean;
  in_france_universe: boolean;
  rule: SpeciesRuleKind | null;
  redirect_to_scientific_name: string | null;
}
export interface SiteSpeciesResponse {
  site_slug: string;
  species: SiteSpecies[];
}

export interface UniverseSpecies {
  scientific_name: string;
  common_name_fr: string | null;
  order: string | null;
  family: string | null;
  in_france_universe: boolean;
  france_max_score: number | null;
  detected_sites: string[];
  total_detections: number;
  site_total: number | null;
  photo_url: string | null;
  has_sheet: boolean;
}
export interface SpeciesListResponse extends Page {
  species: UniverseSpecies[];
}

export interface WikiRef {
  title: string;
  url: string | null;
  description: string | null;
  extract: string | null;
}
export interface Taxonomy {
  kingdom: string | null;
  phylum: string | null;
  class: string | null;
  order: string | null;
  family: string | null;
  family_common: string | null;
  genus: string | null;
  species: string | null;
}
export interface SpeciesPhoto {
  url: string;
  url_1600: string;
  width: number | null;
  height: number | null;
  license: string | null;
  license_url: string | null;
  author: string | null;
  credit: string | null;
  description_url: string | null;
}
export interface Lookalike {
  scientific_name: string;
  common_name_fr: string | null;
  why_fr: string;
  /** L'espèce a une fiche sur ce serveur (GET /species/{name} répondrait 200). */
  has_page: boolean;
}
export interface FranceUniverse {
  max_score: number;
  cities: Record<string, number>;
  months: number[];
}
/** Niveau qualitatif d'un mois (contrat §6.9, seuils dans server/app/species_data/local_presence.py). */
export type PresenceLevel = 'tres_courant' | 'courant' | 'peu_frequent' | 'rare' | 'absent';
export interface LocalPresence {
  site_slug: string;
  site_name: string;
  reference_city: { name: string; distance_km: number };
  monthly_levels: PresenceLevel[] /* 12 */;
  /** 1-12, dans le fuseau du site. */
  current_month: number;
  current_month_level: PresenceLevel;
}
export interface PresenceBySite {
  site_slug: string;
  site_name: string;
  total: number;
  first_seen_utc: UtcInstant | null;
  last_seen_utc: UtcInstant | null;
  days_seen: number;
  max_confidence: number | null;
  months: number[] /* 12 */;
  rule: SpeciesRuleKind | null;
  redirect_to_scientific_name: string | null;
  local_presence: LocalPresence | null;
}
export interface SpeciesDetail {
  scientific_name: string;
  aliases: string[];
  common_name_fr: string | null;
  in_france_universe: boolean;
  taxonomy: Taxonomy | null;
  photo: SpeciesPhoto | null;
  wikipedia: { fr: WikiRef | null; en: WikiRef | null };
  has_sheet: boolean;
  summary_fr: string | null;
  habitat: string | null;
  diet: string | null;
  activity_pattern: ActivityPattern | null;
  migration: { statut: MigrationStatut; hiverne: string | null; niche: string | null; passage: string | null } | null;
  seasonality_fr: string | null;
  song_fr: string | null;
  lookalikes: Lookalike[];
  rarity_note: string | null;
  fun_facts: string[];
  france_universe: FranceUniverse | null;
  sources: string[];
  generated_at: UtcInstant | null;
  generator_model: string | null;
  reviewed_by_human: boolean;
  presence_by_site: PresenceBySite[];
  /** Une clé par site existant ; `null` si le site n'a pas de coordonnées ou l'espèce pas de données. */
  local_presence_by_site: Record<string, LocalPresence | null>;
}
export interface TopClip {
  kept_clip_id: number;
  detection_id: number;
  detected_at_utc: UtcInstant;
  confidence: number;
  rank: number | null;
  audio_available: boolean;
  audio_url: string | null;
  spectrogram_url: string | null;
  duration_s: number | null;
  review: 'correct' | null;
  missing: boolean;
  predictions: Prediction[];
}
export interface TopClipsResponse {
  site_slug: string;
  scientific_name: string;
  clips: TopClip[];
}
export interface PresenceResponse {
  scientific_name: string;
  site_slug: string | null;
  total: number;
  first_seen_utc: UtcInstant | null;
  last_seen_utc: UtcInstant | null;
  months: number[] /* 12 */;
  hours: number[] /* 24 */;
  by_day: { date: LocalDate; count: number }[] | null /* 365 */;
}

// ---- Stats ------------------------------------------------------------------
interface StatsBase {
  site_slug: string;
  timezone: string;
}
interface StatsRange extends StatsBase {
  start: LocalDate;
  end: LocalDate;
}
export interface KpisResponse extends StatsBase {
  date: LocalDate;
  lifetime_species: number;
  lifetime_detections: number;
  today_detections: number;
  today_species: number;
  best_day: { date: LocalDate; count: number } | null;
  streak_days: number;
  first_detection_utc: UtcInstant | null;
  last_detection_utc: UtcInstant | null;
}
export interface DailyResponse extends StatsRange {
  days: { date: LocalDate; total: number; species_count: number }[];
}
export interface HourlyResponse extends StatsRange {
  hours: {
    hour: number;
    total: number;
    species: { scientific_name: string; common_name_fr: string | null; count: number }[];
  }[] /* 24 */;
}
export interface SpeciesRankingResponse extends StatsRange {
  total_species: number;
  species: {
    rank: number;
    scientific_name: string;
    common_name_fr: string | null;
    total: number;
    days_seen: number;
    max_confidence: number;
    avg_confidence: number;
    first_utc: UtcInstant;
    last_utc: UtcInstant;
    photo_url: string | null;
  }[];
}
export interface HeatmapResponse extends StatsBase {
  year: number;
  week_count: 53;
  species: { scientific_name: string; common_name_fr: string | null; total: number; weeks: number[] /* 53 */ }[];
}
export interface ConfidenceResponse extends StatsRange {
  species: string | null;
  total: number;
  buckets: { min: number; max: number; count: number }[] /* 10 */;
}

// ---- Système ----------------------------------------------------------------
export interface SpeciesRule {
  scientific_name: string;
  common_name_fr: string | null;
  rule: SpeciesRuleKind;
  threshold_override: number | null;
  redirect_to_scientific_name: string | null;
  redirect_to_common_name_fr: string | null;
  reason: string | null;
  updated_at: UtcInstant;
  sync_status: 'none' | 'pending' | 'applied' | 'failed';
  commands: CommandInfo[];
}
export interface SpeciesRulesResponse {
  site_slug: string;
  rules: SpeciesRule[];
}
export interface PutSpeciesRuleBody {
  rule: SpeciesRuleKind;
  threshold_override?: number | null;
  redirect_to_scientific_name?: string | null;
  reason?: string | null;
}
export interface PutSpeciesRuleResponse {
  rule: SpeciesRule;
}
export interface DeleteSpeciesRuleResponse {
  deleted: true;
  commands: CommandInfo[];
}

export interface DynamicThreshold {
  node_id: number;
  scientific_name: string;
  common_name_fr: string | null;
  node_species_name: string;
  level: number;
  current_value: number;
  base_threshold: number;
  high_conf_count: number;
  trigger_count: number;
  is_active: boolean;
  expires_at: UtcInstant | null;
  last_triggered_at: UtcInstant | null;
  first_created_at: UtcInstant | null;
  reset_pending: boolean;
}
export interface DynamicThresholdsResponse {
  site_slug: string;
  snapshot_at: UtcInstant | null;
  thresholds: DynamicThreshold[];
}
export interface ResetDynamicThresholdResponse {
  commands: CommandInfo[];
}

export interface Review {
  review_id: number;
  detection_id: number;
  kind: ReviewKind;
  note: string | null;
  created_at: UtcInstant;
  created_by: string | null;
  synced_to_node_at: UtcInstant | null;
  command_status: CommandStatus | null;
  detection: { scientific_name: string; common_name_fr: string | null; confidence: number; detected_at_utc: UtcInstant };
}
export interface PostReviewBody {
  detection_id: number;
  kind: ReviewKind;
  note?: string | null;
}
export interface PostReviewResponse {
  review: Review;
  command_id: number | null;
}
export interface ReviewsResponse extends Page {
  reviews: Review[];
}

export interface FalseNegative {
  id: number;
  scientific_name: string;
  common_name_fr: string | null;
  known_species: boolean;
  approx_time_utc: UtcInstant | null;
  notes: string | null;
  reported_at: UtcInstant;
  reported_by: string | null;
}
export interface PostFalseNegativeBody {
  scientific_name: string;
  approx_time_utc?: UtcInstant | null;
  notes?: string | null;
}
export interface PostFalseNegativeResponse {
  false_negative: FalseNegative;
}
export interface FalseNegativesResponse extends Page {
  false_negatives: FalseNegative[];
}

export interface CommandsResponse extends Page {
  commands: CommandInfo[];
}

export interface ReviewDetection {
  detection_id: number;
  node_id: number;
  node_local_id: number;
  detected_at_utc: UtcInstant;
  local_date: LocalDate;
  scientific_name: string;
  common_name_fr: string | null;
  effective_scientific_name: string;
  effective_common_name_fr: string | null;
  confidence: number;
  source_display_name: string | null;
  has_clip: boolean;
  kept_clip_id: number | null;
  audio_url: string | null;
  spectrogram_url: string | null;
  review: ReviewKind | null;
  review_note: string | null;
  rule: SpeciesRuleKind | null;
  predictions: Prediction[];
}
export interface DetectionsResponse extends Page {
  detections: ReviewDetection[];
}

// ---- Santé --------------------------------------------------------------------
// GET /health (hors /api/v1, contrat §1.12) — ajout non normatif mais pratique pour la
// page système (statut serveur), pas de champ en plus par rapport au contrat.
export interface HealthResponse {
  status: string;
  version: string;
}
