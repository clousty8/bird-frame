import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import RulesTab from '../src/lib/components/system/RulesTab.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import * as client from '../src/lib/api/client';
import type { SpeciesRule } from '../src/lib/api/types';

function makeRule(overrides: Partial<SpeciesRule> = {}): SpeciesRule {
  return {
    scientific_name: 'Columba livia',
    common_name_fr: 'Pigeon biset',
    rule: 'impossible',
    threshold_override: null,
    redirect_to_scientific_name: null,
    redirect_to_common_name_fr: null,
    reason: 'Confusion avec le ramier',
    updated_at: '2026-09-27T15:00:00Z',
    sync_status: 'applied',
    commands: [],
    ...overrides,
  };
}

describe('RulesTab', () => {
  beforeEach(() => {
    siteStore._resetForTests();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("invite à choisir un site quand aucun n'est sélectionné", () => {
    render(RulesTab);

    expect(screen.getByText('Aucun site sélectionné')).toBeInTheDocument();
  });

  it('charge et affiche les règles du site courant', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getSpeciesRules').mockResolvedValue({ site_slug: 'pornic', rules: [makeRule()] });

    render(RulesTab);

    expect(await screen.findByText('Pigeon biset')).toBeInTheDocument();
    expect(screen.getByText('impossible ici')).toBeInTheDocument();
    expect(screen.getByText('appliquée')).toBeInTheDocument();
    expect(client.getSpeciesRules).toHaveBeenCalledWith('pornic');
  });

  it("affiche un état vide quand le site n'a aucune règle", async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getSpeciesRules').mockResolvedValue({ site_slug: 'pornic', rules: [] });

    render(RulesTab);

    expect(await screen.findByText('Aucune règle')).toBeInTheDocument();
  });

  it('remonte une erreur de chargement (jamais avalée)', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getSpeciesRules').mockRejectedValue(
      new client.ApiRequestError('internal_error', 'Erreur serveur.', 500)
    );

    render(RulesTab);

    expect(await screen.findByText('Erreur serveur.')).toBeInTheDocument();
  });

  it('supprime une règle après confirmation en deux temps', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getSpeciesRules')
      .mockResolvedValueOnce({ site_slug: 'pornic', rules: [makeRule()] })
      .mockResolvedValueOnce({ site_slug: 'pornic', rules: [] });
    vi.spyOn(client, 'deleteSpeciesRule').mockResolvedValue({ deleted: true, commands: [] });

    render(RulesTab);

    await screen.findByText('Pigeon biset');

    await fireEvent.click(screen.getByRole('button', { name: 'Supprimer' }));
    // Deuxième temps : le bouton "Supprimer" se transforme en "Confirmer" / "Annuler".
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }));

    expect(client.deleteSpeciesRule).toHaveBeenCalledWith('pornic', 'Columba livia');
    expect(await screen.findByText('Aucune règle')).toBeInTheDocument();
  });

  it('pré-remplit le formulaire quand on clique sur « Modifier »', async () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getSpeciesRules').mockResolvedValue({
      site_slug: 'pornic',
      rules: [makeRule({ rule: 'present', threshold_override: 0.35, reason: 'Nicheur au jardin' })],
    });

    render(RulesTab);

    await screen.findByText('Pigeon biset');
    await fireEvent.click(screen.getByRole('button', { name: 'Modifier' }));

    // Le champ espèce du formulaire passe en mode "déjà sélectionné" (bouton Changer).
    expect(screen.getAllByText('Pigeon biset').length).toBeGreaterThan(1);
    expect(screen.getByDisplayValue('0.35')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Nicheur au jardin')).toBeInTheDocument();
  });

  it("refuse de valider sans espèce choisie (bouton d'enregistrement désactivé)", () => {
    siteStore.select('pornic');
    vi.spyOn(client, 'getSpeciesRules').mockResolvedValue({ site_slug: 'pornic', rules: [] });

    render(RulesTab);

    expect(screen.getByRole('button', { name: 'Enregistrer la règle' })).toBeDisabled();
  });
});
