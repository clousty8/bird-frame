<script lang="ts">
  // Composant neuf. Heatmap saisonnière espèce × semaine (contrat §6.18, semaine au sens
  // §1.4 — jamais la semaine ISO). Matrice large et haute (jusqu'à 40 lignes × 53 colonnes) :
  // dimensions FIXES calculées depuis les données (pas de redimensionnement responsive comme
  // les autres graphiques), le conteneur défile horizontalement sur mobile — un tableau de
  // cette forme reste lisible en défilant, jamais en écrasant les colonnes jusqu'à
  // l'illisibilité.
  import { onDestroy, onMount } from 'svelte';
  import { select } from 'd3-selection';
  import type { AxisDomain, AxisScale } from 'd3-axis';

  import BaseChart from '../../charts/BaseChart.svelte';
  import { createBandScale } from '../../charts/utils/scales';
  import { createAxis, styleAxis } from '../../charts/utils/axes';
  import { ChartTooltip } from '../../charts/utils/interactions';
  import { fitTextNode } from '../../charts/utils/labels';
  import type { ChartRenderContext } from '../../charts/utils/theme';
  import type { HeatmapResponse } from '../../api/types';

  interface Props {
    data: HeatmapResponse;
    year: number;
    minYear: number;
    onYearChange: (year: number) => void;
  }

  let { data, year, minYear, onYearChange }: Props = $props();

  const MARGIN = { top: 8, right: 12, bottom: 24, left: 170 };
  const ROW_HEIGHT = 15;
  const CELL_WIDTH = 15;
  const MIN_CELL_OPACITY = 0.12;
  const WEEK_TICK_STEP = 4;

  const currentYear = new Date().getFullYear();
  const yearOptions = $derived.by(() => {
    const from = Math.min(minYear, currentYear);
    const years: number[] = [];
    for (let y = currentYear; y >= from; y--) years.push(y);
    return years;
  });

  const width = $derived(MARGIN.left + MARGIN.right + data.week_count * CELL_WIDTH);
  const height = $derived(MARGIN.top + MARGIN.bottom + Math.max(1, data.species.length) * ROW_HEIGHT);

  let tooltip: ChartTooltip | null = null;
  let chartContainer: HTMLDivElement | null = null;
  let chartContext = $state<ChartRenderContext | null>(null);

  function drawChart(context: ChartRenderContext): void {
    const { chartGroup, innerWidth, innerHeight, theme } = context;
    tooltip?.hide();
    chartGroup.selectAll('*').remove();

    const species = data.species;
    if (!species.length || innerWidth <= 0 || innerHeight <= 0) return;

    const speciesLabels = species.map(s => s.common_name_fr ?? s.scientific_name);
    const weekDomain = Array.from({ length: data.week_count }, (_, i) => String(i + 1));

    const xScale = createBandScale({ domain: weekDomain, range: [0, innerWidth], padding: 0.08 });
    const yScale = createBandScale({ domain: speciesLabels, range: [0, innerHeight], padding: 0.08 });

    const maxCount = Math.max(1, ...species.flatMap(s => s.weeks));

    const xAxis = createAxis({
      scale: xScale as unknown as AxisScale<AxisDomain>,
      orientation: 'bottom',
      tickFormat: d => `S${d}`,
    });
    xAxis.tickValues(weekDomain.filter((_, i) => i % WEEK_TICK_STEP === 0));
    const xAxisGroup = chartGroup.append('g').attr('class', 'x-axis').attr('transform', `translate(0,${innerHeight})`).call(xAxis);
    styleAxis(xAxisGroup, theme.axis);

    const yAxis = createAxis({ scale: yScale as unknown as AxisScale<AxisDomain>, orientation: 'left' });
    const yAxisGroup = chartGroup.append('g').attr('class', 'y-axis').call(yAxis);
    styleAxis(yAxisGroup, theme.axis);
    // Noms français parfois longs : ajustés à la largeur de la marge gauche (comme le
    // classement horizontal de BirdNET-Go), nom complet conservé en <title>.
    yAxisGroup.selectAll<globalThis.SVGTextElement, AxisDomain>('.tick text').each(function (d) {
      fitTextNode(this, String(d), MARGIN.left - 12);
    });
    yAxisGroup.selectAll<globalThis.SVGGElement, AxisDomain>('.tick').append('title').text(d => String(d));

    const bandW = xScale.bandwidth();
    const bandH = yScale.bandwidth();

    interface Cell {
      speciesLabel: string;
      scientificName: string;
      week: number;
      count: number;
    }
    const cells: Cell[] = [];
    species.forEach(s => {
      const label = s.common_name_fr ?? s.scientific_name;
      s.weeks.forEach((count, i) => {
        cells.push({ speciesLabel: label, scientificName: s.scientific_name, week: i + 1, count });
      });
    });

    chartGroup
      .append('g')
      .attr('class', 'heatmap-cells')
      .selectAll('rect.heatmap-cell')
      .data(cells)
      .enter()
      .append('rect')
      .attr('class', 'heatmap-cell')
      .attr('x', d => xScale(String(d.week)) ?? 0)
      .attr('y', d => yScale(d.speciesLabel) ?? 0)
      .attr('width', bandW)
      .attr('height', bandH)
      .attr('rx', 1)
      .style('fill', d => (d.count > 0 ? theme.primary : theme.grid))
      .style('opacity', d => (d.count > 0 ? MIN_CELL_OPACITY + (1 - MIN_CELL_OPACITY) * (d.count / maxCount) : 1))
      .on('mouseenter', function (event: MouseEvent, d) {
        select(this).style('stroke', theme.text).style('stroke-width', 1);
        tooltip?.show({
          title: d.speciesLabel,
          items: [
            { label: 'Semaine', value: d.week },
            { label: 'Détections', value: d.count },
          ],
          x: event.clientX,
          y: event.clientY,
        });
      })
      .on('mouseleave', function () {
        select(this).style('stroke', 'none');
        tooltip?.hide();
      });
  }

  $effect(() => {
    void data;
    if (chartContext) drawChart(chartContext);
  });

  onMount(() => {
    if (chartContainer) tooltip = new ChartTooltip(chartContainer);
  });

  onDestroy(() => {
    tooltip?.destroy();
    tooltip = null;
  });
