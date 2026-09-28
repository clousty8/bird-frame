<!--
  Adapté de BirdNET-Go (birdnet-go-ui, fork bird-frame, tag 20260823).
  Licence d'origine : CC BY-NC-SA 4.0. Voir web/NOTICE.md.
  Modifications : suppression de la dépendance à l'icône @lucide/svelte (chevron SVG
  inline), suppression de l'utilitaire safeGet (non nécessaire ici), classes de thème
  BirdNET-Go (`bg-[var(--color-base-100)]`) conservées telles quelles (mêmes tokens que
  web/src/styles/tailwind.css).
  Corrections bird-frame : la classe `collapsible-open` est posée selon `isOpen` (sans elle
  le CSS garde le contenu à max-height 0, même ouvert) ; classes `collapse*` renommées
  `collapsible*` (l'utilitaire Tailwind v4 `collapse` = `visibility: collapse` rendait tout
  le bloc invisible, en-tête compris) ; identifiant de contenu unique par instance
  (`$props.id()` : plusieurs sections de même titre coexistent, ex. page Système → règles) ;
  contenu fermé rendu `inert` (ni focusable au clavier ni lu par les lecteurs d'écran).
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import { cn } from '../../utils/cn';
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    defaultOpen?: boolean;
    class?: string;
    titleClass?: string;
    contentClass?: string;
    children?: Snippet;
  }

  let {
    title,
    defaultOpen = false,
    class: className = '',
    titleClass = '',
    contentClass = '',
    children,
  }: Props = $props();

  // untrack : capture la valeur initiale sans créer de dépendance réactive sur defaultOpen.
  let isOpen = $state(untrack(() => defaultOpen));

  const uid = $props.id();
  const contentId = `${uid}-content`;

  function toggleOpen(): void {
    isOpen = !isOpen;
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggleOpen();
    }
  }
</script>

<div class={cn('collapsible bg-[var(--color-base-100)] shadow-xs', isOpen && 'collapsible-open', className)}>
  <button
    type="button"
    class={cn('collapsible-title text-lg font-medium w-full text-left', titleClass)}
    onclick={toggleOpen}
    onkeydown={handleKeydown}
    aria-expanded={isOpen}
    aria-controls={contentId}
  >
    <div class="flex items-center justify-between gap-2 w-full">
      <span>{title}</span>
      <svg
        class={cn('size-5 shrink-0 transition-transform duration-200', isOpen ? 'rotate-180' : '')}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
  </button>
  <div id={contentId} class={cn('collapsible-content', contentClass)} aria-hidden={!isOpen} inert={!isOpen}>
    {#if children}
      {@render children()}
    {/if}
  </div>
</div>
