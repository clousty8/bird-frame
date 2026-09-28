<script lang="ts">
  // Composant neuf. Classement des espèces (contrat §6.17), barres horizontales avec photo
  // miniature. Choix délibéré : pas de D3 ici (voir web/README de l'équipe stats / réponse
  // finale) — une liste de barres horizontales avec vignette est un tableau mis en forme,
  // pas une visualisation qui bénéficie d'un moteur de graphique ; du CSS pur reste plus
  // lisible, plus simple à tester et plus léger sur mobile.
  import type { SpeciesRankingResponse } from '../../api/types';
  import SpeciesPhoto from '../SpeciesPhoto.svelte';
  import Link from '../../Link.svelte';
  import { speciesDetailPath } from '../../router';

  interface Props {
    data: SpeciesRankingResponse;
  }

  let { data }: Props = $props();

  const maxTotal = $derived(Math.max(1, ...data.species.map(s => s.total)));
  const percentFormatter = new Intl.NumberFormat('fr-FR', { style: 'percent', maximumFractionDigits: 0 });
</script>

<ol class="flex flex-col gap-2">
  {#each data.species as species (species.scientific_name)}
    <li class="flex items-center gap-2 sm:gap-3">
      <span class="w-6 shrink-0 text-right text-sm text-muted tabular-nums">{species.rank}</span>
      <SpeciesPhoto src={species.photo_url} alt={species.common_name_fr ?? species.scientific_name} size={40} class="size-10 shrink-0 rounded-full object-cover" />
      <div class="min-w-0 flex-1">
        <Link to={speciesDetailPath(species.scientific_name)} class="block text-sm font-medium leading-tight break-words hover:underline sm:truncate">
          {species.common_name_fr ?? species.scientific_name}
        </Link>
        <div class="mt-1 h-2 w-full rounded-full bg-[var(--color-base-200)]">
          <div
            class="h-2 rounded-full bg-[var(--color-primary)]"
            style:width="{Math.max(2, (species.total / maxTotal) * 100)}%"
          ></div>
        </div>
      </div>
      <div class="w-16 sm:w-24 shrink-0 text-right">
        <p class="text-sm font-semibold tabular-nums">{species.total}</p>
        <p class="text-xs text-muted tabular-nums">{percentFormatter.format(species.avg_confidence)} conf.</p>
      </div>
    </li>
  {/each}
</ol>
