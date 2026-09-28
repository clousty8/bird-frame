// Grille « Activité quotidienne » (DailyActivityCalendar.svelte) : paliers de couleur.
//
// Le code couleur reste relatif au maximum horaire de CHAQUE espèce (on voit son rythme de la
// journée), mais en 5 paliers fixes plutôt qu'un dégradé continu : chaque case affiche
// désormais son nombre de détections, et un dégradé continu passait par des fonds bleu moyen
// sur lesquels ni un texte sombre ni un texte blanc n'atteignaient 4,5:1. Couleurs (dans le
// <style> du composant) et contraste du nombre, calculés en WCAG 2.x :
//   clair  : #e1e8f6 11,9 · #c3d2f3 9,7 · #a1baf2 7,6 · #6f96ee 5,1 (texte #1f2937) · #2563eb 5,2 (texte blanc)
//   sombre : #0a1a45 15,4 · #0f2a66 12,4 · #143786 10,0 · #1c4ab8 7,0 · #2563eb 4,7 (texte #f1f5f9)

export const HOURS: readonly number[] = Array.from({ length: 24 }, (_, hour) => hour);

export const HEAT_LEVELS = 5;

/** 0 = case vide ; 1..5 = part du maximum de l'espèce (≤ 20 %, ≤ 40 %, …, le maximum = 5). */
export function heatLevel(count: number, peak: number): number {
  if (count <= 0 || peak <= 0) return 0;
  return Math.min(HEAT_LEVELS, Math.max(1, Math.ceil((count / peak) * HEAT_LEVELS)));
}

/** Première heure ≥ `fromHour` où au moins une espèce a été détectée (les chouettes de la
 *  nuit ne doivent pas cacher le chœur de l'aube) ; `fromHour` si rien après. */
export function firstActiveHour(hoursBySpecies: readonly (readonly number[])[], fromHour = 0): number {
  let first = 24;
  for (const hours of hoursBySpecies) {
    for (let hour = fromHour; hour < Math.min(first, hours.length); hour += 1) {
      if ((hours[hour] ?? 0) > 0) {
        first = hour;
        break;
      }
    }
  }
  return first === 24 ? fromHour : first;
}
