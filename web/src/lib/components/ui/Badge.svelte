<!--
  Adapté de BirdNET-Go (birdnet-go-ui, fork bird-frame, tag 20260823).
  Licence d'origine : CC BY-NC-SA 4.0. Voir web/NOTICE.md.
  Modifications : suppression de l'utilitaire safeGet (accès direct aux tables de
  classes, sûr ici car `variant`/`size` sont des unions fermées vérifiées par TypeScript) ;
  texte des variantes `outline` d'état en `--color-*-text` (contraste AA, voir tailwind.css).
-->
<script lang="ts">
  import { cn } from '../../utils/cn';
  import type { Snippet } from 'svelte';

  type BadgeVariant = 'primary' | 'secondary' | 'accent' | 'neutral' | 'info' | 'success' | 'warning' | 'error' | 'ghost';
  type BadgeSize = 'xs' | 'sm' | 'md' | 'lg';

  interface Props {
    variant?: BadgeVariant;
    size?: BadgeSize;
    text?: string;
    outline?: boolean;
    class?: string;
    children?: Snippet;
  }

  let { variant = 'neutral', size = 'md', text = '', outline = false, class: className = '', children }: Props = $props();

  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-full whitespace-nowrap';

  let variantClasses = $derived<Record<BadgeVariant, string>>({
    primary: outline
      ? 'bg-transparent border border-[var(--color-primary)] text-[var(--color-primary)]'
      : 'bg-[var(--color-primary)] text-[var(--color-primary-content)]',
    secondary: outline
      ? 'bg-transparent border border-[var(--color-secondary)] text-[var(--color-secondary)]'
      : 'bg-[var(--color-secondary)] text-[var(--color-secondary-content)]',
    accent: outline
      ? 'bg-transparent border border-[var(--color-accent)] text-[var(--color-accent)]'
      : 'bg-[var(--color-accent)] text-[var(--color-accent-content)]',
    neutral: outline ? 'bg-transparent border border-current' : 'bg-[var(--color-base-300)] text-[var(--color-base-content)]',
    info: outline
      ? 'bg-transparent border border-[var(--color-info)] text-[var(--color-info-text)]'
      : 'bg-[var(--color-info)] text-[var(--color-info-content)]',
    success: outline
      ? 'bg-transparent border border-[var(--color-success)] text-[var(--color-success-text)]'
      : 'bg-[var(--color-success)] text-[var(--color-success-content)]',
    warning: outline
      ? 'bg-transparent border border-[var(--color-warning)] text-[var(--color-warning-text)]'
      : 'bg-[var(--color-warning)] text-[var(--color-warning-content)]',
    error: outline
      ? 'bg-transparent border border-[var(--color-error)] text-[var(--color-error-text)]'
      : 'bg-[var(--color-error)] text-[var(--color-error-content)]',
    ghost: 'bg-black/5 dark:bg-white/5 text-[var(--color-base-content)]',
  });

  const sizeClasses: Record<BadgeSize, string> = {
    xs: 'px-1 text-[0.625rem] leading-[0.875rem]',
    sm: 'px-1.5 py-px text-[0.6875rem] leading-[0.9375rem]',
    md: 'px-2 py-0.5 text-xs leading-4',
    lg: 'px-2.5 py-1 text-sm leading-[1.125rem]',
  };
</script>

<span class={cn(baseClasses, variantClasses[variant], sizeClasses[size], className)}>
  {#if children}
    {@render children()}
  {:else}
    {text}
  {/if}
</span>
