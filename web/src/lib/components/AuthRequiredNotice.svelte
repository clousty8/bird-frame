<script lang="ts">
  // Composant neuf. Mention « Connexion requise » + lien qui ouvre la modale (contrat §2.2),
  // à placer au-dessus des contrôles désactivés d'une page. Ne rend rien quand l'accès est
  // ouvert (session active, ou authentification désactivée en dev).
  import { authStore } from '../stores/auth.svelte';

  interface Props {
    /** Ce que la connexion permettrait, ex. « ajouter ou modifier des règles ». */
    action?: string;
  }

  let { action = 'modifier' }: Props = $props();
</script>

{#if !authStore.unlocked}
  <p
    class="flex flex-wrap items-center gap-x-1.5 gap-y-1 max-w-3xl rounded-lg border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 px-3 py-2 text-sm"
  >
    <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
    <span class="font-medium">Connexion requise</span>
    <span>pour {action} —</span>
    <button type="button" class="link link-primary" onclick={() => void authStore.openLoginModal()}>
      se connecter
    </button>
  </p>
{/if}
