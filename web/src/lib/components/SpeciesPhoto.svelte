<script lang="ts">
  import { untrack } from 'svelte';

  // Composant neuf. Le retry reprend seulement l'IDÉE générale (repli + petit essai
  // supplémentaire) d'`image-utils.ts` (birdnet-go-ui, CC BY-NC-SA 4.0) — la logique est
  // réécrite ici car le contrat bird-frame diffère : GET /species/{name}/photo génère la
  // photo de façon SYNCHRONE (contrat §6.10), il n'y a donc pas de "pas encore en cache,
  // réessayer plus tard" comme côté BirdNET-Go (dont le proxy asynchrone justifiait 4
  // paliers de retry). Seuls les aléas réseau transitoires justifient un nouvel essai ici,
  // avec un nombre de tentatives volontairement réduit ("retry léger").

  interface Props {
    /** URL déjà résolue par le serveur (`photo_url`/`photo.url`), ou `null` si l'espèce n'a pas de photo. */
    src: string | null;
    alt: string;
    /** Taille d'affichage en pixels (carrée). Défaut 320, comme la vignette standard du contrat. */
    size?: number;
    class?: string;
  }

  let { src, alt, size = 320, class: className = '' }: Props = $props();

  const RETRY_DELAYS_MS = [500, 2000, 5000];

  let attempt = $state(0);
  let failed = $state(false);
  // untrack : la valeur initiale seulement, le $effect ci-dessous gère les changements de `src`.
  let displaySrc = $state(untrack(() => src));
  // Timer du retry programmé en cours, hors état réactif : sert uniquement à l'annuler.
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    // Un changement d'URL (nouvelle espèce, nouvelle taille) repart d'un état propre — et
    // annule tout retry déjà programmé pour l'ANCIENNE url : sans ça, ce retry se déclenchait
    // après coup et réécrivait `displaySrc` avec l'ancienne image par-dessus la nouvelle.
    displaySrc = src;
    attempt = 0;
    failed = false;
    clearTimeout(retryTimer);
    retryTimer = undefined;

    // Nettoyage : exécuté juste avant la prochaine ré-exécution de cet effect (nouveau `src`)
    // et à la destruction du composant — même garde-fou dans les deux cas.
    return () => clearTimeout(retryTimer);
  });

  function scheduleRetry(originalSrc: string): void {
    const delay = RETRY_DELAYS_MS[attempt];
    if (delay === undefined) {
      failed = true;
      return;
    }
    attempt += 1;
    const jitteredDelay = delay * (0.85 + Math.random() * 0.3);
    retryTimer = setTimeout(() => {
      // Casse le cache HTTP pour forcer une vraie nouvelle requête plutôt qu'un rejeu
      // silencieux du même échec depuis le cache du navigateur.
      const separator = originalSrc.includes('?') ? '&' : '?';
      displaySrc = `${originalSrc}${separator}retry=${attempt}`;
    }, jitteredDelay);
  }

  function handleError(): void {
    if (!src) return;
    scheduleRetry(src);
  }
</script>

{#if displaySrc && !failed}
  <img src={displaySrc} {alt} width={size} height={size} loading="lazy" class={className} onerror={handleError} />
{:else}
  <div
    class="flex items-center justify-center bg-[var(--color-base-200)] text-[var(--color-base-content)] {className}"
    role="img"
    aria-label={alt}
  >
    <svg viewBox="0 0 24 24" class="w-1/3 h-1/3 opacity-40" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.5" />
      <path d="M21 16l-5.5-5.5a1 1 0 0 0-1.4 0L6 19" />
    </svg>
  </div>
{/if}
