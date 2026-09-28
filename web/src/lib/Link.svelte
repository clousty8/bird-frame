<script lang="ts">
  import type { Snippet } from 'svelte';
  import { navigate } from './router';

  interface Props {
    to: string;
    replace?: boolean;
    class?: string;
    children?: Snippet;
  }

  let { to, replace = false, class: className = '', children }: Props = $props();

  function handleClick(event: MouseEvent): void {
    // Laisse le navigateur gérer les clics modifiés (Ctrl/Cmd/Shift/Alt, clic molette) :
    // c'est l'utilisateur qui demande explicitement un nouvel onglet/une nouvelle fenêtre.
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to, { replace });
  }
</script>

<a href={to} class={className} onclick={handleClick}>
  {#if children}
    {@render children()}
  {/if}
</a>
