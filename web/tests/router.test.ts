import { describe, it, expect, beforeEach } from 'vitest';
import {
  matchRoute,
  speciesDetailPath,
  systemTabPath,
  isSystemTab,
  navigate,
  getCurrentRoute,
  onRouteChange,
} from '../src/lib/router';

describe('matchRoute — résolution des routes et des paramètres', () => {
  it('résout "/" comme le tableau de bord', () => {
    expect(matchRoute('/')).toEqual({ name: 'dashboard', params: {}, path: '/', search: '' });
  });

  it('résout "/dashboard"', () => {
    const match = matchRoute('/dashboard');
    expect(match.name).toBe('dashboard');
    expect(match.params).toEqual({});
  });

  it('résout "/species" (liste)', () => {
    expect(matchRoute('/species').name).toBe('species-list');
  });

  it('résout "/species/:name" et décode le paramètre (espace encodé en %20)', () => {
    const match = matchRoute('/species/Erithacus%20rubecula');
    expect(match.name).toBe('species-detail');
    expect(match.params).toEqual({ name: 'Erithacus rubecula' });
  });

  it('résout "/stats"', () => {
    expect(matchRoute('/stats').name).toBe('stats');
  });

  it('résout "/system" sans sous-onglet', () => {
    const match = matchRoute('/system');
    expect(match.name).toBe('system');
    expect(match.params).toEqual({});
  });

  it('résout "/system/:tab"', () => {
    const match = matchRoute('/system/rules');
    expect(match.name).toBe('system');
    expect(match.params).toEqual({ tab: 'rules' });
  });

  it('sépare la chaîne de requête du chemin', () => {
    const match = matchRoute('/species?q=merle&limit=10');
    expect(match.name).toBe('species-list');
    expect(match.path).toBe('/species');
    expect(match.search).toBe('?q=merle&limit=10');
  });

  it('retombe sur "not-found" pour un chemin inconnu', () => {
    expect(matchRoute('/nawak').name).toBe('not-found');
  });

  it('retombe sur "not-found" pour un chemin plus profond que prévu', () => {
    expect(matchRoute('/species/Erithacus%20rubecula/sites/pornic/top-clips').name).toBe('not-found');
  });

  it('retombe sur "not-found" (sans lever d\'URIError) pour un "%" isolé mal encodé', () => {
    // decodeURIComponent lève une URIError sur ce genre de séquence : sans le try/catch,
    // cette exception remontait jusqu'à l'appelant (mount() au chargement initial) et
    // cassait le montage de toute l'application (page blanche).
    expect(() => matchRoute('/species/Erithacus%20rubecula%2')).not.toThrow();
    expect(matchRoute('/species/Erithacus%20rubecula%2').name).toBe('not-found');
  });

  it('retombe sur "not-found" pour un "%" seul, sans chiffres hexa', () => {
    expect(() => matchRoute('/species/%')).not.toThrow();
    expect(matchRoute('/species/%').name).toBe('not-found');
  });

  it('retombe sur "not-found" pour une séquence % suivie de caractères non hexadécimaux', () => {
    expect(() => matchRoute('/species/%zz')).not.toThrow();
    expect(matchRoute('/species/%zz').name).toBe('not-found');
  });
});

describe('isSystemTab', () => {
  it('reconnaît les sous-onglets valides', () => {
    expect(isSystemTab('nodes')).toBe(true);
    expect(isSystemTab('false-negatives')).toBe(true);
  });

  it('rejette un sous-onglet inconnu', () => {
    expect(isSystemTab('bidule')).toBe(false);
  });
});

describe('speciesDetailPath / systemTabPath', () => {
  it('encode le nom scientifique dans le chemin espèce', () => {
    expect(speciesDetailPath('Erithacus rubecula')).toBe('/species/Erithacus%20rubecula');
  });

  it('construit le chemin d\'un sous-onglet système', () => {
    expect(systemTabPath('thresholds')).toBe('/system/thresholds');
  });
});

describe('navigate / onRouteChange — navigation programmatique', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/dashboard');
  });

  it('met à jour location et notifie les abonnés', () => {
    const seen: string[] = [];
    const unsubscribe = onRouteChange((match) => seen.push(match.name));

    navigate('/species');

    expect(window.location.pathname).toBe('/species');
    expect(seen).toEqual(['species-list']);
    expect(getCurrentRoute().name).toBe('species-list');

    unsubscribe();
  });

  it('ne notifie plus après désabonnement', () => {
    const seen: string[] = [];
    const unsubscribe = onRouteChange((match) => seen.push(match.name));
    unsubscribe();

    navigate('/stats');

    expect(seen).toEqual([]);
  });

  it('replace: true ne pousse pas de nouvelle entrée d\'historique', () => {
    const initialLength = window.history.length;
    navigate('/species', { replace: true });
    expect(window.history.length).toBe(initialLength);
    expect(window.location.pathname).toBe('/species');
  });

  it('ne plante pas et notifie "not-found" sur un retour arrière (popstate) vers une URL malformée', () => {
    // Avant le correctif : l'URIError levée dans le listener 'popstate' interrompait
    // silencieusement la boucle for..of de notifyListeners() — l'URL changeait dans la barre
    // d'adresse mais le contenu affiché restait figé sur l'ancienne page, sans le moindre
    // indicateur d'erreur.
    const seen: string[] = [];
    const unsubscribe = onRouteChange((match) => seen.push(match.name));

    window.history.pushState({}, '', '/species/Erithacus%20rubecula%2');
    expect(() => window.dispatchEvent(new PopStateEvent('popstate'))).not.toThrow();

    expect(seen).toEqual(['not-found']);
    expect(getCurrentRoute().name).toBe('not-found');

    unsubscribe();
  });
});
