<script lang="ts">
  // Section « Sources » en fin de fiche (comme les références d'un article Wikipédia) :
  // Wikipédia FR puis EN, puis les autres sources de la fiche, dédoublonnées (sources.ts).
  import type { SourceLink } from './sources';

  interface Props {
    links: SourceLink[];
  }

  let { links }: Props = $props();
</script>

{#if links.length > 0}
  <section id="sources" class="wiki-section">
    <h2 class="wiki-h2">Sources</h2>
    <ol class="list-decimal pl-6 flex flex-col gap-1 text-sm">
      {#each links as source (source.title)}
        <li class="break-words">
          {#if source.href}
            <a class="link link-primary" href={source.href} title={source.title} target="_blank" rel="noopener noreferrer">{source.label}</a>
          {:else}
            <span class="text-muted">{source.label}</span>
          {/if}
        </li>
      {/each}
    </ol>
  </section>
{/if}
