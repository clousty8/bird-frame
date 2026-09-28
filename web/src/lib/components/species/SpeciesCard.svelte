<script lang="ts">
  // Carte espèce réutilisée par la liste (/species) : photo, nom FR + nom scientifique,
  // ligne de stat libre (total/dernière détection selon le mode), badges de statut.
  import Link from '../../Link.svelte';
  import SpeciesPhoto from '../SpeciesPhoto.svelte';
  import Badge from '../ui/Badge.svelte';
  import { speciesDetailPath } from '../../router';
  import type { SpeciesCardBadge } from './types';

  interface Props {
    scientificName: string;
    commonNameFr: string | null;
    photoUrl: string | null;
    statLine: string;
    badges?: SpeciesCardBadge[];
  }

  let { scientificName, commonNameFr, photoUrl, statLine, badges = [] }: Props = $props();
</script>

<Link
  to={speciesDetailPath(scientificName)}
  class="group flex gap-3 items-center rounded-lg bg-[var(--color-base-100)] p-3 shadow-sm hover:shadow-md transition-shadow"
>
  <SpeciesPhoto
    src={photoUrl}
    alt={commonNameFr ?? scientificName}
    size={64}
    class="size-16 rounded-md object-cover shrink-0"
  />
  <div class="min-w-0 flex-1">
    <p class="font-medium truncate group-hover:underline">{commonNameFr ?? scientificName}</p>
    {#if commonNameFr}
      <p class="text-xs italic text-muted truncate">{scientificName}</p>
    {/if}
    <p class="text-xs text-muted mt-1">{statLine}</p>
    {#if badges.length > 0}
      <div class="flex flex-wrap gap-1 mt-1">
        {#each badges as badge (badge.text)}
          <Badge variant={badge.variant} size="xs" text={badge.text} />
        {/each}
      </div>
    {/if}
  </div>
</Link>
