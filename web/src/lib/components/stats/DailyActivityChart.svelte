<script lang="ts">
  // Composant neuf (pas une copie BirdNET-Go) — reprend seulement le motif de dessin D3
  // imperatif utilisé par les graphiques du fork (BaseChart + un $effect qui redessine dans
  // chartGroup à chaque changement de données), documenté dans docs/plan.md WP-15. Le
  // contrat de données (DailyResponse) est propre à bird-frame, donc pas de fichier source
  // à attribuer dans NOTICE.md.
  //
  // Barres = détections du jour (axe gauche), ligne = nombre d'espèces du jour (axe droit).
  import { onDestroy, onMount } from 'svelte';
  import { select } from 'd3-selection';
  import { line as d3Line, curveMonotoneX } from 'd3-shape';
  import type { AxisDomain, AxisScale } from 'd3-axis';

  import BaseChart from '../../charts/BaseChart.svelte';
  import { createBandScale, createLinearScale } from '../../charts/utils/scales';
  import { createAxis, styleAxis, addAxisLabel, createGridLines } from '../../charts/utils/axes';
  import { ChartTooltip } from '../../charts/utils/interactions';
  import type { ChartRenderContext } from '../../charts/utils/theme';
  import type { DailyResponse } from '../../api/types';
  import { formatLocalDateFr } from './period';
  import { maxTicksForWidth, sampleTicks } from './axisDensity';

  interface Props {
    data: DailyResponse;
  }

  let { data }: Props = $props();

  const MARGIN = { top: 20, right: 56, bottom: 46, left: 52 };
  const MAX_X_TICKS = 8;
  const VALUE_TICKS = 5;
  const HEADROOM = 1.1;
  const POINT_RADIUS = 3;
  const POINT_HOVER_RADIUS = 5;

  let tooltip: ChartTooltip | null = null;
  let chartContainer: HTMLDivElement | null = null;
  let chartContext = $state<ChartRenderContext | null>(null);

  function shortDateLabel(value: string): string {
    const d = new Date(`${value}T12:00:00Z`);
    if (Number.isNaN(d.getTime())) return value;
    return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(d);
  }

  function drawChart(context: ChartRenderContext): void {
    const { chartGroup, innerWidth, innerHeight, theme } = context;
    tooltip?.hide();
    chartGroup.selectAll('*').remove();

    const days = data.days;
    if (!days.length || innerWidth <= 0 || innerHeight <= 0) return;

    const dates = days.map(d => d.date);
    const maxTotal = Math.max(1, ...days.map(d => d.total));
    const maxSpecies = Math.max(1, ...days.map(d => d.species_count));

    const xScale = createBandScale({ domain: dates, range: [0, innerWidth], padding: 0.25 });
    const yLeft = createLinearScale({ domain: [0, maxTotal * HEADROOM], range: [innerHeight, 0] });
    const yRight = createLinearScale({ domain: [0, maxSpecies * HEADROOM], range: [innerHeight, 0] });

    createGridLines(chartGroup, { yScale: yLeft, width: innerWidth, height: innerHeight }, theme.axis);

    const xAxis = createAxis({
      scale: xScale as unknown as AxisScale<AxisDomain>,
      orientation: 'bottom',
      tickFormat: (d: AxisDomain) => shortDateLabel(String(d)),
    });
    // « 29 août » ≈ 45 px : une date toutes les 60 px au moins.
    xAxis.tickValues(sampleTicks(dates, maxTicksForWidth(innerWidth, 60, MAX_X_TICKS)));
    const xAxisGroup = chartGroup
      .append('g')
      .attr('class', 'x-axis')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis);
    styleAxis(xAxisGroup, theme.axis);

    const yLeftAxis = createAxis({ scale: yLeft, orientation: 'left', tickCount: VALUE_TICKS, tickFormat: d => String(Math.round(Number(d))) });
    const yLeftGroup = chartGroup.append('g').attr('class', 'y-axis-left').call(yLeftAxis);
    styleAxis(yLeftGroup, theme.axis);

    const yRightAxis = createAxis({ scale: yRight, orientation: 'right', tickCount: VALUE_TICKS, tickFormat: d => String(Math.round(Number(d))) });
    const yRightGroup = chartGroup
      .append('g')
      .attr('class', 'y-axis-right')
      .attr('transform', `translate(${innerWidth},0)`)
      .call(yRightAxis);
    styleAxis(yRightGroup, theme.axis);

    addAxisLabel(chartGroup, { text: 'Détections', orientation: 'left', offset: 40, width: innerWidth, height: innerHeight }, theme.axis);
    addAxisLabel(chartGroup, { text: 'Espèces', orientation: 'right', offset: 40, width: innerWidth, height: innerHeight }, theme.axis);

    const bars = chartGroup
      .append('g')
      .attr('class', 'bars')
      .selectAll('rect.bar')
      .data(days)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', d => xScale(d.date) ?? 0)
      .attr('y', d => yLeft(d.total))
      .attr('width', xScale.bandwidth())
      .attr('height', d => Math.max(0, innerHeight - yLeft(d.total)))
      .style('fill', theme.primary)
      .style('opacity', 0.85);

    bars
      .on('mouseenter', function (event: MouseEvent, d) {
        select(this).style('opacity', 1);
        tooltip?.show({
          title: formatLocalDateFr(d.date),
          items: [
            { label: 'Détections', value: d.total, color: theme.primary },
            { label: 'Espèces', value: d.species_count, color: theme.accent },
          ],
          x: event.clientX,
          y: event.clientY,
        });
      })
      .on('mousemove', (event: MouseEvent) => tooltip?.move(event.clientX, event.clientY))
      .on('mouseleave', function () {
        select(this).style('opacity', 0.85);
        tooltip?.hide();
      });

    const lineGenerator = d3Line<(typeof days)[number]>()
      .x(d => (xScale(d.date) ?? 0) + xScale.bandwidth() / 2)
      .y(d => yRight(d.species_count))
      .curve(curveMonotoneX);

    chartGroup
      .append('path')
      .datum(days)
      .attr('class', 'species-line')
      .attr('d', lineGenerator)
      .style('fill', 'none')
      .style('stroke', theme.accent)
      .style('stroke-width', 2);

    chartGroup
      .append('g')
      .attr('class', 'species-points')
      .selectAll('circle')
      .data(days)
      .enter()
      .append('circle')
      .attr('cx', d => (xScale(d.date) ?? 0) + xScale.bandwidth() / 2)
      .attr('cy', d => yRight(d.species_count))
      .attr('r', POINT_RADIUS)
      .style('fill', theme.accent)
      .on('mouseenter', function (event: MouseEvent, d) {
        select(this).transition().duration(120).attr('r', POINT_HOVER_RADIUS);
        tooltip?.show({
          title: formatLocalDateFr(d.date),
          items: [
            { label: 'Espèces', value: d.species_count, color: theme.accent },
            { label: 'Détections', value: d.total, color: theme.primary },
          ],
          x: event.clientX,
          y: event.clientY,
        });
      })
      .on('mousemove', (event: MouseEvent) => tooltip?.move(event.clientX, event.clientY))
      .on('mouseleave', function () {
        select(this).transition().duration(120).attr('r', POINT_RADIUS);
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

<div class="daily-activity-chart" bind:this={chartContainer}>
  <BaseChart height={320} margin={MARGIN} responsive={true} ariaLabel="Détections et nombre d'espèces par jour">
    {#snippet children(context)}
      {((chartContext = context), '')}
    {/snippet}
  </BaseChart>
  <div class="flex items-center gap-4 mt-2 text-xs text-muted">
    <span class="inline-flex items-center gap-1.5">
      <span class="inline-block size-2.5 rounded-sm" style="background-color: var(--color-primary)"></span>
      Détections
    </span>
    <span class="inline-flex items-center gap-1.5">
      <span class="inline-block size-2.5 rounded-full" style="background-color: var(--color-accent)"></span>
      Espèces
    </span>
  </div>
</div>

<style>
  .daily-activity-chart {
    width: 100%;
    min-height: 320px;
  }
</style>
