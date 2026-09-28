// Utilitaires de formatage propres à la page Système (équipe « système »).
// Pas partagés avec les autres équipes : gardés ici plutôt que dans src/lib/utils/
// pour respecter le périmètre de fichiers assigné (voir web/README.md).

import type { UtcInstant } from '../../api/types';

/** Formate un instant UTC en date/heure locale du navigateur, lisible en français. */
export function formatInstant(instant: UtcInstant | null): string {
  if (!instant) return '—';
  const date = new Date(instant);
  if (Number.isNaN(date.getTime())) return instant;
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Formate un pourcentage déjà en base 100 (ex. disk_free_pct). */
export function formatPercent(value: number | null, digits = 1): string {
  if (value === null) return '—';
  return `${value.toFixed(digits)} %`;
}

/** Formate une confiance [0,1] en pourcentage entier. */
export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)} %`;
}
