<!--
  Adapté de BirdNET-Go (birdnet-go-ui, fork bird-frame, tag 20260823).
  Licence d'origine : CC BY-NC-SA 4.0. Voir web/NOTICE.md.
  Modifications : suppression des icônes @lucide/svelte (SVG inline), suppression de la
  dépendance i18n (`t('common.aria.dismissAlert')` → libellé français en dur), suppression
  du logger BirdNET-Go (`console.error` direct : toute erreur reste visible, jamais
  avalée), suppression de l'utilitaire safeGet (accès direct, sûr).
-->
<script lang="ts">
  import { cn } from '../../utils/cn';
  import type { Snippet } from 'svelte';

  type AlertType = 'error' | 'warning' | 'info' | 'success';

  interface Props {
    message?: string;
    type?: AlertType;
    dismissible?: boolean;
    onDismiss?: () => void;
    class?: string;
    children?: Snippet;
  }

  let { message = '', type = 'error', dismissible = false, onDismiss = () => {}, class: className = '', children }: Props =
    $props();

  let isVisible = $state(true);

  const baseClasses = 'flex items-start gap-3 p-3 rounded-lg text-sm text-[var(--color-base-content)]';

  const typeClasses: Record<AlertType, string> = {
    error:
      'bg-[color-mix(in_srgb,var(--color-error)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-error)_30%,transparent)]',
    warning:
      'bg-[color-mix(in_srgb,var(--color-warning)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-warning)_30%,transparent)]',
    info: 'bg-[color-mix(in_srgb,var(--color-info)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-info)_30%,transparent)]',
    success:
      'bg-[color-mix(in_srgb,var(--color-success)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-success)_30%,transparent)]',
  };

  const iconColorClasses: Record<AlertType, string> = {
    error: 'text-[var(--color-error)]',
    warning: 'text-[var(--color-warning)]',
    info: 'text-[var(--color-info)]',
    success: 'text-[var(--color-success)]',
  };

  function handleDismiss(): void {
    isVisible = false;
    try {
      onDismiss();
    } catch (error) {
      // Ne jamais avaler une erreur du callback appelant : journalisée pour rester visible en debug.
      console.error('[bird-frame] erreur dans le callback onDismiss de ErrorAlert :', error);
    }
  }
</script>

{#if isVisible}
  <div class={cn(baseClasses, typeClasses[type], className)} role="alert">
    <svg
      class={cn('size-5 shrink-0 mt-0.5', iconColorClasses[type])}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      {#if type === 'error'}
        <circle cx="12" cy="12" r="9" />
        <path d="M9.5 9.5l5 5M14.5 9.5l-5 5" />
      {:else if type === 'warning'}
        <path d="M12 3.5l9.5 16.5H2.5L12 3.5z" />
        <path d="M12 10v4M12 17h.01" />
      {:else if type === 'info'}
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5M12 8h.01" />
      {:else}
        <circle cx="12" cy="12" r="9" />
        <path d="M8.5 12.5l2.5 2.5 5-5" />
      {/if}
    </svg>

    <span class="min-w-0">
      {#if children}
        {@render children()}
      {:else}
        {message}
      {/if}
    </span>

    {#if dismissible}
      <button
        type="button"
        class="ml-auto inline-flex items-center justify-center p-1.5 rounded-md bg-transparent hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
        onclick={handleDismiss}
        aria-label="Fermer cette alerte"
      >
        <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    {/if}
  </div>
{/if}
