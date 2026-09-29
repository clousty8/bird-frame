# NOTICE — fichiers adaptés de BirdNET-Go

Conformément à `docs/architecture.md` §0.3, tout fichier copié ou adapté depuis
`birdnet-go-ui/frontend` reste sous la licence d'origine du projet BirdNET-Go
(**CC BY-NC-SA 4.0**, texte complet : `LICENSES/CC-BY-NC-SA-4.0.txt` à la racine) et porte un
en-tête de licence en tête de fichier. Le reste de `web/` est sous licence MIT (`LICENSE`). Ce tableau est
la référence : `web/tests/notice.test.ts` vérifie automatiquement que chaque fichier listé
ici existe et porte bien cet en-tête (aucune dérive silencieuse possible).

| Fichier copié | Fichier d'origine (dans `birdnet-go-ui/frontend`) | Nature de l'adaptation | Licence |
|---|---|---|---|
| `web/src/styles/tailwind.css` | `src/styles/tailwind.css` | Suppression de l'import de `custom.css` (styles historiques BirdNET-Go absents ici) et des `@font-face` Inter (fichiers de police non copiés), remplacés par une pile de polices système ; classes d'accordéon `.collapse*` renommées `.collapsible*` (collision avec l'utilitaire Tailwind v4 `collapse` = `visibility: collapse`) ; couleurs d'état : contenus (`--color-*-content`) et jetons `--color-*-text` ajustés pour un contraste WCAG AA dans les deux thèmes. Le reste (tokens `@theme`, composants/utilitaires CSS génériques) est repris tel quel. | CC BY-NC-SA 4.0 |
| `web/src/styles/schemes.css` | `src/styles/schemes.css` | Copié tel quel (6 palettes clair/sombre, aucune modification). | CC BY-NC-SA 4.0 |
| `web/src/lib/components/ui/CollapsibleSection.svelte` | `src/lib/desktop/components/ui/CollapsibleSection.svelte` | Icône `@lucide/svelte` (ChevronDown) remplacée par un SVG inline ; suppression de la case à cocher cachée (compatibilité DaisyUI, non utilisée ici) ; classe `collapsible-open` posée selon l'état ouvert, classes `.collapsible*`, identifiant de contenu unique (`$props.id()`), contenu fermé rendu `inert`. | CC BY-NC-SA 4.0 |
| `web/src/lib/components/ui/Card.svelte` | `src/lib/desktop/components/ui/Card.svelte` | Aucune dépendance externe à retirer ; prop `className` renommée `class`. | CC BY-NC-SA 4.0 |
| `web/src/lib/components/ui/Badge.svelte` | `src/lib/desktop/components/ui/Badge.svelte` | Suppression de l'utilitaire `safeGet` (accès direct aux tables de classes, sûr ici car les unions `variant`/`size` sont fermées et vérifiées par TypeScript) ; texte des variantes `outline` d'état en `--color-*-text` (contraste WCAG AA). | CC BY-NC-SA 4.0 |
| `web/src/lib/components/ui/Button.svelte` | `src/lib/desktop/components/ui/Button.svelte` | Suppression de `safeGet` ; props HTML réduites au strict nécessaire plutôt qu'un spread `HTMLButtonAttributes` complet ; texte des variantes success/warning/error en `--color-*-text` (contraste WCAG AA). | CC BY-NC-SA 4.0 |
| `web/src/lib/components/ui/LoadingSpinner.svelte` | `src/lib/desktop/components/ui/LoadingSpinner.svelte` | Suppression de la dépendance i18n (`t('common.ui.loading')`) : libellé français en dur ("Chargement…"), conforme à la décision du lead (pas de système i18n pour l'instant). | CC BY-NC-SA 4.0 |
| `web/src/lib/components/ui/EmptyState.svelte` | `src/lib/desktop/components/ui/EmptyState.svelte` | Icône `@lucide/svelte` (Inbox) remplacée par un SVG inline. | CC BY-NC-SA 4.0 |
| `web/src/lib/components/ui/ErrorAlert.svelte` | `src/lib/desktop/components/ui/ErrorAlert.svelte` | Icônes `@lucide/svelte` remplacées par des SVG inline ; suppression de la dépendance i18n (libellé français en dur) et du logger BirdNET-Go (`console.error` direct). | CC BY-NC-SA 4.0 |
| `web/src/lib/charts/BaseChart.svelte` | `src/lib/desktop/features/analytics/components/charts/d3/BaseChart.svelte` | Copié tel quel, sauf une garde ajoutée dans `setupResizeObserver()` : si `ResizeObserver` n'existe pas dans l'environnement (jsdom, tests vitest), le graphique reste sur ses dimensions par défaut au lieu de planter. | CC BY-NC-SA 4.0 |
| `web/src/lib/charts/utils/theme.ts` | `.../charts/d3/utils/theme.ts` | Remplacement du logger interne BirdNET-Go (`$lib/utils/logger`, absent ici) par un `console.error` direct dans `ThemeStore.notifySubscribers()`, même convention que `ErrorAlert.svelte`. Le reste (lecture des tokens CSS, palette espèces) est repris tel quel. | CC BY-NC-SA 4.0 |
| `web/src/lib/charts/utils/scales.ts` | `.../charts/d3/utils/scales.ts` | Copié tel quel. | CC BY-NC-SA 4.0 |
| `web/src/lib/charts/utils/axes.ts` | `.../charts/d3/utils/axes.ts` | Suppression de la dépendance i18n (`$lib/i18n`, `getLocale()`) — bird-frame n'a pas de système i18n (interface entièrement en français) : le formateur de dates utilise la locale fixe `'fr-FR'`. Le reste (créateur d'axe, grille, formateur d'heures) est repris tel quel. | CC BY-NC-SA 4.0 |
| `web/src/lib/charts/utils/labels.ts` | `.../charts/d3/utils/labels.ts` | Copié tel quel. | CC BY-NC-SA 4.0 |
| `web/src/lib/charts/utils/interactions.ts` | `.../charts/d3/utils/interactions.ts` | Copié tel quel. | CC BY-NC-SA 4.0 |
| `web/src/lib/charts/utils/speciesColor.ts` | `.../charts/d3/utils/speciesColor.ts` | Copié tel quel (un repli `?? '#94a3b8'` ajouté pour satisfaire `noUncheckedIndexedAccess`, sans changer le comportement : la palette n'est jamais vide). | CC BY-NC-SA 4.0 |

## Composants inspirés mais non copiés (pas d'en-tête requis)

- `web/src/lib/components/SpeciesPhoto.svelte` : le mécanisme de retry léger s'inspire de
  l'idée générale d'`image-utils.ts` (birdnet-go-ui) mais la logique est entièrement
  réécrite — le contrat bird-frame diffère (photo générée de façon synchrone, contrat
  `docs/api-contract.md` §6.10), donc pas de copie de code à attribuer.
- `web/src/lib/components/stats/DailyActivityChart.svelte`,
  `HourlyDistributionChart.svelte`, `ConfidenceHistogram.svelte`, `SeasonalHeatmap.svelte` :
  reprennent le **motif** de dessin D3 impératif des graphiques BirdNET-Go (un `$effect`
  qui redessine `chartGroup` à chaque changement de données, capturé via le snippet de
  `BaseChart`), visible par exemple dans `charts/d3/BarChart.svelte` et
  `SeasonalHeatmap.svelte` du fork — mais aucun fichier n'est copié : les formes de données
  (contrat `docs/api-contract.md` §6.14-6.19) et l'essentiel du code de tracé sont propres
  à bird-frame. `web/src/lib/components/stats/SpeciesRankingChart.svelte` n'utilise pas D3
  du tout (barres horizontales en CSS pur, décision documentée dans le composant).
