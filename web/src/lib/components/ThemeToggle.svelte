<script lang="ts">
  // Composant neuf. Bouton unique qui fait défiler préférence système → clair → sombre.
  import { themeStore } from '../stores/theme.svelte';

  const LABELS = {
    system: 'Thème : automatique (suit le système)',
    light: 'Thème : clair',
    dark: 'Thème : sombre',
  } as const;
</script>

<button
  type="button"
  class="btn btn-ghost btn-sm"
  onclick={() => themeStore.cycle()}
  title={LABELS[themeStore.preference]}
  aria-label={LABELS[themeStore.preference]}
>
  {#if themeStore.preference === 'system'}
    <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <rect x="3" y="4" width="18" height="13" rx="1.5" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  {:else if themeStore.preference === 'light'}
    <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
    </svg>
  {:else}
    <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z" />
    </svg>
  {/if}
</button>
