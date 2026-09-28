<script lang="ts">
  // Composant neuf (équipe Tableau de bord, WP-06). Bloc « en écoute » : snapshot initial via
  // GET /sites/{slug}/now (contrat §6.3) puis relais quasi temps réel via SSE
  // GET /sites/{slug}/pending/stream (contrat §6.4). Affiche aussi les 10 dernières détections
  // confirmées en petites puces (PAS un grand bloc « détections récentes » séparé — supprimé
  // du code neuf, cf. docs/architecture.md §8.3/docs/plan.md WP-06).
  import { getSiteNow, subscribeToPending, ApiRequestError } from '../../api/client';
  import type { PendingItem, PendingStatus, RecentDetection } from '../../api/types';
  import { speciesDetailPath } from '../../router';
  import Card from '../ui/Card.svelte';
  import Badge from '../ui/Badge.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import CollapsibleSection from '../ui/CollapsibleSection.svelte';
  import SpeciesPhoto from '../SpeciesPhoto.svelte';
  import Link from '../../Link.svelte';
  import LiveSpectrogram from './LiveSpectrogram.svelte';
  import { formatCount } from '../../format';

  interface Props {
    /** Slug du site courant (contrat §1.5). Changer de site recharge tout ce bloc. */
    slug: string;
    /** Fuseau du site (pour l'heure des puces « dernières détections »), si déjà connu. */
    timezone?: string;
  }

  let { slug, timezone }: Props = $props();

  let pending = $state<PendingItem[]>([]);
  let recent = $state<RecentDetection[]>([]);
  let nodeOnline = $state<boolean | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const STATUS_LABELS: Record<PendingStatus, string> = {
    active: 'en écoute',
    approved: 'confirmé',
    rejected: 'écarté',
  };
  const STATUS_VARIANTS: Record<PendingStatus, 'info' | 'success' | 'neutral'> = {
    active: 'info',
    approved: 'success',
    rejected: 'neutral',
  };

  function pendingKey(item: PendingItem): string {
    return `${item.node_id}|${item.scientific_name}|${item.first_detected_unix}`;
  }

  function formatLocalTime(utcInstant: string): string {
    const date = new Date(utcInstant);
    try {
      return new Intl.DateTimeFormat('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
        ...(timezone ? { timeZone: timezone } : {}),
      }).format(date);
    } catch {
      // Fuseau inconnu/mal formé : jamais bloquant, on retombe sur l'heure du navigateur.
      return new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(date);
    }
  }

  // Effet clé sur `slug` : re-snapshot + nouvel abonnement SSE à chaque changement de site.
  $effect(() => {
    const currentSlug = slug;
    let cancelled = false;

    loading = true;
    error = null;
    pending = [];
    recent = [];
    nodeOnline = null;

    // Le SSE envoie son premier `pending` immédiatement à la connexion (contrat §6.4), il
    // peut donc très bien arriver avant que ce fetch (aller-retour HTTP + parsing JSON) ne
    // se résolve. Ces variables capturent ce que le SSE a déjà livré pendant que le fetch est
    // en vol, pour fusionner au lieu d'écraser au moment où `getSiteNow` se résout — sinon le
    // snapshot, plus ancien, effaçait purement et simplement un état déjà plus frais.
    let pendingFromSse: PendingItem[] | null = null;
    let sseDetections: RecentDetection[] = [];

    getSiteNow(currentSlug)
      .then((now) => {
        if (cancelled) return;
        pending = pendingFromSse ?? now.pending;
        const knownIds = new Set(sseDetections.map((d) => d.detection_id));
        recent = [...sseDetections, ...now.recent.filter((d) => !knownIds.has(d.detection_id))].slice(0, 10);
        nodeOnline = now.node_status?.online ?? nodeOnline;
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        error =
          err instanceof ApiRequestError
            ? err.message
            : "Erreur inconnue lors du chargement du bloc « en écoute ».";
      })
      .finally(() => {
        if (!cancelled) loading = false;
      });

    const unsubscribe = subscribeToPending(currentSlug, {
      onPending: (event) => {
        pendingFromSse = event.pending;
        pending = event.pending;
      },
      onDetection: (event) => {
        sseDetections = [event, ...sseDetections].slice(0, 10);
        recent = [event, ...recent].slice(0, 10);
      },
      onHeartbeat: (event) => {
        nodeOnline = event.node_online;
      },
      onError: () => {
        // EventSource se reconnecte de lui-même (contrat §6.4) : rien à faire ici, juste
        // ne jamais planter silencieusement — journalisé pour le debug.
        console.error(`[bird-frame] connexion SSE « pending » interrompue pour le site ${currentSlug}`);
      },
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  });
</script>

<Card padding={false}>
  <div class="p-4">
    <div class="flex items-center justify-between gap-2 mb-3">
      <h2 class="text-lg font-semibold">En écoute</h2>
      {#if nodeOnline !== null}
        <span class="inline-flex items-center gap-1.5 text-xs text-muted">
          <span
            class="inline-block size-2 rounded-full"
            class:bg-success={nodeOnline}
            class:bg-base-300={!nodeOnline}
            aria-hidden="true"
          ></span>
          {nodeOnline ? 'Nœud en ligne' : 'Nœud hors ligne'}
        </span>
      {/if}
    </div>

    {#if loading}
      <LoadingSpinner label="Chargement du bloc « en écoute »…" size="md" />
    {:else if error}
      <ErrorAlert message={error} />
    {:else if pending.length === 0}
      <p class="text-sm text-muted">Rien en cours d'écoute pour l'instant.</p>
    {:else}
      <ul class="flex flex-col gap-3">
        {#each pending as item (pendingKey(item))}
          <li class="flex items-center gap-3">
            <SpeciesPhoto
              src={item.photo_url}
              alt={item.common_name_fr ?? item.scientific_name}
              size={56}
              class="w-14 h-14 rounded-md object-cover shrink-0"
            />
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium truncate">{item.common_name_fr ?? item.scientific_name}</span>
                <Badge variant={STATUS_VARIANTS[item.status]} size="sm" text={STATUS_LABELS[item.status]} />
              </div>
              <div class="text-xs text-muted mt-0.5">
                {formatCount(item.hit_count, 'coup')}
              </div>
              {#if item.confidence_hint !== null}
                {@const percent = Math.round(item.confidence_hint * 100)}
                <div
                  class="mt-1 h-1.5 w-full max-w-40 rounded-full bg-[var(--color-base-300)] overflow-hidden"
                  role="progressbar"
                  aria-valuenow={percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Confiance"
                >
                  <div class="h-full rounded-full bg-[var(--color-primary)]" style="width: {percent}%"></div>
                </div>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {/if}

    {#if recent.length > 0}
      <div class="mt-4 pt-3 border-t border-border-100">
        <h3 class="text-xs font-medium text-muted uppercase tracking-wide mb-2">
          Dernières détections confirmées
        </h3>
        <ul class="flex flex-wrap gap-1.5">
          {#each recent as det (det.detection_id)}
            <li>
              <Link
                to={speciesDetailPath(det.scientific_name)}
                class="badge badge-ghost hover:opacity-80 inline-flex items-center gap-1"
              >
                {det.common_name_fr ?? det.scientific_name} · {formatLocalTime(det.detected_at_utc)}
              </Link>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  </div>

  <!-- CollapsibleSection = composant partagé (src/lib/components/ui/), identifié par
       docs/architecture.md §8.1 comme le candidat direct pour ce déplié. Repliée par défaut. -->
  <CollapsibleSection
    title="Spectrogramme en direct"
    defaultOpen={false}
    class="rounded-t-none border-t border-[var(--border-100)]"
  >
    <LiveSpectrogram hlsUrl={null} />
  </CollapsibleSection>
</Card>