</script>

<div class="flex flex-col gap-2">
  <label class="flex items-center gap-2 text-sm w-fit">
    Année
    <select class="select select-sm w-auto" value={year} onchange={(e) => onYearChange(Number((e.target as HTMLSelectElement).value))}>
      {#each yearOptions as y (y)}
        <option value={y}>{y}</option>
      {/each}
    </select>
  </label>

  <div class="seasonal-heatmap overflow-x-auto" bind:this={chartContainer}>
    <BaseChart {width} {height} margin={MARGIN} responsive={false} ariaLabel="Détections par espèce et par semaine de l'année {year}">
      {#snippet children(context)}
        {((chartContext = context), '')}
      {/snippet}
    </BaseChart>
  </div>

  <div class="flex items-center gap-3 text-xs text-muted">
    <span class="inline-flex items-center gap-1.5">
      <span class="inline-block size-2.5 rounded-sm" style="background-color: var(--color-base-300)"></span>
      Aucune détection
    </span>
    <span class="inline-flex items-center gap-1.5">
      <span class="inline-block size-2.5 rounded-sm" style="background-color: var(--color-primary); opacity: 0.4"></span>
      Peu
    </span>
    <span class="inline-flex items-center gap-1.5">
      <span class="inline-block size-2.5 rounded-sm" style="background-color: var(--color-primary)"></span>
      Beaucoup
    </span>
  </div>
</div>

<style>
  .seasonal-heatmap {
    width: 100%;
  }
</style>
