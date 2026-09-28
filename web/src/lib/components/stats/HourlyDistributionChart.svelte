<script lang="ts">
  // Composant neuf. 24 barres (une par heure locale), chacune empilée avec les espèces
  // principales de cette heure (contrat §6.16 : jusqu'à 10 espèces par heure, déjà triées
  // par le serveur) + un segment "Autres" pour le reste du total. La couleur de chaque
  // espèce est stable sur toute la page (speciesColor.ts), pas seulement dans ce graphique.
  import { onDestroy, onMount } from 'svelte';
  import { select } from 'd3-selection';
  import type { AxisDomain, AxisScale } from 'd3-axis';

  import BaseChart from '../../charts/BaseChart.svelte';
  import { createBandScale, createLinearScale } from '../../charts/utils/scales';
  import { createAxis, styleAxis, addAxisLabel, createGridLines, createHourAxisFormatter, hourAxisTickValues } from '../../charts/utils/axes';
  import { ChartTooltip } from '../../charts/utils/interactions';
  import { getSpeciesColor, registerChart } from '../../charts/utils/speciesColor';
  import { getCurrentTheme, type ChartRenderContext, type ChartTheme } from '../../charts/utils/theme';
  import type { HourlyResponse } from '../../api/types';
  import { hourTickStep } from './axisDensity';

  interface Props {
    data: HourlyResponse;
  }

  let { data }: Props = $props();

  const MARGIN = { top: 20, right: 20, bottom: 46, left: 52 };
  const HEADROOM = 1.08;
  const OTHER_COLOR = 'var(--color-base-300)';
  const LEGEND_MAX = 8;

  interface Segment {
    hour: number;
    label: string;
    count: number;
    y0: number;
    y1: number;
    color: string;
  }

  let tooltip: ChartTooltip | null = null;
  let chartContainer: HTMLDivElement | null = null;
  let chartContext = $state<ChartRenderContext | null>(null);
  let unregisterColors: (() => void) | null = null;
  // Thème utilisé pour le dernier tracé D3, réutilisé pour colorer la légende HTML sous le
  // graphique (mêmes couleurs que les segments, y compris en thème sombre).
  let drawnTheme = $state<ChartTheme>(getCurrentTheme());

  // Espèces à afficher dans la légende : les plus fréquentes sur l'ensemble des heures
  // (somme des tops horaires — une approximation du classement réel, suffisante pour une
  // légende : le classement précis vient de la page "Classement des espèces").
  const legendSpecies = $derived.by(() => {
    const totals = new Map<string, { label: string; total: number }>();
    for (const hour of data.hours) {
      for (const species of hour.species) {
        const existing = totals.get(species.scientific_name);
        const label = species.common_name_fr ?? species.scientific_name;
        if (existing) {
          existing.total += species.count;
        } else {
          totals.set(species.scientific_name, { label, total: species.count });
        }
      }
    }
    return Array.from(totals.entries())
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, LEGEND_MAX)
      .map(([scientificName, info]) => ({ scientificName, label: info.label }));
  });

  const hasOthers = $derived(
    data.hours.some(hour => hour.total > hour.species.reduce((sum, s) => sum + s.count, 0))
  );

  function buildSegments(theme: ChartRenderContext['theme']): Segment[] {
    const segments: Segment[] = [];
    for (const hour of data.hours) {
      let offset = 0;
      for (const species of hour.species) {
        const label = species.common_name_fr ?? species.scientific_name;
        segments.push({
          hour: hour.hour,
          label,
          count: species.count,
          y0: offset,
          y1: offset + species.count,
          color: getSpeciesColor(species.scientific_name, theme),
        });
        offset += species.count;
      }
      if (hour.total > offset) {
        segments.push({
          hour: hour.hour,
          label: 'Autres espèces',
          count: hour.total - offset,
          y0: offset,
          y1: hour.total,
          color: OTHER_COLOR,
        });
      }
    }
    return segments;
  }

  function drawChart(context: ChartRenderContext): void {
    const { chartGroup, innerWidth, innerHeight, theme } = context;
    tooltip?.hide();
    chartGroup.selectAll('*').remove();
    drawnTheme = theme;

    if (innerWidth <= 0 || innerHeight <= 0) return;

    const hours = data.hours;
    const maxTotal = Math.max(1, ...hours.map(h => h.total));

    const xScale = createBandScale({ domain: hours.map(h => String(h.hour)), range: [0, innerWidth], padding: 0.15 });
    const yScale = createLinearScale({ domain: [0, maxTotal * HEADROOM], range: [innerHeight, 0] });

    createGridLines(chartGroup, { yScale, width: innerWidth, height: innerHeight }, theme.axis);

    const hourFormat = createHourAxisFormatter(true);
    const xAxis = createAxis({
      scale: xScale as unknown as AxisScale<AxisDomain>,
      orientation: 'bottom',
      tickFormat: d => hourFormat(Number(d)),
    });
    // « 00:00 » ≈ 32 px : une graduation toutes les 44 px au moins, pas de 3 h minimum.
    xAxis.tickValues(hourAxisTickValues(23, hourTickStep(innerWidth, 44, 3)).map(String));
    const xAxisGroup = chartGroup.append('g').attr('class', 'x-axis').attr('transform', `translate(0,${innerHeight})`).call(xAxis);
    styleAxis(xAxisGroup, theme.axis);

    const yAxis = createAxis({ scale: yScale, orientation: 'left', tickCount: 5, tickFormat: d => String(Math.round(Number(d))) });
    const yAxisGroup = chartGroup.append('g').attr('class', 'y-axis').call(yAxis);
    styleAxis(yAxisGroup, theme.axis);

    addAxisLabel(chartGroup, { text: 'Détections', orientation: 'left', offset: 40, width: innerWidth, height: innerHeight }, theme.axis);

    const segments = buildSegments(theme);
    const bandwidth = xScale.bandwidth();

    chartGroup
      .append('g')
      .attr('class', 'segments')
      .selectAll('rect.segment')
      .data(segments)
      .enter()
      .append('rect')
      .attr('class', 'segment')
      .attr('x', d => xScale(String(d.hour)) ?? 0)
      .attr('y', d => yScale(d.y1))
      .attr('width', bandwidth)
      .attr('height', d => Math.max(0, yScale(d.y0) - yScale(d.y1)))
      .style('fill', d => d.color)
      .style('opacity', 0.9)
      .on('mouseenter', function (event: MouseEvent, d) {
        select(this).style('opacity', 1).style('stroke', theme.text).style('stroke-width', 1);
        tooltip?.show({
          title: `${d.hour}h — ${d.label}`,
          items: [{ label: 'Détections', value: d.count, color: d.color }],
          x: event.clientX,
          y: event.clientY,
        });
      })
      .on('mousemove', (event: MouseEvent) => tooltip?.move(event.clientX, event.clientY))
      .on('mouseleave', function () {
        select(this).style('opacity', 0.9).style('stroke', 'none');
        tooltip?.hide();
      });
  }

  $effect(() => {
    void data;
    if (chartContext) drawChart(chartContext);
  });

  onMount(() => {
    if (chartContainer) tooltip = new ChartTooltip(chartContainer);
    unregisterColors = registerChart();
  });

  onDestroy(() => {
    tooltip?.destroy();
    tooltip = null;
    unregisterColors?.();
  });
</script>

<div class="hourly-distribution-chart" bind:this={chartContainer}>
  <BaseChart height={300} margin={MARGIN} responsive={true} ariaLabel="Répartition des détections par heure de la journée, empilée par espèce">
    {#snippet children(context)}
      {((chartContext = context), '')}
    {/snippet}
  </BaseChart>
  {#if legendSpecies.length > 0}
    <div class="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-muted">
      {#each legendSpecies as species (species.scientificName)}
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-block size-2.5 rounded-sm" style="background-color: {getSpeciesColor(species.scientificName, drawnTheme)}"
          ></span>
          {species.label}
        </span>
      {/each}
      {#if hasOthers}
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-block size-2.5 rounded-sm" style="background-color: {OTHER_COLOR}"></span>
          Autres espèces
        </span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .hourly-distribution-chart {
    width: 100%;
    min-height: 300px;
  }
</style>
