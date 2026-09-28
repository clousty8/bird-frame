<script lang="ts">
  // Section « Peut-on l'entendre à <site> ? » (remplace l'ancienne « Plausibilité ici ») :
  // pour quelqu'un qui ne connaît rien aux oiseaux, à BirdNET ni à l'informatique. Données :
  // `local_presence_by_site` (contrat §6.9) — un niveau par mois d'après les observations des
  // naturalistes autour de la ville de référence la plus proche du site. Affiche une frise des
  // 12 mois colorée par niveau (mois en cours encadré), une légende en mots et une phrase de
  // conclusion adaptée au site et au mois (localPresence.ts). Aucun score ni pourcentage.
  // Site : celui du sélecteur global par défaut, modifiable ici sans changer le site global.
  import { siteStore } from '../../stores/site.svelte';
  import type { SpeciesDetail } from '../../api/types';
  import { MONTH_AXIS_LABELS, MONTH_NAMES } from './months';
  import { atPlace, capitalizeFirst, ofPlace, type SpeciesNoun } from './frenchGrammar';
  import { PRESENCE_LEVELS, PRESENCE_LEVEL_LABELS, describeLocalPresence } from './localPresence';

  interface Props {
    detail: SpeciesDetail;
    noun: SpeciesNoun;
  }

  let { detail, noun }: Props = $props();

  const MONTH_SHORT = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

  // `null` = suit le site global (utile aussi le temps que siteStore.load() se termine).
  let chosenSlug = $state<string | null>(null);
  let slug = $derived(chosenSlug ?? siteStore.selectedSlug);
  let site = $derived(siteStore.sites.find((candidate) => candidate.slug === slug) ?? null);
  let presence = $derived(slug ? (detail.local_presence_by_site?.[slug] ?? null) : null);
  let sentences = $derived(presence && site ? describeLocalPresence(presence, noun, site.name) : []);
  let title = $derived(site ? `Peut-on l'entendre ${atPlace(site.name)} ?` : "Peut-on l'entendre ici ?");

  function handleSiteChange(event: Event): void {
    chosenSlug = (event.target as HTMLSelectElement).value;
  }
</script>

<section id="ici" class="wiki-section">
  <div class="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 wiki-h2-row">
    <h2 class="wiki-h2 basis-full sm:basis-auto sm:flex-1">{title}</h2>
    {#if siteStore.sites.length > 1}
      <label class="flex items-center gap-2 text-sm pb-1">
        Lieu
        <select class="select select-sm" value={slug ?? ''} onchange={handleSiteChange} aria-label="Lieu">
          {#each siteStore.sites as option (option.slug)}
            <option value={option.slug}>{option.name}</option>
          {/each}
        </select>
      </label>
    {/if}
  </div>

  {#if !site}
    <p class="wiki-prose text-muted">Choisissez un lieu pour savoir si cet oiseau y est habituel.</p>
  {:else if !presence}
    <p class="wiki-prose text-muted">
      {#if site.lat === null || site.lon === null}
        La position {ofPlace(site.name)} n'est pas renseignée : impossible de dire si cet oiseau y est habituel.
      {:else}
        Il n'y a pas assez d'observations de cet oiseau en France pour dire s'il est habituel par ici.
      {/if}
    </p>
  {:else}
    <div class="presence-card">
      <p class="text-sm text-muted mb-3">
        Mois par mois, d'après les observations des naturalistes autour {ofPlace(presence.reference_city.name)}.
      </p>
      <ol class="presence-frieze" aria-label="Présence mois par mois {atPlace(site.name)}">
        {#each presence.monthly_levels as level, index (index)}
          {@const isCurrent = index + 1 === presence.current_month}
          <li
            class="presence-month level-{level}"
            class:is-current={isCurrent}
            title="{capitalizeFirst(MONTH_NAMES[index] ?? '')} : {PRESENCE_LEVEL_LABELS[level].toLowerCase()}"
          >
            <span aria-hidden="true" class="sm:hidden">{MONTH_AXIS_LABELS[index]}</span>
            <span aria-hidden="true" class="hidden sm:inline">{MONTH_SHORT[index]}</span>
            <span class="sr-only">
              {MONTH_NAMES[index]} : {PRESENCE_LEVEL_LABELS[level].toLowerCase()}{isCurrent ? ' (mois en cours)' : ''}
            </span>
          </li>
        {/each}
      </ol>
      <div class="presence-marker" aria-hidden="true">
        <span style="grid-column: {presence.current_month}">▲</span>
      </div>

      <ul class="presence-legend" aria-label="Légende">
        {#each PRESENCE_LEVELS as level (level)}
          <li><span class="swatch level-{level}"></span>{PRESENCE_LEVEL_LABELS[level]}</li>
        {/each}
        <li><span class="swatch swatch-current"></span>Mois en cours</li>
      </ul>
    </div>

    <p class="wiki-prose presence-conclusion">{sentences.join(' ')}</p>
  {/if}
</section>

<style>
  .presence-card {
    border-radius: var(--radius-box);
    background-color: var(--color-base-100);
    padding: 1rem;
    box-shadow: var(--shadow-sm);
  }

  .presence-frieze {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 0.25rem;
  }

  .presence-month {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 2.5rem;
    border-radius: 0.375rem;
    font-size: 0.75rem;
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
  }

  .presence-month.is-current {
    outline: 2px solid var(--color-base-content);
    outline-offset: 2px;
    font-weight: 700;
  }

  .presence-marker {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 0.25rem;
    margin-top: 0.25rem;
    font-size: 0.625rem;
    line-height: 1;
    text-align: center;
    color: var(--color-base-content);
  }

  .presence-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem 1rem;
    margin-top: 0.75rem;
    font-size: 0.8125rem;
  }

  .presence-legend li {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
  }

  .swatch {
    display: inline-block;
    width: 0.875rem;
    height: 0.875rem;
    border-radius: 0.1875rem;
  }

  .swatch-current {
    background: transparent;
    outline: 2px solid var(--color-base-content);
    outline-offset: -2px;
  }

  .presence-conclusion {
    margin-top: 1rem;
  }

  /* Palette séquentielle vert (plus foncé = plus courant en clair, plus lumineux en sombre).
     Contrastes texte/fond vérifiés ≥ 5:1 dans les deux thèmes. */
  .level-absent {
    background-color: #eef0f3;
    color: #475569;
    box-shadow: inset 0 0 0 1px #d5dae1;
  }
  .level-rare {
    background-color: #d1fae5;
    color: #1f2937;
  }
  .level-peu_frequent {
    background-color: #86efac;
    color: #1f2937;
  }
  .level-courant {
    background-color: #22c55e;
    color: #052e16;
  }
  .level-tres_courant {
    background-color: #15803d;
    color: #ffffff;
  }

  :global([data-theme='dark']) .level-absent {
    background-color: #1e293b;
    color: #cbd5e1;
    box-shadow: inset 0 0 0 1px #334155;
  }
  :global([data-theme='dark']) .level-rare {
    background-color: #143d2c;
    color: #e2e8f0;
  }
  :global([data-theme='dark']) .level-peu_frequent {
    background-color: #166534;
    color: #f1f5f9;
  }
  :global([data-theme='dark']) .level-courant {
    background-color: #16a34a;
    color: #020617;
  }
  :global([data-theme='dark']) .level-tres_courant {
    background-color: #4ade80;
    color: #020617;
  }
</style>
