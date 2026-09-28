<script lang="ts">
  // Composant neuf (équipe Tableau de bord, WP-06). Prévu pour WP-19 : quand un relais HLS
  // sera branché côté serveur (contrat docs/architecture.md §6), `hlsUrl` portera l'URL
  // proxiée et ce composant câblera hls.js + Web Audio API (AnalyserNode) pour dessiner le
  // spectrogramme en direct. Pour l'instant `hlsUrl` vaut toujours `null` : on affiche un
  // message d'indisponibilité clair plutôt qu'un lecteur qui n'aurait rien à lire.

  interface Props {
    /** URL du flux HLS proxié par le serveur (contrat, WP-19), ou `null` tant qu'il n'existe pas. */
    hlsUrl: string | null;
  }

  let { hlsUrl }: Props = $props();
</script>

{#if hlsUrl === null}
  <div
    class="rounded-lg border border-dashed border-[var(--border-200)] p-4 text-sm text-muted text-center"
  >
    Spectrogramme en direct : disponible quand le relais audio sera branché (WP-19).
  </div>
{:else}
  <!-- Branchement réel (hls.js + AnalyserNode) laissé à WP-19 : ce cas n'est pas encore
       atteignable tant que le serveur ne renvoie jamais d'URL non nulle. -->
  <div class="rounded-lg border border-[var(--border-100)] p-4 text-sm text-muted text-center">
    Lecture du flux en direct pas encore implémentée.
  </div>
{/if}
