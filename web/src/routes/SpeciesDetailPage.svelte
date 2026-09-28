<script lang="ts">
  // Propriété de l'équipe « Espèces ». Voir web/README.md.
  // Route dédiée /species/:name, deep-linkable (architecture.md §8.2 : fiche espèce
  // partageable, pas une modale). Mise en page façon Wikipédia (v0.2, relecture d'Armand du
  // 28/09/2026), une colonne de lecture confortable :
  //   en-tête (nom, nom latin, classification, sommaire) → photo entière (jamais recadrée) →
  //   « À propos » (introduction + sous-sections, encadré « En bref » à droite sur grand
  //   écran) → « Peut-on l'entendre à … ? » → enregistrements → détections par lieu →
  //   statistiques → sources. Contrat §6.9.
  import { onMount } from 'svelte';
  import { siteStore } from '../lib/stores/site.svelte';
  import { getSpeciesDetail, ApiRequestError } from '../lib/api/client';
  import type { SpeciesDetail } from '../lib/api/types';
  import LoadingSpinner from '../lib/components/ui/LoadingSpinner.svelte';
  import ErrorAlert from '../lib/components/ui/ErrorAlert.svelte';
  import Badge from '../lib/components/ui/Badge.svelte';
  import RecordingList from '../lib/components/species/RecordingList.svelte';
  import PresenceBySiteSection from '../lib/components/species/PresenceBySiteSection.svelte';
  import AboutSection from '../lib/components/species/AboutSection.svelte';
  import LocalPresenceSection from '../lib/components/species/LocalPresenceSection.svelte';
  import SpeciesInfobox from '../lib/components/species/SpeciesInfobox.svelte';
  import SourcesSection from '../lib/components/species/SourcesSection.svelte';
  import StatsSection from '../lib/components/species/StatsSection.svelte';
  import { speciesNoun } from '../lib/components/species/frenchGrammar';
  import { aboutContent } from '../lib/components/species/speciesProse';
  import { buildSourceLinks } from '../lib/components/species/sources';

  interface Props {
    scientificName: string;
  }

  let { scientificName }: Props = $props();

  let detail = $state<SpeciesDetail | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let photoFailed = $state(false);

  onMount(() => {
    void siteStore.load();
  });

  // Jeton de requête (même remède que StatsPage.svelte/CurrentlyHearingBlock.svelte) : un
  // clic rapide d'une espèce A vers une espèce B avant la résolution de la requête de A ne
  // doit pas laisser la réponse de A (si elle revient après celle de B) écraser la fiche de B.
  let loadRequestId = 0;

  async function load(name: string): Promise<void> {
    const requestId = ++loadRequestId;
    loading = true;
    error = null;
    detail = null;
    photoFailed = false;
    try {
      const data = await getSpeciesDetail(name);
      if (requestId !== loadRequestId) return;
      detail = data;
    } catch (err) {
      if (requestId !== loadRequestId) return;
      error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement de la fiche.';
    } finally {
      if (requestId === loadRequestId) loading = false;
    }
  }

  $effect(() => {
    void load(scientificName);
  });

  let noun = $derived(speciesNoun(detail?.common_name_fr ?? null));
  let content = $derived(detail ? aboutContent(detail, noun) : null);
  let sourceLinks = $derived(detail ? buildSourceLinks(detail.wikipedia, detail.sources) : []);
  let globalSite = $derived(siteStore.selectedSite);
  let globalPresence = $derived(
    detail && globalSite ? (detail.local_presence_by_site?.[globalSite.slug] ?? null) : null,
  );

  interface TocEntry {
    id: string;
    label: string;
  }

  let toc = $derived.by((): TocEntry[] => {
    if (!detail || !content) return [];
    const entries: TocEntry[] = [{ id: 'a-propos', label: 'À propos' }];
    if (content.where) entries.push({ id: 'ou-le-trouver', label: `Où ${noun.object} trouver` });
    if (content.diet) entries.push({ id: 'alimentation', label: 'Alimentation' });
    if (content.activity) entries.push({ id: 'mode-de-vie', label: 'Mode de vie' });
    if (content.migration.length > 0) entries.push({ id: 'migration', label: 'Migration et saisons' });
    if (content.song) entries.push({ id: 'chant', label: 'Son chant' });
    if (content.lookalikes.length > 0) entries.push({ id: 'confusions', label: 'À ne pas confondre' });
    if (content.facts.length > 0) entries.push({ id: 'anecdotes', label: 'Le saviez-vous ?' });
    entries.push(
      { id: 'ici', label: "Peut-on l'entendre ici ?" },
      { id: 'enregistrements', label: 'Enregistrements' },
      { id: 'detections', label: 'Détections' },
      { id: 'statistiques', label: 'Statistiques' },
    );
    if (sourceLinks.length > 0) entries.push({ id: 'sources', label: 'Sources' });
    return entries;
  });

  // Défilement vers la section sans passer par l'URL (le routeur ne gère pas les ancres).
  function scrollToSection(event: MouseEvent, id: string): void {
    const target = document.getElementById(id);
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
</script>

{#if loading}
  <LoadingSpinner label="Chargement de la fiche…" />
{:else if error}
  <ErrorAlert message={error} />
{:else if detail && content}
  {@const currentDetail = detail}
  <article class="species-article">
    <header class="flex flex-col gap-2">
      <h1 class="wiki-title">{currentDetail.common_name_fr ?? currentDetail.scientific_name}</h1>
      <p class="italic text-muted text-lg">{currentDetail.scientific_name}</p>
      {#if currentDetail.taxonomy}
        <div class="flex flex-wrap gap-1.5">
          {#if currentDetail.taxonomy.order}<span title="Ordre"><Badge variant="neutral" outline text={currentDetail.taxonomy.order} /></span>{/if}
          {#if currentDetail.taxonomy.family}<span title="Famille"><Badge variant="neutral" outline text={currentDetail.taxonomy.family} /></span>{/if}
          {#if currentDetail.taxonomy.genus}<span title="Genre"><Badge variant="neutral" outline text={currentDetail.taxonomy.genus} /></span>{/if}
        </div>
      {/if}

      <nav class="toc" aria-label="Sommaire">
        <span class="toc-label">Sommaire</span>
        <ul>
          {#each toc as entry (entry.id)}
            <li><a href="#{entry.id}" onclick={(event) => scrollToSection(event, entry.id)}>{entry.label}</a></li>
          {/each}
        </ul>
      </nav>
    </header>

    {#if currentDetail.photo && !photoFailed}
      {@const photo = currentDetail.photo}
      <figure class="species-photo">
        <div class="species-photo-frame">
          <img
            src={photo.url_1600}
            alt={currentDetail.common_name_fr ?? currentDetail.scientific_name}
            width={photo.width ?? undefined}
            height={photo.height ?? undefined}
            onerror={() => (photoFailed = true)}
          />
        </div>
        {#if photo.author || photo.license}
          <figcaption class="text-xs text-muted">
            Photo{photo.author ? ` : ${photo.author}` : ''}{photo.license ? ` — ${photo.license}` : ''}{#if photo.description_url}{' — '}<a
                class="link"
                href={photo.description_url}
                target="_blank"
                rel="noopener noreferrer">source</a
              >{/if}
          </figcaption>
        {/if}
      </figure>
    {/if}

    <AboutSection detail={currentDetail} {content} {noun}>
      {#snippet aside()}
        <SpeciesInfobox detail={currentDetail} {noun} presence={globalPresence} siteName={globalSite?.name ?? null} />
      {/snippet}
    </AboutSection>

    <LocalPresenceSection detail={currentDetail} {noun} />

    <RecordingList scientificName={currentDetail.scientific_name} />

    <PresenceBySiteSection presenceBySite={currentDetail.presence_by_site} />

    <StatsSection scientificName={currentDetail.scientific_name} />

    <SourcesSection links={sourceLinks} />
  </article>
{/if}

<style>
  /* Colonne de lecture (≈ 52 rem) centrée : marges larges sur grand écran. */
  .species-article {
    display: flex;
    flex-direction: column;
    gap: 2.5rem;
    width: 100%;
    max-width: 52rem;
    margin-inline: auto;
    --wiki-serif: 'Linux Libertine', 'Libertinus Serif', Georgia, 'Times New Roman', Times, serif;
  }

  .wiki-title {
    font-family: var(--wiki-serif);
    font-size: 2.25rem;
    font-weight: 400;
    line-height: 1.15;
  }

  @media (min-width: 640px) {
    .wiki-title {
      font-size: 2.75rem;
    }
  }

  /* Titres de section façon Wikipédia : empattements, filet fin dessous. */
  .species-article :global(.wiki-h2) {
    font-family: var(--wiki-serif);
    font-size: 1.5rem;
    font-weight: 400;
    line-height: 1.3;
    padding-bottom: 0.25rem;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-200);
    scroll-margin-top: 1rem;
  }

  @media (min-width: 640px) {
    .species-article :global(.wiki-h2) {
      font-size: 1.625rem;
    }
  }

  .species-article :global(.wiki-h2-row) {
    border-bottom: 1px solid var(--border-200);
    margin-bottom: 0.75rem;
  }

  .species-article :global(.wiki-h2-row .wiki-h2) {
    border-bottom: 0;
    margin-bottom: 0;
  }

  .species-article :global(.wiki-h3) {
    font-family: var(--wiki-serif);
    font-size: 1.3125rem;
    font-weight: 700;
    line-height: 1.35;
    margin-top: 1.75rem;
    margin-bottom: 0.5rem;
    scroll-margin-top: 1rem;
  }

  /* Texte courant : ~17 px, interligne 1,65, paragraphes aérés. */
  .species-article :global(.wiki-prose) {
    font-size: 1.0625rem;
    line-height: 1.65;
  }

  .species-article :global(.wiki-prose p + p) {
    margin-top: 0.9em;
  }

  .species-article :global(.wiki-lead) {
    font-size: 1.1875rem;
    line-height: 1.6;
  }

  .species-article :global(.wiki-list) {
    list-style: disc;
    padding-left: 1.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .species-article :global(.wiki-list li::marker) {
    color: var(--text-muted);
  }

  /* La section « À propos » contient l'encadré flottant : elle l'enclôt. */
  .species-article :global(.about) {
    display: flow-root;
  }

  /* Encadré « En bref » : flottant à droite sur grand écran seulement. */
  .species-article :global(.infobox) {
    display: none;
  }

  @media (min-width: 1024px) {
    .species-article :global(.infobox) {
      display: block;
      float: right;
      width: 15rem;
      margin: 0.25rem 0 1rem 2rem;
      padding: 0.875rem 1rem;
      border: 1px solid var(--border-200);
      border-radius: var(--radius-box);
      background-color: var(--color-base-100);
      font-size: 0.875rem;
      line-height: 1.4;
    }
  }

  .species-article :global(.infobox-title) {
    font-family: var(--wiki-serif);
    font-size: 1.125rem;
    text-align: center;
    padding-bottom: 0.375rem;
    margin-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-200);
  }

  .species-article :global(.infobox dt) {
    color: var(--text-muted);
    font-size: 0.75rem;
    margin-top: 0.5rem;
  }

  .species-article :global(.infobox dd) {
    font-weight: 500;
  }

  /* Sommaire discret : une ligne de liens (défile horizontalement sur mobile). */
  .toc {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-top: 0.5rem;
    padding-top: 0.625rem;
    border-top: 1px solid var(--border-100);
    font-size: 0.8125rem;
  }

  .toc-label {
    flex-shrink: 0;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 0.6875rem;
  }

  .toc ul {
    display: flex;
    gap: 0.25rem 0.875rem;
    overflow-x: auto;
    white-space: nowrap;
    scrollbar-width: thin;
    padding-bottom: 0.25rem;
    /* Fondu à droite : signale qu'il y a d'autres liens en faisant défiler. */
    mask-image: linear-gradient(to right, #000 85%, transparent);
  }

  @media (min-width: 640px) {
    .toc ul {
      flex-wrap: wrap;
      overflow-x: visible;
      white-space: normal;
      mask-image: none;
    }
  }

  .toc a {
    color: var(--color-primary);
    text-decoration: none;
  }

  .toc a:hover {
    text-decoration: underline;
  }

  :global([data-theme='dark']) .toc a {
    color: #93c5fd;
  }

  /* Photo entière, jamais recadrée : hauteur ≤ 60 % de la fenêtre, centrée sur fond neutre. */
  .species-photo {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin: 0;
  }

  .species-photo-frame {
    display: flex;
    justify-content: center;
    border-radius: var(--radius-box);
    overflow: hidden;
    background-color: var(--color-base-300);
  }

  .species-photo-frame img {
    display: block;
    width: auto;
    height: auto;
    max-width: 100%;
    max-height: 60vh;
    object-fit: contain;
  }

  .species-photo figcaption {
    text-align: center;
  }
</style>
