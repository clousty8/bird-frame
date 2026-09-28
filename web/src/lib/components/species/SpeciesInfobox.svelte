<script lang="ts">
  // Encadré « En bref » façon infobox Wikipédia, flottant à droite de l'introduction sur grand
  // écran seulement (sur mobile, tout est déjà dans la colonne : chips de classification sous
  // le titre, statut dans « Migration et saisons », présence dans « Peut-on l'entendre… »).
  import type { LocalPresence, SpeciesDetail } from '../../api/types';
  import { agree, atPlace, capitalizeFirst, type SpeciesNoun } from './frenchGrammar';
  import { presencePeriodLabel } from './localPresence';

  interface Props {
    detail: SpeciesDetail;
    noun: SpeciesNoun;
    presence: LocalPresence | null;
    siteName: string | null;
  }

  let { detail, noun, presence, siteName }: Props = $props();

  const ACTIVITY_LABELS = {
    diurne: 'De jour',
    nocturne: 'De nuit',
    crépusculaire: 'À l’aube et au crépuscule',
    mixte: 'De jour comme de nuit',
  } as const;
</script>

<aside class="infobox" aria-label="En bref">
  <p class="infobox-title">En bref</p>
  <dl>
    {#if detail.taxonomy?.order}
      <dt>Ordre</dt>
      <dd>{detail.taxonomy.order}</dd>
    {/if}
    {#if detail.taxonomy?.family}
      <dt>Famille</dt>
      <dd>{detail.taxonomy.family}</dd>
    {/if}
    {#if detail.taxonomy?.genus}
      <dt>Genre</dt>
      <dd class="italic">{detail.taxonomy.genus}</dd>
    {/if}
    {#if detail.migration}
      <dt>En France</dt>
      <dd>{capitalizeFirst(detail.migration.statut)}</dd>
    {/if}
    {#if detail.activity_pattern}
      <dt>Actif</dt>
      <dd>{ACTIVITY_LABELS[detail.activity_pattern]}</dd>
    {/if}
    {#if presence && siteName}
      <dt>{capitalizeFirst(agree('présent', noun.feminine))} {atPlace(siteName)}</dt>
      <dd>{presencePeriodLabel(presence, noun)}</dd>
    {/if}
  </dl>
</aside>
