<script lang="ts">
  // Mini-histogramme vertical (fiche espèce : présence par mois, statistiques par mois et
  // par heure). Hauteurs en pixels calculées par barHeightsPx (voir barChart.ts pour la
  // raison : les hauteurs en % s'effondraient à 0 px).
  import { barHeightsPx } from './barChart';

  interface Props {
    /** Valeurs, une barre par élément. */
    values: number[];
    /** Libellé d'axe sous chaque barre (`null`/'' = pas de libellé pour cette barre). */
    axisLabels: (string | null)[];
    /** Libellé complet d'une barre pour l'infobulle et le lecteur d'écran (ex. « septembre »). */
    barLabel: (index: number) => string;
    /** Variable CSS de couleur (ex. `--color-primary`). */
    colorVar: string;
    /** Description du graphique pour les technologies d'assistance. */
    ariaLabel: string;
    /** Hauteur de la zone des barres, en pixels. */
    heightPx?: number;
  }

  let { values, axisLabels, barLabel, colorVar, ariaLabel, heightPx = 64 }: Props = $props();

  const heights = $derived(barHeightsPx(values, heightPx));
</script>

<figure class="mini-bar-chart m-0" aria-label={ariaLabel}>
  <div
    class="flex items-end gap-0.5 sm:gap-1 border-b border-[var(--border-100)]"
    style="height: {heightPx}px"
    data-testid="mini-bar-chart-track"
  >
    {#each values as value, index (index)}
      <div
        class="flex-1 min-w-0 rounded-t"
        style="height: {heights[index] ?? 0}px; background-color: var({colorVar})"
        title="{barLabel(index)} : {value}"
        data-value={value}
        data-testid="mini-bar"
      ></div>
    {/each}
  </div>
  <div class="flex gap-0.5 sm:gap-1 mt-1" aria-hidden="true">
    {#each values as _value, index (index)}
      <span class="flex-1 min-w-0 text-center text-[0.6rem] leading-none text-muted whitespace-nowrap overflow-visible">
        {axisLabels[index] ?? ''}
      </span>
    {/each}
  </div>
</figure>
