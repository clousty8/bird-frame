import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import LoginModal from '../src/lib/components/LoginModal.svelte';
import { authStore } from '../src/lib/stores/auth.svelte';
import * as client from '../src/lib/api/client';

async function openAndSubmit(password: string): Promise<void> {
  const input = await screen.findByLabelText('Mot de passe');
  await fireEvent.input(input, { target: { value: password } });
  await fireEvent.click(screen.getByRole('button', { name: 'Se connecter' }));
}

describe('LoginModal', () => {
  beforeEach(() => {
    authStore._resetForTests({ authEnabled: true, authenticated: false });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('n’affiche rien tant que la modale est fermée', () => {
    render(LoginModal);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('connecte et se ferme avec le bon mot de passe', async () => {
    vi.spyOn(client, 'login').mockResolvedValue({ authenticated: true, auth_enabled: true });
    render(LoginModal);
    const waiting = authStore.openLoginModal();

    expect(await screen.findByRole('dialog', { name: 'Connexion' })).toBeInTheDocument();
    await openAndSubmit('le bon');

    await expect(waiting).resolves.toBe(true);
    expect(client.login).toHaveBeenCalledWith('le bon');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('affiche « Mot de passe incorrect. » et reste ouverte', async () => {
    vi.spyOn(client, 'login').mockRejectedValue(
      new client.ApiRequestError('invalid_password', 'Mot de passe incorrect.', 401)
    );
    render(LoginModal);
    void authStore.openLoginModal();

    await openAndSubmit('faux');

    expect(await screen.findByText('Mot de passe incorrect.')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(authStore.authenticated).toBe(false);
  });

  it('affiche le délai quand il y a eu trop de tentatives (429)', async () => {
    vi.spyOn(client, 'login').mockRejectedValue(
      new client.ApiRequestError('too_many_attempts', 'Trop de tentatives.', 429, { retry_after_s: 287 })
    );
    render(LoginModal);
    void authStore.openLoginModal();

    await openAndSubmit('encore faux');

    expect(await screen.findByText('Trop de tentatives. Nouvel essai possible dans 5 min.')).toBeInTheDocument();
  });

  it('se ferme sur « Annuler » et sur Échap sans se connecter', async () => {
    render(LoginModal);

    const first = authStore.openLoginModal();
    await fireEvent.click(await screen.findByRole('button', { name: 'Annuler' }));
    await expect(first).resolves.toBe(false);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    const second = authStore.openLoginModal();
    await screen.findByRole('dialog');
    await fireEvent.keyDown(window, { key: 'Escape' });
    await expect(second).resolves.toBe(false);
  });
});
