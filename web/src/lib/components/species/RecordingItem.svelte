<script lang="ts">
  // Un enregistrement : spectrogramme (contrat §6.13, image sans axes/légende, 0..durée
  // sur l'axe X) avec un bouton lecture superposé et un curseur de progression simple, un
  // <audio> natif (masqué : c'est le bouton + curseur qui servent d'interface, contrat
  // « audio natif <audio> + bouton lecture superposé au spectrogramme »), date/heure,
  // confiance, et les labels multi-espèces.
  // Écoute réservée à une session (contrat §2.2, voix privées possibles) : déconnecté, le
  // spectrogramme reste visible mais le bouton devient un cadenas qui ouvre la modale, et
  // aucun <audio> n'est créé (il précharge sinon l'URL et récolterait des 401).
  import type { TopClip } from '../../api/types';
  import { authStore } from '../../stores/auth.svelte';
  import MultiSpeciesLabels from './MultiSpeciesLabels.svelte';

  interface Props {
    clip: TopClip;
  }

  let { clip }: Props = $props();

  let audioEl: HTMLAudioElement | undefined = $state();
  let playing = $state(false);
  let progressPct = $state(0);
  // Affiché à côté du bouton quand .play() rejette (politique autoplay, clip supprimé côté
  // serveur mais encore référencé, fichier tronqué) : sans ça, l'échec n'était visible qu'en
  // console et le bouton restait sur 'Lire' sans aucun retour pour l'utilisateur.
  let playbackError = $state<string | null>(null);

  function togglePlay(): void {
    if (!audioEl) return;
    if (playing) {
      audioEl.pause();
    } else {
      playbackError = null;
      // .play() peut rejeter (politique autoplay du navigateur, fichier non lisible) : ne
      // jamais avaler l'échec silencieusement.
      audioEl.play().catch((err: unknown) => {
        console.error('[bird-frame] lecture audio impossible', err);
        playbackError = 'Lecture impossible.';
        // Une session expirée donne le même échec opaque côté <audio> (401) : on relit
        // l'état de session, le cadenas réapparaît si c'était la cause.
        if (authStore.authEnabled) void authStore.load();
      });
    }
  }

  // Déconnexion pendant une lecture : arrêter le son avant que l'<audio> ne soit retiré du
  // DOM (un élément détaché peut continuer à jouer dans certains navigateurs).
  $effect.pre(() => {
    if (authStore.unlocked) return;
    if (playing) audioEl?.pause();
    playing = false;
    progressPct = 0;
  });

  function handleTimeUpdate(): void {
    if (!audioEl || !audioEl.duration) return;
    progressPct = (audioEl.currentTime / audioEl.duration) * 100;
  }

  function formatDateTime(iso: string): string {
    try {
      return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });
    } catch {
      return iso;
    }
  }
</script>

<div class="rounded-lg bg-[var(--color-base-100)] p-3 shadow-sm flex flex-col gap-2">
  <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
    <span>{formatDateTime(clip.detected_at_utc)}</span>
    <span class="text-muted">Confiance : {Math.round(clip.confidence * 100)} %</span>
  </div>

  {#if clip.audio_available && clip.audio_url}
    <div class="relative rounded-md overflow-hidden bg-[var(--color-base-200)]">
      {#if clip.spectrogram_url}
        <img src={clip.spectrogram_url} alt="Spectrogramme de l'enregistrement" class="w-full h-24 object-cover block" />
      {:else}
        <div class="w-full h-24"></div>
      {/if}

      {#if authStore.unlocked}
        <!-- Curseur de progression (contrat §6.13 : x = currentTime / duration × largeur). -->
        <div class="absolute inset-y-0 left-0 w-0.5 bg-[var(--color-primary)]" style="left: {progressPct}%" aria-hidden="true"></div>

        <button
          type="button"
          class="absolute inset-0 flex items-center justify-center bg-black/20 hover:bg-black/30 transition-colors"
          onclick={togglePlay}
          aria-label={playing ? 'Mettre en pause' : "Lire l'enregistrement"}
        >
          <svg class="size-8 text-white drop-shadow" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            {#if playing}
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            {:else}
              <path d="M8 5v14l11-7z" />
            {/if}
          </svg>
        </button>
      {:else}
        <button
          type="button"
          class="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/35 hover:bg-black/45 transition-colors text-white"
          onclick={() => void authStore.openLoginModal()}
        >
          <svg class="size-7 drop-shadow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <rect x="5" y="11" width="14" height="10" rx="2" />
            <path d="M8 11V8a4 4 0 0 1 8 0v3" />
          </svg>
          <span class="text-xs font-medium drop-shadow">Connecte-toi pour écouter</span>
        </button>
      {/if}
    </div>

    {#if authStore.unlocked}
      <audio
        bind:this={audioEl}
        src={clip.audio_url}
        class="hidden"
        onplay={() => (playing = true)}
        onpause={() => (playing = false)}
        onended={() => (playing = false)}
        ontimeupdate={handleTimeUpdate}
      ></audio>
    {/if}

    {#if playbackError}
      <p class="text-xs text-red-600" role="alert">{playbackError}</p>
    {/if}
  {:else}
    <p class="text-xs text-muted italic">Audio pas encore rapatrié pour cet enregistrement.</p>
  {/if}

  <MultiSpeciesLabels predictions={clip.predictions} />
</div>
