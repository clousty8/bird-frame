// Densité des graduations des axes X des graphiques de la page Statistiques, selon la
// largeur réellement disponible (BaseChart est responsive). Sans ça, à 375 px de large, les
// 8 dates, 9 heures ou 10 tranches de confiance se chevauchaient en un trait illisible.

/** Nombre de graduations qui tiennent dans `width` px avec au moins `minSpacingPx` entre
 *  deux, borné à [2, maxTicks]. */
export function maxTicksForWidth(width: number, minSpacingPx: number, maxTicks: number): number {
  const fit = Math.floor(width / minSpacingPx);
  return Math.max(2, Math.min(maxTicks, fit));
}

const HOUR_STEPS = [1, 2, 3, 4, 6, 8, 12];

/** Pas (en heures) des graduations d'un axe 0-23 h : le plus petit pas « rond » ≥ `minStep`
 *  dont toutes les graduations tiennent dans `width` px. */
export function hourTickStep(width: number, minSpacingPx: number, minStep = 1): number {
  const fit = Math.max(2, Math.floor(width / minSpacingPx));
  for (const step of HOUR_STEPS) {
    if (step >= minStep && Math.ceil(24 / step) <= fit) return step;
  }
  return 12;
}

/** Vrai si chaque tranche (bande) est trop étroite pour un libellé « 90-100% », même incliné. */
export function isCompactBandAxis(width: number, bandCount: number, minBandPx = 48): boolean {
  return bandCount > 0 && width / bandCount < minBandPx;
}

/**
 * Échantillonne au plus `maxTicks` valeurs régulièrement espacées d'un domaine ordonné, en
 * gardant toujours la première et la dernière (ex. « aujourd'hui »). Si la dernière tombe
 * trop près de la précédente graduation échantillonnée (moins d'un demi-pas), c'est cette
 * précédente qui est retirée — sinon leurs libellés se chevauchent (« 26 sept.27 sept. »).
 */
export function sampleTicks<T>(domain: readonly T[], maxTicks: number): T[] {
  if (domain.length <= maxTicks) return [...domain];
  const step = Math.ceil(domain.length / Math.max(1, maxTicks - 1));
  const lastIndex = domain.length - 1;
  const indices: number[] = [];
  for (let i = 0; i < lastIndex; i += step) indices.push(i);
  const previous = indices[indices.length - 1];
  if (previous !== undefined && previous > 0 && lastIndex - previous < step / 2) indices.pop();
  indices.push(lastIndex);
  return indices.map((i) => domain[i] as T);
}
