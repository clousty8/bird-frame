<script lang="ts">
  // Chips « Rouge-gorge 100 % · Pie bavarde 20 % » : la prédiction primaire en tête, puis
  // les secondaires dont la confiance est ≥ 5 % (contrat api-contract.md §6.11 : jusqu'à 9
  // secondaires dans le payload, mais on n'affiche que celles qui dépassent ce seuil — trop
  // de chips à confiance quasi nulle nuirait à la lisibilité ; décision hors contrat).
  import type { Prediction } from '../../api/types';
  import Badge from '../ui/Badge.svelte';

  interface Props {
    predictions: Prediction[];
  }

  let { predictions }: Props = $props();

  const SECONDARY_MIN_CONFIDENCE = 0.05;

  let primary = $derived(predictions.find((p) => p.is_primary) ?? null);
  let secondaries = $derived(predictions.filter((p) => !p.is_primary && p.confidence >= SECONDARY_MIN_CONFIDENCE));

  function formatLabel(prediction: Prediction): string {
    const name = prediction.common_name_fr ?? prediction.scientific_name;
    return `${name} ${Math.round(prediction.confidence * 100)} %`;
  }
</script>

{#if primary || secondaries.length > 0}
  <div class="flex flex-wrap gap-1.5" role="list" aria-label="Espèces identifiées dans cet enregistrement">
    {#if primary}
      <Badge variant="primary" text={formatLabel(primary)} />
    {/if}
    {#each secondaries as prediction (prediction.scientific_name)}
      <Badge variant="neutral" outline text={formatLabel(prediction)} />
    {/each}
  </div>
{/if}
