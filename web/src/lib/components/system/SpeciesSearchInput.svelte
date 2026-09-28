<script lang="ts">
  // Composant neuf, propre à l'équipe « système » : recherche d'espèce (GET /species?q=)
  // utilisée par le formulaire de règles (espèce visée, cible de redirection) et par le
  // formulaire de faux négatif. Pas un composant copié de BirdNET-Go.
  import { getSpeciesList, ApiRequestError } from '../../api/client';
  import type { UniverseSpecies } from '../../api/types';

  interface Props {
    id: string;
    label: string;
    placeholder?: string;
    /** Espèce déjà choisie : affichée en lecture avec un bouton pour la changer. */
    selectedScientificName?: string | null;
    selectedCommonName?: string | null;
    onSelect: (species: UniverseSpecies) => void;
    onClear?: () => void;
    /** Nom scientifique à exclure des résultats (ex. l'espèce de la règle elle-même). */
    excludeScientificName?: string | null;
    disabled?: boolean;
  }

  let {
    id,
    label,
    placeholder = 'Nom français ou scientifique…',
    selectedScientificName = null,
    selectedCommonName = null,
    onSelect,
    onClear,
    excludeScientificName = null,
    disabled = false,
  }: Props = $props();

  let query = $state('');
  let results = $state<UniverseSpecies[]>([]);
  let open = $state(false);
  let loading = $state(false);
  let searchError = $state<string | null>(null);
  let debounceTimer: ReturnType<typeof setTimeout> | undefined;
  // Jeton de requête : le debounce n'empêche que plusieurs setTimeout de se déclencher, pas
  // deux fetch déjà en vol de se croiser à l'arrivée. Sans ce garde-fou, une réponse en retard
  // pour une frappe précédente pouvait écraser les résultats d'une recherche plus récente.
  let searchRequestId = 0;

  async function runSearch(term: string): Promise<void> {
    const requestId = ++searchRequestId;
    loading = true;
    searchError = null;
    try {
      const response = await getSpeciesList({ q: term, limit: 8 });
      if (requestId !== searchRequestId) return;
      results = response.species.filter((species) => species.scientific_name !== excludeScientificName);
      open = true;
    } catch (err) {
      if (requestId !== searchRequestId) return;
      // Jamais avalée : affichée sous le champ, la recherche reste réessayable en retapant.
      searchError = err instanceof ApiRequestError ? err.message : 'Recherche indisponible pour le moment.';
      results = [];
      open = true;
    } finally {
      if (requestId === searchRequestId) loading = false;
    }
  }

  function scheduleSearch(): void {
    if (debounceTimer) clearTimeout(debounceTimer);
    const term = query.trim();
    if (term.length < 2) {
      results = [];
      open = false;
      return;
    }
    debounceTimer = setTimeout(() => void runSearch(term), 300);
  }

  function pick(species: UniverseSpecies): void {
    onSelect(species);
    query = '';
    results = [];
    open = false;
  }

  function handleBlur(): void {
    // Laisse le temps au clic sur une option d'être traité avant de fermer la liste.
    setTimeout(() => {
      open = false;
    }, 150);
  }
</script>

<div class="relative">
  <label for={id} class="block text-sm font-medium mb-1">{label}</label>

  {#if selectedScientificName}
    <div class="flex items-center gap-2">
      <span class="input flex-1 flex items-center gap-1 bg-[var(--color-base-200)]">
        <span>{selectedCommonName ?? selectedScientificName}</span>
        <span class="text-muted text-xs italic">({selectedScientificName})</span>
      </span>
      {#if onClear}
        <button type="button" class="btn btn-ghost btn-sm" onclick={onClear} {disabled}>Changer</button>
      {/if}
    </div>
  {:else}
    <input
      {id}
      type="text"
      class="input input-bordered w-full"
      {placeholder}
      bind:value={query}
      oninput={scheduleSearch}
      onfocus={scheduleSearch}
      onblur={handleBlur}
      autocomplete="off"
      {disabled}
      role="combobox"
      aria-expanded={open}
      aria-controls="{id}-listbox"
      aria-autocomplete="list"
    />
    {#if loading}
      <p class="text-xs text-muted mt-1">Recherche…</p>
    {:else if searchError}
      <p class="text-xs text-error mt-1">{searchError}</p>
    {/if}
    {#if open && results.length > 0}
      <ul
        id="{id}-listbox"
        role="listbox"
        class="absolute z-10 mt-1 w-full max-h-60 overflow-auto rounded-lg border shadow-lg bg-[var(--color-base-100)] border-[var(--color-base-300)]"
      >
        {#each results as species (species.scientific_name)}
          <li>
            <button
              type="button"
              role="option"
              aria-selected="false"
              class="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-base-200)]"
              onmousedown={(event) => event.preventDefault()}
              onclick={() => pick(species)}
            >
              {species.common_name_fr ?? species.scientific_name}
              <span class="text-muted text-xs">({species.scientific_name})</span>
            </button>
          </li>
        {/each}
      </ul>
    {:else if open && !loading && !searchError}
      <p class="text-xs text-muted mt-1">Aucune espèce ne correspond.</p>
    {/if}
  {/if}
</div>
