<script lang="ts">
  // Section « À propos », façon Wikipédia : une vraie introduction (chapeau mis en valeur puis
  // paragraphes) et des sous-sections titrées rédigées en phrases — « Où le trouver »,
  // « Alimentation », « Mode de vie », « Migration et saisons », « Son chant », « À ne pas
  // confondre avec », « Le saviez-vous ? ». Tout le texte vient de `aboutContent()`
  // (speciesProse.ts), qui retire au passage les mentions techniques des fiches générées.
  // Sans partie rédactionnelle (has_sheet=false) : « Fiche en cours de rédaction » + extrait
  // Wikipédia (contrat §6.9). Les sources sont en fin de page (SourcesSection.svelte).
  import type { Snippet } from 'svelte';
  import type { SpeciesDetail } from '../../api/types';
  import Link from '../../Link.svelte';
  import { speciesDetailPath } from '../../router';
  import type { SpeciesNoun } from './frenchGrammar';
  import type { AboutContent } from './speciesProse';

  interface Props {
    detail: SpeciesDetail;
    content: AboutContent;
    noun: SpeciesNoun;
    /** Encadré « En bref » flottant à droite sur grand écran. */
    aside?: Snippet;
  }

  let { detail, content, noun, aside }: Props = $props();
</script>

<section id="a-propos" class="wiki-section about">
  <h2 class="wiki-h2">À propos</h2>
  {@render aside?.()}

  <div class="wiki-prose">
    {#if content.intro}
      <p class="wiki-lead">{content.intro.lead}</p>
      {#each content.intro.rest as paragraph, index (index)}
        <p>{paragraph}</p>
      {/each}
    {:else}
      <p class="text-muted italic">Fiche en cours de rédaction.</p>
      {#if detail.wikipedia.fr?.extract}
        <p>{detail.wikipedia.fr.extract}</p>
      {/if}
    {/if}
  </div>

  {#if content.where}
    <h3 id="ou-le-trouver" class="wiki-h3">Où {noun.object} trouver</h3>
    <p class="wiki-prose">{content.where}</p>
  {/if}

  {#if content.diet}
    <h3 id="alimentation" class="wiki-h3">Alimentation</h3>
    <p class="wiki-prose">{content.diet}</p>
  {/if}

  {#if content.activity}
    <h3 id="mode-de-vie" class="wiki-h3">Mode de vie</h3>
    <p class="wiki-prose">{content.activity}</p>
  {/if}

  {#if content.migration.length > 0}
    <h3 id="migration" class="wiki-h3">Migration et saisons</h3>
    <div class="wiki-prose">
      {#each content.migration as paragraph, index (index)}
        <p>{paragraph}</p>
      {/each}
    </div>
  {/if}

  {#if content.song}
    <h3 id="chant" class="wiki-h3">Son chant</h3>
    <p class="wiki-prose">{content.song}</p>
  {/if}

  {#if content.lookalikes.length > 0}
    <h3 id="confusions" class="wiki-h3">À ne pas confondre avec</h3>
    <ul class="wiki-prose wiki-list">
      {#each content.lookalikes as lookalike (lookalike.scientificName)}
        <li>
          {#if lookalike.hasPage}
            <Link to={speciesDetailPath(lookalike.scientificName)} class="link link-primary font-medium">{lookalike.name}</Link>
          {:else}
            <span class="font-medium">{lookalike.name}</span>
          {/if}
          {#if lookalike.why}<span> — {lookalike.why}</span>{/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if content.facts.length > 0}
    <h3 id="anecdotes" class="wiki-h3">Le saviez-vous ?</h3>
    <ul class="wiki-prose wiki-list">
      {#each content.facts as fact, index (index)}
        <li>{fact}</li>
      {/each}
    </ul>
  {/if}
</section>
