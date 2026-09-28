// Types partagés entre les composants de src/lib/components/species/ (équipe « Espèces »).

/** Reprend les variantes de web/src/lib/components/ui/Badge.svelte (non exportées par ce
 *  fichier .svelte — on les redéclare ici pour typer les badges construits par les pages). */
export type SpeciesBadgeVariant =
  | 'primary'
  | 'secondary'
  | 'accent'
  | 'neutral'
  | 'info'
  | 'success'
  | 'warning'
  | 'error'
  | 'ghost';

export interface SpeciesCardBadge {
  text: string;
  variant: SpeciesBadgeVariant;
}
