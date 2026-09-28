<!--
  Adapté de BirdNET-Go (birdnet-go-ui, fork bird-frame, tag 20260823).
  Licence d'origine : CC BY-NC-SA 4.0. Voir web/NOTICE.md.
  Modifications : suppression de la dépendance i18n (`t('common.ui.loading')`), libellé
  français en dur ("Chargement…") — décision du lead : pas de système i18n pour l'instant.
  Suppression de l'utilitaire safeGet (accès direct, sûr).
-->
<script lang="ts">
  import { cn } from '../../utils/cn';

  type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

  interface Props {
    size?: SpinnerSize;
    color?: string;
    label?: string;
  }

  let { size = 'lg', color = 'text-[var(--color-primary)]', label = 'Chargement…' }: Props = $props();

  const sizeClasses: Record<SpinnerSize, string> = {
    xs: 'w-3 h-3 border',
    sm: 'w-4 h-4 border',
    md: 'w-6 h-6 border-2',
    lg: 'w-10 h-10 border-2',
    xl: 'w-14 h-14 border-[3px]',
  };

  const baseSpinnerClasses =
    'inline-block aspect-square border-[var(--color-base-300)] border-t-current rounded-full animate-spin';
</script>

<div class="flex items-center justify-center" role="status" aria-label={label}>
  <span class={cn(baseSpinnerClasses, sizeClasses[size], color)}></span>
  <span class="sr-only">{label}</span>
</div>
