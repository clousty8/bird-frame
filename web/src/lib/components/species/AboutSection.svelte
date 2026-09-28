<script lang="ts">
  // Section « À propos » : brief (summary_fr), puis un tableau de faits, sources cliquables
  // + lien Wikipédia FR/EN. Si la fiche n'a pas de partie rédactionnelle (has_sheet=false),
  // affiche proprement « fiche en cours de rédaction » — avec, en secours, l'extrait
  // Wikipédia déjà renvoyé par le serveur (contrat §6.9 : "le frontend affiche alors
  // wikipedia.fr.extract").
  import type { SpeciesDetail } from '../../api/types';
  import { buildSourceLinks } from './sources';

  interface Props {
    detail: SpeciesDetail;
  }

  let { detail }: Props = $props();

  let sourceLinks = $derived(buildSourceLinks(detail.wikipedia, detail.sources));
</script>

<section class="flex flex-col gap-4">
  <h2 class="text-xl font-semibold">À propos</h2>

  {#if detail.has_sheet && detail.summary_fr}
    <p class="leading-relaxed">{detail.summary_fr}</p>
  {:else}
    <p class="text-muted italic">Fiche en cours de rédaction.</p>
    {#if detail.wikipedia.fr?.extract}
      <p class="leading-relaxed">{detail.wikipedia.fr.extract}</p>
    {/if}
  {/if}

  {#if detail.has_sheet}
    <dl class="grid gap-x-6 gap-y-3 sm:grid-cols-2 text-sm">
      {#if detail.habitat}
        <div>
          <dt class="font-medium">Habitat</dt>
          <dd class="text-muted">{detail.habitat}</dd>
        </div>
      {/if}
      {#if detail.diet}
        <div>
          <dt class="font-medium">Régime</dt>
          <dd class="text-muted">{detail.diet}</dd>
        </div>
      {/if}
      {#if detail.activity_pattern}
        <div>
          <dt class="font-medium">Activité</dt>
          <dd class="text-muted capitalize">{detail.activity_pattern}</dd>
        </div>
      {/if}
      {#if detail.migration}
        <div>
          <dt class="font-medium">Migration</dt>
          <dd class="text-muted">
            {detail.migration.statut}
            {#if detail.migration.hiverne}<br />Hiverne : {detail.migration.hiverne}{/if}
            {#if detail.migration.niche}<br />Niche : {detail.migration.niche}{/if}
            {#if detail.migration.passage}<br />Passage : {detail.migration.passage}{/if}
          </dd>
        </div>
      {/if}
      {#if detail.seasonality_fr}
        <div>
          <dt class="font-medium">Quand la voir / l'entendre en France</dt>
          <dd class="text-muted">{detail.seasonality_fr}</dd>
        </div>
      {/if}
      {#if detail.song_fr}
        <div>
          <dt class="font-medium">Chant</dt>
          <dd class="text-muted">{detail.song_fr}</dd>
        </div>
      {/if}
      {#if detail.rarity_note}
        <div>
          <dt class="font-medium">Rareté</dt>
          <dd class="text-muted">{detail.rarity_note}</dd>
        </div>
      {/if}
      {#if detail.lookalikes.length > 0}
        <div class="sm:col-span-2">
          <dt class="font-medium">Espèces ressemblantes</dt>
          <dd class="text-muted">
            <ul class="list-disc list-inside">
              {#each detail.lookalikes as lookalike (lookalike.scientific_name)}
                <li>{lookalike.common_name_fr ?? lookalike.scientific_name} — {lookalike.why_fr}</li>
              {/each}
            </ul>
          </dd>
        </div>
      {/if}
      {#if detail.fun_facts.length > 0}
        <div class="sm:col-span-2">
          <dt class="font-medium">Anecdotes</dt>
          <dd class="text-muted">
            <ul class="list-disc list-inside">
              {#each detail.fun_facts as fact, index (index)}
                <li>{fact}</li>
              {/each}
            </ul>
          </dd>
        </div>
      {/if}
    </dl>
  {/if}

  {#if sourceLinks.length > 0}
    <div class="text-sm">
      <p class="font-medium mb-1">Sources</p>
      <ul class="flex flex-col gap-0.5">
        {#each sourceLinks as source (source.title)}
          <li class="break-words">
            {#if source.href}
              <a class="link link-primary" href={source.href} title={source.title} target="_blank" rel="noopener noreferrer">{source.label}</a>
            {:else}
              <span class="text-muted">{source.label}</span>
            {/if}
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</section>
