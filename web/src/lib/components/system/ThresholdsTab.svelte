<script lang="ts">
  // Sous-onglet « Seuils dynamiques » (contrat §6.23-§6.24). Composant neuf.
  import { onMount } from 'svelte';
  import { siteStore } from '../../stores/site.svelte';
  import { getDynamicThresholds, resetDynamicThreshold, ApiRequestError } from '../../api/client';
  import type { DynamicThreshold } from '../../api/types';
  import Badge from '../ui/Badge.svelte';
  import Button from '../ui/Button.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import { formatInstant } from './format';

  let thresholds = $state<DynamicThreshold[]>([]);
  let snapshotAt = $state<string | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);

  let resettingFor = $state<string | null>(null);
  let resetMessage = $state<string | null>(null);
  let resetError = $state<string | null>(null);

  async function load(): Promise<void> {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    loading = true;
    loadError = null;
    try {
      const response = await getDynamicThresholds(slug);
      thresholds = response.thresholds;
      snapshotAt = response.snapshot_at;
    } catch (err) {
      loadError = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des seuils dynamiques.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const slug = siteStore.selectedSlug;
    if (slug) void load();
  });

  async function reset(threshold: DynamicThreshold): Promise<void> {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    resettingFor = threshold.scientific_name;
    resetError = null;
    resetMessage = null;
    try {
      await resetDynamicThreshold(slug, threshold.scientific_name);
      resetMessage = `Réinitialisation demandée pour ${threshold.common_name_fr ?? threshold.scientific_name} — l'affichage se mettra à jour au prochain signal du nœud (jusqu'à 60 s).`;
      await load();
    } catch (err) {
      resetError = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors de la réinitialisation.';
    } finally {
      resettingFor = null;
    }
  }

  const LEVEL_VARIANT: Record<number, 'neutral' | 'info' | 'warning' | 'error'> = {
    0: 'neutral',
    1: 'info',
    2: 'warning',
    3: 'error',
  };

  onMount(() => {
    // Rafraîchit le miroir de temps en temps : le heartbeat du nœud le met à jour côté
    // serveur toutes les ~60 s (contrat §4.6), pas besoin de temps réel ici.
    const interval = setInterval(() => void load(), 60_000);
    return () => clearInterval(interval);
  });
</script>

<div class="space-y-4">
  <div class="rounded-lg border border-[var(--color-info)]/30 bg-[var(--color-info)]/10 p-4 text-sm max-w-3xl">
    <p class="font-medium mb-1">Comment ça marche</p>
    <p>
      BirdNET-Go abaisse automatiquement le seuil de confiance d'une espèce (niveaux 0 à 3) pendant
      <strong>24 h</strong> après plusieurs détections à forte confiance, pour continuer à la
      repérer même si le signal faiblit ensuite. Ce tableau est un <strong>miroir en lecture
      seule</strong> de l'état réel du nœud (mis à jour au heartbeat, toutes les ~60 s) — la
      réinitialisation envoie une commande au bridge, elle n'agit pas directement ici.
      Une règle « impossible ici » (onglet <em>Règles par espèce</em>) reste prioritaire même si le
      seuil dynamique d'une espèce s'est abaissé.
    </p>
  </div>

  {#if !siteStore.selectedSlug}
    <EmptyState title="Aucun site sélectionné" description="Choisissez un site en haut de page pour voir ses seuils dynamiques." />
  {:else}
    {#if resetError}
      <ErrorAlert type="error" message={resetError} dismissible onDismiss={() => (resetError = null)} />
    {/if}
    {#if resetMessage}
      <p role="status" class="text-sm text-[var(--color-success)]">{resetMessage}</p>
    {/if}

    {#if loading}
      <LoadingSpinner label="Chargement des seuils dynamiques…" />
    {:else if loadError}
      <div class="space-y-2">
        <ErrorAlert type="error" message={loadError} />
        <Button variant="default" onclick={load}>Réessayer</Button>
      </div>
    {:else if thresholds.length === 0}
      <EmptyState
        title="Aucun seuil dynamique actif"
        description="Aucune espèce n'a actuellement de seuil abaissé automatiquement sur ce site."
      />
    {:else}
      {#if snapshotAt}
        <p class="text-xs text-muted">Instantané du {formatInstant(snapshotAt)}</p>
      {/if}
      <div class="overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            <tr>
              <th>Espèce</th>
              <th>Niveau</th>
              <th>Seuil courant</th>
              <th>Seuil de base</th>
              <th>Expire le</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each thresholds as threshold (threshold.node_id + '|' + threshold.scientific_name)}
              <tr>
                <td>
                  <div class="font-medium">{threshold.common_name_fr ?? threshold.scientific_name}</div>
                  <div class="text-xs text-muted italic">{threshold.scientific_name}</div>
                </td>
                <td><Badge variant={LEVEL_VARIANT[threshold.level] ?? 'neutral'} text="niveau {threshold.level}" /></td>
                <td class="text-sm">{threshold.current_value}</td>
                <td class="text-sm">{threshold.base_threshold}</td>
                <td class="text-sm whitespace-nowrap">{formatInstant(threshold.expires_at)}</td>
                <td class="whitespace-nowrap">
                  {#if threshold.reset_pending}
                    <Badge variant="warning" size="xs" text="réinitialisation en attente" />
                  {:else}
                    <Button
                      variant="default"
                      size="xs"
                      disabled={resettingFor === threshold.scientific_name}
                      onclick={() => reset(threshold)}
                    >
                      {resettingFor === threshold.scientific_name ? 'Envoi…' : 'Réinitialiser'}
                    </Button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>
