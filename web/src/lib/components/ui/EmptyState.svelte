<!--
  Adapté de BirdNET-Go (birdnet-go-ui, fork bird-frame, tag 20260823).
  Licence d'origine : CC BY-NC-SA 4.0. Voir web/NOTICE.md.
  Modifications : suppression de la dépendance à l'icône @lucide/svelte (icône "boîte
  vide" en SVG inline), bouton d'action utilisant les classes .btn génériques copiées
  dans web/src/styles/tailwind.css plutôt qu'un import de composant.
-->
<script lang="ts">
  import { cn } from '../../utils/cn';
  import type { Snippet } from 'svelte';

  interface ActionConfig {
    label: string;
    onClick: () => void;
  }

  interface Props {
    icon?: Snippet;
    title?: string;
    description?: string;
    action?: ActionConfig | null;
    class?: string;
    children?: Snippet;
  }

  let { icon, title = '', description = '', action = null, class: className = '', children }: Props = $props();
</script>

<div class={cn('flex flex-col items-center justify-center py-12 px-4 text-center', className)}>
  {#if icon}
    {@render icon()}
  {:else}
    <svg
      class="size-16 opacity-20"
      style="color: var(--color-base-content)"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      aria-hidden="true"
    >
      <path
        d="M3 9l1.5-5A1 1 0 0 1 5.45 3h13.1a1 1 0 0 1 .95.68L21 9M3 9v9a1.5 1.5 0 0 0 1.5 1.5h15A1.5 1.5 0 0 0 21 18V9M3 9h18M9 13.5a3 3 0 0 0 6 0"
      />
    </svg>
  {/if}

  {#if title}
    <h3 class="mt-4 text-lg font-semibold text-[var(--color-base-content)]">{title}</h3>
  {/if}

  {#if description}
    <p class="mt-2 text-sm opacity-70 max-w-md" style:color="var(--color-base-content)">{description}</p>
  {/if}

  {#if children}
    <div class="mt-4">
      {@render children()}
    </div>
  {/if}

  {#if action}
    <div class="mt-6">
      <button type="button" class="btn btn-primary" onclick={action.onClick}>
        {action.label}
      </button>
    </div>
  {/if}
</div>
