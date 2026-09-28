<script lang="ts">
  // Composant neuf. Bouton « Se connecter » / « Se déconnecter » de l'en-tête (contrat §2.2).
  // Rien n'est affiché quand l'authentification est désactivée (serveur de dev sans mot de passe).
  import { authStore } from '../stores/auth.svelte';

  let loggingOut = $state(false);

  async function handleLogout(): Promise<void> {
    loggingOut = true;
    try {
      await authStore.logout();
    } finally {
      loggingOut = false;
    }
  }
</script>

{#if authStore.authEnabled}
  {#if authStore.authenticated}
    <button type="button" class="btn btn-ghost btn-sm" onclick={handleLogout} disabled={loggingOut}>
      {loggingOut ? 'Déconnexion…' : 'Se déconnecter'}
    </button>
  {:else}
    <button type="button" class="btn btn-ghost btn-sm" onclick={() => void authStore.openLoginModal()}>
      <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
        <rect x="5" y="11" width="14" height="10" rx="2" />
        <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
      Se connecter
    </button>
  {/if}
{/if}

{#if authStore.error}
  <span class="text-xs text-error hidden md:inline" role="alert">{authStore.error}</span>
{/if}
