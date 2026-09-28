import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import App from '../src/App.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import { navigate } from '../src/lib/router';

describe('App.svelte — rendu de la coquille', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    vi.spyOn(client, 'getSites').mockResolvedValue({ sites: [] });
    window.history.pushState({}, '', '/dashboard');
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('affiche les quatre sections de navigation', () => {
    render(App);

    expect(screen.getByRole('link', { name: 'Tableau de bord' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Espèces' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Statistiques' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Système' })).toBeInTheDocument();
  });

  it('monte la page de la route courante (tableau de bord par défaut)', () => {
    render(App);

    expect(screen.getByRole('heading', { name: 'Tableau de bord' })).toBeInTheDocument();
  });

  it('bascule de page lors d\'une navigation programmatique', async () => {
    render(App);

    navigate('/stats');

    expect(await screen.findByRole('heading', { name: 'Statistiques' })).toBeInTheDocument();
  });

  it('affiche la page "introuvable" sur une route inconnue', async () => {
    render(App);

    navigate('/ceci-nexiste-pas');

    expect(await screen.findByRole('heading', { name: 'Page introuvable' })).toBeInTheDocument();
  });

  it('monte quand même l\'application (page "introuvable", pas une page blanche) si l\'URL au chargement est mal encodée', () => {
    // Avant le correctif : getCurrentRoute() (appelé par `let route = $state(getCurrentRoute())`
    // dans App.svelte) levait une URIError non rattrapée pendant mount(App, ...) — l'exception
    // remontait jusqu'à l'appel de mount() et cassait le montage de toute l'application (page
    // blanche, rien n'affiché, aucun message d'erreur).
    window.history.pushState({}, '', '/species/Erithacus%20rubecula%2');

    expect(() => render(App)).not.toThrow();
    expect(screen.getByRole('heading', { name: 'Page introuvable' })).toBeInTheDocument();
  });
});
