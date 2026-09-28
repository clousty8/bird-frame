<script lang="ts">
  // Composant neuf. Menu déroulant du site courant, affiche le nom + l'état en ligne du
  // nœud principal quand il est disponible (Site.online, contrat §6.2).
  import { onMount } from 'svelte';
  import { siteStore } from '../stores/site.svelte';

  let open = $state(false);
  let containerEl: HTMLDivElement | undefined;

  onMount(() => {
    void siteStore.load();
  });

  $effect(() => {
    if (!open) return;
    function handleOutsideClick(event: MouseEvent): void {
      if (event.target instanceof Node && containerEl && !containerEl.contains(event.target)) {
        open = false;
      }
    }
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  });

  function toggle(): void {
    open = !open;
  }

  function choose(slug: string): void {
    siteStore.select(slug);
    open = false;
  }
</script>

<div class="dropdown" class:dropdown-open={open} bind:this={containerEl}>
  <button
    type="button"
    class="btn btn-ghost btn-sm"
    onclick={toggle}
    aria-haspopup="listbox"
    aria-expanded={open}
  >
    {#if siteStore.selectedSite}
      <span
        class="inline-block size-2 rounded-full"
        class:bg-success={siteStore.selectedSite.online}
        class:bg-base-300={!siteStore.selectedSite.online}
        aria-hidden="true"
      ></span>
      {siteStore.selectedSite.name}
    {:else if siteStore.loading}
      Chargement des sites…
    {:else if siteStore.error}
      Sites indisponibles
    {:else}
      Aucun site
    {/if}
    <svg class="size-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path d="M6 9l6 6 6-6" />
    </svg>
  </button>

  {#if open}
    <ul class="dropdown-content menu" role="listbox">
      {#each siteStore.sites as site (site.slug)}
        <li>
          <button
            type="button"
            role="option"
            class:active={site.slug === siteStore.selectedSlug}
            aria-selected={site.slug === siteStore.selectedSlug}
            onclick={() => choose(site.slug)}
          >
            <span
              class="inline-block size-2 rounded-full"
              class:bg-success={site.online}
              class:bg-base-300={!site.online}
              aria-hidden="true"
            ></span>
            {site.name}
          </button>
        </li>
      {:else}
        <li>
          <span class="text-muted text-sm px-2 py-1">
            {siteStore.loading ? 'Chargement…' : 'Aucun site enregistré'}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

{#if siteStore.error}
  <span class="text-xs text-error hidden md:inline" role="alert">{siteStore.error}</span>
{/if}
