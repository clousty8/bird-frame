// Formatage partagé entre toutes les pages (bien commun, voir web/README.md).

const numberFormatter = new Intl.NumberFormat('fr-FR');

/** Nombre au format français (séparateur de milliers : espace fine insécable). */
export function formatNumber(value: number): string {
  return numberFormatter.format(value);
}

/**
 * Accord du nom avec un compteur, règle française : singulier pour 0 et 1 (et toute
 * valeur absolue < 2, ex. « 1,5 kilo »), pluriel à partir de 2. `plural` par défaut =
 * `singular + 's'` ; le fournir pour les pluriels irréguliers (« 3 nouveaux oiseaux »).
 */
export function pluralize(count: number, singular: string, plural: string = `${singular}s`): string {
  return Math.abs(count) < 2 ? singular : plural;
}

/** « 1 détection », « 2 438 détections » : nombre formaté + nom accordé. */
export function formatCount(count: number, singular: string, plural?: string): string {
  return `${formatNumber(count)} ${pluralize(count, singular, plural)}`;
}

/** Date locale `YYYY-MM-DD` (contrat §1.3) → « 27 sept. 2026 ». Valeur invalide renvoyée telle quelle. */
export function formatLocalDate(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  // Midi UTC : aucun fuseau ne fait glisser l'affichage sur la veille ou le lendemain.
  const date = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date);
}
