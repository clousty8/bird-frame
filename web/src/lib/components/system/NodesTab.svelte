<script lang="ts">
  // Sous-onglet « Nœuds » (contrat §6.2 GET /nodes). Composant neuf.
  import { onMount } from 'svelte';
  import { getNodes, ApiRequestError } from '../../api/client';
  import type { NodeStatus } from '../../api/types';
  import Card from '../ui/Card.svelte';
  import Badge from '../ui/Badge.svelte';
  import Button from '../ui/Button.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import { formatInstant, formatPercent } from './format';
  import { formatCount } from '../../format';

  let nodes = $state<NodeStatus[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    loading = true;
    error = null;
    try {
      const response = await getNodes();
      nodes = response.nodes;
    } catch (err) {
      // Jamais avalée : affichée avec un bouton pour réessayer.
      error = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des nœuds.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    void load();
  });
</script>

<div class="space-y-4">
  <p class="text-sm text-muted max-w-3xl">
    Le <strong>bridge</strong> tourne à côté de chaque installation BirdNET-Go : il lit sa base de
    détections en lecture seule, les pousse vers ce serveur, et applique les commandes envoyées
    depuis cette page système (règles, seuils, revue) — sans jamais écrire directement dans la
    base du nœud.
  </p>

  {#if loading}
    <LoadingSpinner label="Chargement des nœuds…" />
  {:else if error}
    <div class="space-y-2">
      <ErrorAlert type="error" message={error} />
      <Button variant="default" onclick={load}>Réessayer</Button>
    </div>
  {:else if nodes.length === 0}
    <EmptyState
      title="Aucun nœud enregistré"
      description="Aucun bridge ne s'est encore enregistré auprès de ce serveur (scripts/register_node.py)."
    />
  {:else}
    <div class="grid gap-4 sm:grid-cols-2">
      {#each nodes as node (node.node_id)}
        <Card>
          {#snippet header()}
            <div class="flex items-start justify-between gap-2">
              <div>
                <h3 class="text-lg font-semibold">{node.node_name}</h3>
                <p class="text-sm text-muted">{node.site_name}</p>
              </div>
              <Badge variant={node.online ? 'success' : 'error'} text={node.online ? 'En ligne' : 'Hors ligne'} />
            </div>
          {/snippet}

          <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm mt-2">
            <dt class="text-muted">Micro</dt>
            <dd class="flex items-center gap-1.5 flex-wrap">
              <span>{node.mic_device_name ?? 'inconnu'}</span>
              {#if node.mic_healthy === true}
                <Badge variant="success" size="xs" text="OK" />
              {:else if node.mic_healthy === false}
                <Badge variant="error" size="xs" text="anomalie" />
              {:else}
                <Badge variant="neutral" size="xs" text="inconnu" />
              {/if}
            </dd>

            <dt class="text-muted">Dernière détection</dt>
            <dd>{formatInstant(node.last_detection_at)}</dd>

            <dt class="text-muted">Dernière synchro</dt>
            <dd>{formatInstant(node.last_sync_at)}</dd>

            <dt class="text-muted">Disque libre</dt>
            <dd>{formatPercent(node.disk_free_pct)}</dd>

            <dt class="text-muted">BirdNET-Go</dt>
            <dd>
              {node.birdnet_go_version ?? 'inconnu'}
              {#if node.birdnet_go_reachable === false}
                <Badge variant="warning" size="xs" text="injoignable" />
              {/if}
            </dd>

            <dt class="text-muted">Bridge</dt>
            <dd>{node.bridge_version ?? 'inconnu'}</dd>

            {#if node.sync_lag !== null && node.sync_lag > 0}
              <dt class="text-muted">Retard de synchro</dt>
              <dd>{formatCount(node.sync_lag, 'détection')} en attente</dd>
            {/if}

            {#if node.decommissioned_at}
              <dt class="text-muted">Statut</dt>
              <dd><Badge variant="neutral" size="xs" text="mis hors service" /></dd>
            {/if}
          </dl>
        </Card>
      {/each}
    </div>
  {/if}
</div>
