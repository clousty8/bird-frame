<script lang="ts">
  // Propriété de l'équipe « Système ». Voir web/README.md.
  // Le contenu de chaque sous-onglet vit dans src/lib/components/system/ (un composant
  // par onglet), cette page se contente de la navigation et du montage.
  import Link from '../lib/Link.svelte';
  import { DEFAULT_SYSTEM_TAB, SYSTEM_TABS, isSystemTab, systemTabPath, type SystemTab } from '../lib/router';
  import NodesTab from '../lib/components/system/NodesTab.svelte';
  import RulesTab from '../lib/components/system/RulesTab.svelte';
  import ReviewTab from '../lib/components/system/ReviewTab.svelte';
  import FalseNegativesTab from '../lib/components/system/FalseNegativesTab.svelte';
  import ThresholdsTab from '../lib/components/system/ThresholdsTab.svelte';

  interface Props {
    tab: string;
  }

  let { tab }: Props = $props();

  const TAB_LABELS: Record<SystemTab, string> = {
    nodes: 'Nœuds',
    rules: 'Règles par espèce',
    review: 'Revue',
    'false-negatives': 'Faux négatifs',
    thresholds: 'Seuils dynamiques',
  };

  let activeTab = $derived<SystemTab>(isSystemTab(tab) ? tab : DEFAULT_SYSTEM_TAB);
</script>

<h1 class="text-2xl font-semibold mb-4">Système</h1>

<nav class="tabs tabs-bordered mb-6" aria-label="Sous-onglets Système">
  {#each SYSTEM_TABS as t (t)}
    <Link to={systemTabPath(t)} class="tab {t === activeTab ? 'tab-active' : ''}">
      {TAB_LABELS[t]}
    </Link>
  {/each}
</nav>

{#if activeTab === 'nodes'}
  <NodesTab />
{:else if activeTab === 'rules'}
  <RulesTab />
{:else if activeTab === 'review'}
  <ReviewTab />
{:else if activeTab === 'false-negatives'}
  <FalseNegativesTab />
{:else if activeTab === 'thresholds'}
  <ThresholdsTab />
{/if}
