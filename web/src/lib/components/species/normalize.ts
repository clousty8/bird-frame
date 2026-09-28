// Recherche texte insensible à la casse et aux accents.
//
// Le contrat (docs/api-contract.md §6.8) décrit ce filtrage pour GET /species (paramètre
// `q`, NFKD + casefold), mais GET /sites/{slug}/species (§6.7, la vue « espèces détectées
// ici » par défaut) n'a pas de paramètre de recherche serveur — le contrat est muet sur ce
// cas. Choix le plus simple, noté hors contrat : filtrage local, sur le même principe
// (NFKD + suppression des diacritiques + casefold) ; la liste des espèces détectées sur un
// site reste petite (quelques dizaines à ~200), donc pas de souci de performance.

export function normalizeForSearch(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/** Vrai si `query` (vide = tout passe) apparaît dans au moins un des champs fournis. */
export function matchesQuery(query: string, ...fields: (string | null)[]): boolean {
  const normalizedQuery = normalizeForSearch(query.trim());
  if (!normalizedQuery) return true;
  return fields.some((field) => field !== null && normalizeForSearch(field).includes(normalizedQuery));
}
