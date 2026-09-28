<script lang="ts">
  // Composant neuf. Modale « mot de passe » (contrat §2.2), montée une seule fois par
  // App.svelte et pilotée par authStore (bouton de l'en-tête, cadenas d'un enregistrement,
  // mention « Connexion requise », ou toute action refusée en 401).
  import { authStore } from '../stores/auth.svelte';
  import { ApiRequestError } from '../api/client';
  import Button from './ui/Button.svelte';
  import ErrorAlert from './ui/ErrorAlert.svelte';

  let password = $state('');
  let submitting = $state(false);
  let error = $state<string | null>(null);
  let inputEl: HTMLInputElement | undefined = $state();

  // Chaque ouverture repart d'un formulaire vide, curseur dans le champ.
  $effect(() => {
    if (!authStore.modalOpen) return;
    password = '';
    error = null;
    submitting = false;
    queueMicrotask(() => inputEl?.focus());
  });

  function messageFor(err: unknown): string {
    if (!(err instanceof ApiRequestError)) return 'Erreur inconnue lors de la connexion.';
    if (err.code === 'invalid_password') return 'Mot de passe incorrect.';
    if (err.code === 'too_many_attempts') {
      const details = err.details as { retry_after_s?: number } | null;
      const minutes = details?.retry_after_s ? Math.max(1, Math.ceil(details.retry_after_s / 60)) : null;
      return minutes
        ? `Trop de tentatives. Nouvel essai possible dans ${minutes} min.`
        : 'Trop de tentatives. Réessayer dans quelques minutes.';
    }
    return err.message;
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!password || submitting) return;
    submitting = true;
    error = null;
    try {
      await authStore.login(password);
    } catch (err) {
      error = messageFor(err);
      password = '';
      inputEl?.focus();
    } finally {
      submitting = false;
    }
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && authStore.modalOpen && !submitting) authStore.cancelLogin();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if authStore.modalOpen}
  <div class="modal modal-open" role="presentation">
    <div class="modal-box w-full max-w-sm" role="dialog" aria-modal="true" aria-labelledby="login-modal-title">
      <h2 id="login-modal-title" class="text-lg font-semibold">Connexion</h2>
      <p class="text-sm text-muted mt-1">
        Le mot de passe du cadre permet de modifier les réglages et d'écouter les enregistrements.
        La consultation reste libre.
      </p>

      <form class="mt-4 space-y-3" onsubmit={submit}>
        <div>
          <label for="login-password" class="block text-sm font-medium mb-1">Mot de passe</label>
          <input
            id="login-password"
            type="password"
            class="input input-bordered w-full"
            autocomplete="current-password"
            required
            bind:this={inputEl}
            bind:value={password}
            disabled={submitting}
          />
        </div>

        {#if error}
          <ErrorAlert type="error" message={error} />
        {/if}

        <div class="modal-action">
          <Button type="button" variant="ghost" onclick={() => authStore.cancelLogin()} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting || !password}>
            {submitting ? 'Connexion…' : 'Se connecter'}
          </Button>
        </div>
      </form>
    </div>
  </div>
{/if}
