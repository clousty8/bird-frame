// Routeur maison (History API), volontairement minimal : ce projet n'a que 5 sections,
// une bibliothèque de routage complète serait de la sur-ingénierie. Fichier framework-
// agnostique (aucune rune Svelte ici) pour rester testable en pur TypeScript ; la partie
// réactive (route courante affichée) vit dans App.svelte via onRouteChange().

export type SystemTab = 'nodes' | 'rules' | 'review' | 'false-negatives' | 'thresholds';

export const SYSTEM_TABS: readonly SystemTab[] = [
  'nodes',
  'rules',
  'review',
  'false-negatives',
  'thresholds',
];

export const DEFAULT_SYSTEM_TAB: SystemTab = 'nodes';

export function isSystemTab(value: string): value is SystemTab {
  return (SYSTEM_TABS as readonly string[]).includes(value);
}

export type RouteName = 'dashboard' | 'species-list' | 'species-detail' | 'stats' | 'system' | 'not-found';

export interface RouteMatch {
  name: RouteName;
  /** Paramètres décodés (ex. { name: 'Erithacus rubecula' } ou { tab: 'nodes' }). */
  params: Record<string, string>;
  /** Chemin brut (non décodé), sans la chaîne de requête. */
  path: string;
  /** Chaîne de requête telle quelle, avec le "?" (ou "" si absente). */
  search: string;
}

interface RouteDef {
  name: RouteName;
  /** Segments du motif : un segment commençant par ":" est un paramètre. */
  segments: string[];
}

const ROUTE_DEFS: readonly RouteDef[] = [
  { name: 'dashboard', segments: [] },
  { name: 'dashboard', segments: ['dashboard'] },
  { name: 'species-list', segments: ['species'] },
  { name: 'species-detail', segments: ['species', ':name'] },
  { name: 'stats', segments: ['stats'] },
  { name: 'system', segments: ['system'] },
  { name: 'system', segments: ['system', ':tab'] },
];

function splitSegments(pathname: string): string[] {
  return pathname.split('/').filter((segment) => segment.length > 0);
}

/**
 * Résout un chemin (avec ou sans chaîne de requête) vers la route correspondante.
 * Fonction pure, testable sans DOM.
 */
export function matchRoute(pathWithSearch: string): RouteMatch {
  const questionMarkIndex = pathWithSearch.indexOf('?');
  const rawPath = questionMarkIndex === -1 ? pathWithSearch : pathWithSearch.slice(0, questionMarkIndex);
  const search = questionMarkIndex === -1 ? '' : pathWithSearch.slice(questionMarkIndex);
  const path = rawPath.length > 0 ? rawPath : '/';
  const actualSegments = splitSegments(path);

  for (const def of ROUTE_DEFS) {
    if (def.segments.length !== actualSegments.length) continue;

    const params: Record<string, string> = {};
    let matched = true;

    for (let i = 0; i < def.segments.length; i += 1) {
      const patternSegment = def.segments[i];
      const actualSegment = actualSegments[i];
      if (patternSegment === undefined || actualSegment === undefined) {
        matched = false;
        break;
      }
      if (patternSegment.startsWith(':')) {
        // decodeURIComponent lève une URIError sur une séquence % mal formée (ex. un '%'
        // isolé ou suivi de moins de deux chiffres hexa). Une telle URL ne correspond à
        // aucune route valable : on tombe sur 'not-found' plutôt que de laisser l'exception
        // remonter jusqu'à l'appelant (mount() au chargement initial, listener 'popstate'
        // ensuite), ce qui plantait toute l'application ou figeait silencieusement la page.
        let decoded: string;
        try {
          decoded = decodeURIComponent(actualSegment);
        } catch {
          return { name: 'not-found', params: {}, path, search };
        }
        params[patternSegment.slice(1)] = decoded;
      } else if (patternSegment !== actualSegment) {
        matched = false;
        break;
      }
    }

    if (matched) {
      return { name: def.name, params, path, search };
    }
  }

  return { name: 'not-found', params: {}, path, search };
}

/** Construit le chemin de la fiche espèce (nom scientifique encodé, cf. contrat §1.6). */
export function speciesDetailPath(scientificName: string): string {
  return `/species/${encodeURIComponent(scientificName)}`;
}

/** Construit le chemin d'un sous-onglet système. */
export function systemTabPath(tab: SystemTab): string {
  return `/system/${tab}`;
}

// --- Navigation et abonnement aux changements de route -----------------------------

type RouteListener = (match: RouteMatch) => void;

const listeners = new Set<RouteListener>();

function currentPathWithSearch(): string {
  if (typeof window === 'undefined') return '/';
  return window.location.pathname + window.location.search;
}

export function getCurrentRoute(): RouteMatch {
  return matchRoute(currentPathWithSearch());
}

function notifyListeners(): void {
  const match = getCurrentRoute();
  for (const listener of listeners) listener(match);
}

let popstateBound = false;
function ensurePopstateListener(): void {
  if (popstateBound || typeof window === 'undefined') return;
  window.addEventListener('popstate', notifyListeners);
  popstateBound = true;
}
ensurePopstateListener();

/** S'abonne aux changements de route (navigation programmatique ou bouton retour). */
export function onRouteChange(listener: RouteListener): () => void {
  ensurePopstateListener();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export interface NavigateOptions {
  /** true = history.replaceState (pas de nouvelle entrée d'historique). */
  replace?: boolean;
}

/** Navigation programmatique : pousse (ou remplace) l'URL puis notifie les abonnés. */
export function navigate(path: string, options: NavigateOptions = {}): void {
  if (typeof window === 'undefined') return;
  if (options.replace) {
    window.history.replaceState({}, '', path);
  } else {
    window.history.pushState({}, '', path);
  }
  notifyListeners();
}
