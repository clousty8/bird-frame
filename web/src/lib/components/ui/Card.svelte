<!--
  Adapté de BirdNET-Go (birdnet-go-ui, fork bird-frame, tag 20260823).
  Licence d'origine : CC BY-NC-SA 4.0. Voir web/NOTICE.md.
  Modifications : aucune dépendance en moins à retirer (déjà autonome) ; renommage des
  props `className`/`padding` en `class`/`padding` conservé, adapté au cn.ts local.
-->
<script lang="ts">
  import { cn } from '../../utils/cn';
  import type { Snippet } from 'svelte';

  interface Props {
    title?: string;
    description?: string;
    padding?: boolean;
    class?: string;
    header?: Snippet;
    children?: Snippet;
    footer?: Snippet;
  }

  let { title = '', description, padding = true, class: className = '', header, children, footer }: Props = $props();

  const cardClasses = 'rounded-lg overflow-hidden bg-[var(--color-base-100)] shadow-sm';
</script>

<div class={cn(cardClasses, className)}>
  {#if title || description || header}
    <div class="px-6 py-4">
      {#if header}
        {@render header()}
      {:else}
        {#if title}
          <h3 class="text-xl font-semibold">{title}</h3>
        {/if}
        {#if description}
          <p class="text-sm opacity-70 mt-1 text-[var(--color-base-content)]">{description}</p>
        {/if}
      {/if}
    </div>
  {/if}

  <div class={cn(padding ? (title || description || header ? 'px-6 pb-6' : 'p-6') : '')}>
    {#if children}
      {@render children()}
    {/if}
  </div>

  {#if footer}
    <div class="px-6 pb-6">
      {@render footer()}
    </div>
  {/if}
</div>
