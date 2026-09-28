// Calcul des hauteurs de barres des mini-histogrammes de la fiche espèce (présence par
// mois, statistiques par mois / par heure).
//
// Les hauteurs sont exprimées en PIXELS, jamais en pourcentage : un `height: N%` ne se
// résout que si le parent a une hauteur définie, et dans une rangée flex `items-end` la
// colonne de chaque barre est dimensionnée par son contenu — le pourcentage retombait donc
// sur `auto` (0 px) et les barres étaient invisibles alors que les données étaient là.

/** Hauteur minimale d'une barre non nulle, pour qu'une petite valeur reste visible à côté
 *  d'un maximum très grand (ex. 3 détections face à 2 436). */
export const MIN_VISIBLE_BAR_PX = 2;

/**
 * Hauteur en pixels de chaque barre, proportionnelle au maximum de la série
 * (le maximum occupe toute la hauteur `trackPx`). Une valeur nulle ou négative → 0 px ;
 * une valeur positive → au moins `MIN_VISIBLE_BAR_PX`.
 */
export function barHeightsPx(values: readonly number[], trackPx: number): number[] {
  const max = Math.max(0, ...values);
  if (max <= 0 || trackPx <= 0) return values.map(() => 0);
  return values.map((value) => {
    if (!(value > 0)) return 0;
    const scaled = Math.round((value / max) * trackPx);
    return Math.min(trackPx, Math.max(MIN_VISIBLE_BAR_PX, scaled));
  });
}
