// Calcul des périodes du sélecteur de la page Statistiques (7 j / 30 j / 90 j / année /
// personnalisée). Fichier neuf (pas de copie BirdNET-Go). Les bornes sont des dates locales
// "YYYY-MM-DD" (contrat docs/api-contract.md §1.3/1.4 — jamais un instant UTC, jamais le
// fuseau du navigateur) : tout le calcul se fait donc en arithmétique de calendrier pure sur
// la chaîne, sans jamais construire un `Date` local qui dépendrait du fuseau du navigateur.

export type PeriodPreset = '7d' | '30d' | '90d' | 'year' | 'custom';

export interface DateRange {
  start: string;
  end: string;
}

export const PERIOD_PRESETS: { value: PeriodPreset; label: string }[] = [
  { value: '7d', label: '7 jours' },
  { value: '30d', label: '30 jours' },
  { value: '90d', label: '90 jours' },
  { value: 'year', label: 'Cette année' },
  { value: 'custom', label: 'Personnalisée' },
];

const LOCAL_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Vrai si `value` a la forme "YYYY-MM-DD" et représente une date calendaire réelle. */
export function isValidLocalDate(value: string): boolean {
  if (!LOCAL_DATE_RE.test(value)) return false;
  const [y, m, d] = value.split('-').map(Number);
  if (y === undefined || m === undefined || d === undefined) return false;
  const date = new Date(Date.UTC(y, m - 1, d));
  // Rejette les dates qui débordent (ex. "2026-02-30" -> remonte en mars).
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}

function parseLocalDate(value: string): Date {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

function formatLocalDate(date: Date): string {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function addDays(value: string, days: number): string {
  const date = parseLocalDate(value);
  date.setUTCDate(date.getUTCDate() + days);
  return formatLocalDate(date);
}

/**
 * Traduit un préréglage en bornes `start`/`end` (inclusives des deux côtés, contrat §1.4),
 * relatives à `todayLocal` — la date locale "aujourd'hui" du site, telle que renvoyée par
 * `GET /stats/kpis` (jamais calculée depuis l'horloge du navigateur, qui peut être dans un
 * autre fuseau que le site).
 */
export function presetToRange(preset: PeriodPreset, todayLocal: string, custom?: DateRange | null): DateRange {
  switch (preset) {
    case '7d':
      return { start: addDays(todayLocal, -6), end: todayLocal };
    case '30d':
      return { start: addDays(todayLocal, -29), end: todayLocal };
    case '90d':
      return { start: addDays(todayLocal, -89), end: todayLocal };
    case 'year': {
      const year = parseLocalDate(todayLocal).getUTCFullYear();
      return { start: `${year}-01-01`, end: todayLocal };
    }
    case 'custom':
      if (custom && isValidLocalDate(custom.start) && isValidLocalDate(custom.end) && custom.start <= custom.end) {
        return custom;
      }
      // Repli tant que l'utilisateur n'a pas encore choisi une plage personnalisée valide.
      return { start: addDays(todayLocal, -29), end: todayLocal };
  }
}

/**
 * Convertit un `UtcInstant` ("...Z") en date locale "YYYY-MM-DD" dans le fuseau donné
 * (contrat §1.3-§1.4 : toute notion de "jour"/"année" se calcule dans le fuseau du site,
 * jamais en UTC — tronquer un UtcInstant à ses 10 premiers caractères donne le jour calendaire
 * UTC, qui diverge du jour local pour toute détection proche de minuit UTC).
 */
export function utcInstantToLocalDate(utcInstant: string, timezone: string): string {
  const date = new Date(utcInstant);
  try {
    // La locale 'en-CA' formate nativement en "YYYY-MM-DD" — pas de recomposition manuelle
    // fragile depuis formatToParts().
    return new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(
      date
    );
  } catch {
    // Fuseau inconnu/mal formé côté site : jamais bloquant, repli sur le jour calendaire UTC.
    return utcInstant.slice(0, 10);
  }
}

/** Formatage court en français d'une date locale "YYYY-MM-DD", ex. "27 sept. 2026". */
export function formatLocalDateFr(value: string): string {
  if (!isValidLocalDate(value)) return value;
  // Midi UTC : évite qu'un fuseau négatif fasse glisser l'affichage sur la veille.
  const date = new Date(`${value}T12:00:00Z`);
  return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(
    date
  );
}
