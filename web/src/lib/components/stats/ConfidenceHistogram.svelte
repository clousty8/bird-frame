<script lang="ts">
  // Composant neuf. Histogramme de confiance (contrat §6.19) : 10 classes fixes de 10 points
  // de confiance chacune.
  import { onDestroy, onMount } from 'svelte';
  import { select } from 'd3-selection';
  import type { AxisDomain, AxisScale } from 'd3-axis';

  import BaseChart from '../../charts/BaseChart.svelte';
  import { createBandScale, createLinearScale } from '../../charts/utils/scales';
  import { createAxis, styleAxis, addAxisLabel, createGridLines } from '../../charts/utils/axes';
  import { ChartTooltip } from '../../charts/utils/interactions';
  import type { ChartRenderContext } from '../../charts/utils/theme';
  import type { ConfidenceResponse } from '../../api/types';
  import { isCompactBandAxis } from './axisDensity';

  interface Props {
    data: ConfidenceResponse;
  }

  let { data }: Props = $props();

  const MARGIN = { top: 20, right: 20, bottom: 46, left: 52 };
  const HEADROOM = 1.1;

  let tooltip: ChartTooltip | null = null;
  let chartContainer: HTMLDivElement | null = null;
  let chartContext = $state<ChartRenderContext | null>(null);

  function bucketLabel(min: number, max: number): string {
    return `${Math.round(min * 100)}-${Math.round(max * 100)}%`;
  }

  function drawChart(context: ChartRenderContext): void {
    const { chartGroup, innerWidth, innerHeight, theme } = context;
    tooltip?.hide();
    chartGroup.selectAll('*').remove();

    const buckets = data.buckets;
    if (!buckets.length || innerWidth <= 0 || innerHeight <= 0) return;

    const maxCount = Math.max(1, ...buckets.map(b => b.count));
    const labels = buckets.map(b => bucketLabel(b.min, b.max));

    const xScale = createBandScale({ domain: labels, range: [0, innerWidth], padding: 0.15 });
    const yScale = createLinearScale({ domain: [0, maxCount * HEADROOM], range: [innerHeight, 0] });

    createGridLines(chartGroup, { yScale, width: innerWidth, height: innerHeight }, theme.axis);

    // Largeur étroite (mobile) : « 90-100% » ne tient plus, même incliné — on n'affiche que
    // la borne basse de chaque tranche (« 90 »), droite, et l'unité passe dans le titre d'axe.
    const compact = isCompactBandAxis(innerWidth, labels.length);
    const lowerBoundByLabel = new Map(buckets.map((b, i) => [labels[i] ?? '', String(Math.round(b.min * 100))]));
    const xAxis = createAxis({
      scale: xScale as unknown as AxisScale<AxisDomain>,
      orientation: 'bottom',
      tickFormat: compact ? (d: AxisDomain) => lowerBoundByLabel.get(String(d)) ?? String(d) : undefined,
    });
    const xAxisGroup = chartGroup.append('g').attr('class', 'x-axis').attr('transform', `translate(0,${innerHeight})`).call(xAxis);
    styleAxis(xAxisGroup, theme.axis);
    if (!compact) {
      xAxisGroup
        .selectAll('.tick text')
        .attr('transform', 'rotate(-30)')
        .attr('text-anchor', 'end')
        .attr('dx', '-0.4em')
        .attr('dy', '0.2em');
    }

    const yAxis = createAxis({ scale: yScale, orientation: 'left', tickCount: 5, tickFormat: d => String(Math.round(Number(d))) });
    const yAxisGroup = chartGroup.append('g').attr('class', 'y-axis').call(yAxis);
    styleAxis(yAxisGroup, theme.axis);

    addAxisLabel(chartGroup, { text: 'Détections', orientation: 'left', offset: 40, width: innerWidth, height: innerHeight }, theme.axis);
    addAxisLabel(
      chartGroup,
      { text: compact ? 'Confiance (début de tranche, %)' : 'Confiance', orientation: 'bottom', offset: compact ? 34 : 40, width: innerWidth, height: innerHeight },
      theme.axis
    );

    const total = data.total;
    const bars = chartGroup
      .append('g')
      .attr('class', 'bars')
      .selectAll('rect.bar')
      .data(buckets)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', (_d, i) => xScale(labels[i] ?? '') ?? 0)
      .attr('y', d => yScale(d.count))
      .attr('width', xScale.bandwidth())
      .attr('height', d => Math.max(0, innerHeight - yScale(d.count)))
      .style('fill', theme.primary)
      .style('opacity', 0.85);

    bars
      .on('mouseenter', function (event: MouseEvent, d) {
        select(this).style('opacity', 1);
        const share = total > 0 ? Math.round((d.count / total) * 100) : 0;
        tooltip?.show({
          title: bucketLabel(d.min, d.max),
          items: [
            { label: 'Détections', value: d.count, color: theme.primary },
            { label: 'Part du total', value: `${share}%` },
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

<div class="confidence-histogram" bind:this={chartContainer}>
  <BaseChart height={280} margin={MARGIN} responsive={true} ariaLabel="Histogramme de la confiance des détections">
    {#snippet children(context)}
      {((chartContext = context), '')}
    {/snippet}
  </BaseChart>
</div>

<style>
  .confidence-histogram {
    width: 100%;
    min-height: 280px;
  }
</style>
