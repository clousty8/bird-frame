<script lang="ts">
  // Composant neuf. Sélecteur de période de la page Statistiques : 5 onglets
  // (7 j / 30 j / 90 j / année / personnalisée), avec deux champs date quand
  // "personnalisée" est actif. Contrôlé par le parent (StatsPage) : ce composant ne
  // détient aucun état, il ne fait que remonter les changements.
  import { PERIOD_PRESETS, isValidLocalDate, type PeriodPreset } from './period';

  interface Props {
    preset: PeriodPreset;
    customStart: string | null;
    customEnd: string | null;
    onPresetChange: (preset: PeriodPreset) => void;
    onCustomChange: (start: string, end: string) => void;
  }

  let { preset, customStart, customEnd, onPresetChange, onCustomChange }: Props = $props();

  // Brouillon local des deux champs date : ne remonte au parent que lorsque la plage est
  // valide (bornes bien formées, début <= fin), pour ne jamais déclencher un appel réseau
  // avec une plage incohérente pendant que l'utilisateur tape. Initialisé à vide puis
  // synchronisé par le $effect ci-dessous (y compris à l'affichage initial), pour ne pas
  // lire les props directement dans l'initialiseur de $state (svelte/state_referenced_locally).
  let draftStart = $state('');
  let draftEnd = $state('');

  $effect(() => {
    draftStart = customStart ?? '';
    draftEnd = customEnd ?? '';
  });

  const customError = $derived.by((): string | null => {
    if (preset !== 'custom') return null;
    if (!draftStart || !draftEnd) return 'Choisissez une date de début et une date de fin.';
    if (!isValidLocalDate(draftStart) || !isValidLocalDate(draftEnd)) return 'Dates invalides.';
    if (draftStart > draftEnd) return 'La date de début doit précéder la date de fin.';
    return null;
  });

  function handleDateChange(): void {
    if (customError === null && draftStart && draftEnd) {
      onCustomChange(draftStart, draftEnd);
    }
  }
</script>

<div class="flex flex-col gap-2">
  <div class="tabs tabs-boxed w-fit" role="tablist" aria-label="Période">
    {#each PERIOD_PRESETS as option (option.value)}
      <button
        type="button"
        role="tab"
        class="tab"
        class:tab-active={preset === option.value}
        aria-selected={preset === option.value}
        onclick={() => onPresetChange(option.value)}
      >
        {option.label}
      </button>
    {/each}
  </div>

  {#if preset === 'custom'}
    <div class="flex flex-wrap items-end gap-2">
      <label class="flex flex-col gap-1 text-sm">
        Du
        <input
          type="date"
          class="input input-sm"
          bind:value={draftStart}
          onchange={handleDateChange}
          max={draftEnd || undefined}
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        Au
        <input
          type="date"
          class="input input-sm"
          bind:value={draftEnd}
          onchange={handleDateChange}
          min={draftStart || undefined}
        />
      </label>
      {#if customError}
        <span class="text-xs text-error" role="alert">{customError}</span>
      {/if}
    </div>
  {/if}
</div>
