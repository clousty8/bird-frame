# Licences de bird-frame

Ce dépôt réunit du code écrit pour bird-frame et quelques éléments repris d'autres projets.
Chaque partie garde sa licence.

| Partie | Licence | Texte |
|---|---|---|
| Tout le code de bird-frame (`server/`, `node/`, `web/`, `scripts/`, documentation), **sauf les exceptions ci-dessous** | MIT | `LICENSE` |
| Les 16 fichiers de `web/` adaptés de BirdNET-Go (liste ci-dessous) | CC BY-NC-SA 4.0 | `LICENSES/CC-BY-NC-SA-4.0.txt` |
| `species-data/` (extraits de Wikipédia, fiches, taxonomie, présence) | CC BY-SA 4.0, avec des réserves pour la taxonomie eBird | `species-data/LICENSE` |

## Fichiers adaptés de BirdNET-Go (CC BY-NC-SA 4.0)

Ces fichiers viennent de [BirdNET-Go](https://github.com/tphakala/birdnet-go), créé par
Tomi P. Hakala et ses contributeurs. Chacun porte un en-tête qui l'indique, et `web/NOTICE.md`
décrit les modifications apportées. Ils restent sous CC BY-NC-SA 4.0 : pas d'usage commercial, et
toute version modifiée doit être publiée sous la même licence.

- `web/src/styles/tailwind.css`
- `web/src/styles/schemes.css`
- `web/src/lib/components/ui/CollapsibleSection.svelte`
- `web/src/lib/components/ui/Card.svelte`
- `web/src/lib/components/ui/Badge.svelte`
- `web/src/lib/components/ui/Button.svelte`
- `web/src/lib/components/ui/LoadingSpinner.svelte`
- `web/src/lib/components/ui/EmptyState.svelte`
- `web/src/lib/components/ui/ErrorAlert.svelte`
- `web/src/lib/charts/BaseChart.svelte`
- `web/src/lib/charts/utils/theme.ts`
- `web/src/lib/charts/utils/scales.ts`
- `web/src/lib/charts/utils/axes.ts`
- `web/src/lib/charts/utils/labels.ts`
- `web/src/lib/charts/utils/interactions.ts`
- `web/src/lib/charts/utils/speciesColor.ts`

L'interface web compilée (`web/dist`) inclut ces fichiers. Pour réutiliser l'interface dans un
cadre commercial, il faut d'abord les remplacer par du code écrit sans reprendre BirdNET-Go.

## Ce qui n'est pas dans ce dépôt

- Les photos d'oiseaux : l'application les charge depuis Wikimedia Commons et affiche pour chacune
  son auteur et sa licence.
- BirdNET-Go et le modèle BirdNET (K. Lisa Yang Center for Conservation Bioacoustics, Cornell Lab
  of Ornithology, et Chemnitz University of Technology), qui ont leurs propres licences.

---

English summary: bird-frame's own code is MIT-licensed (`LICENSE`). The 16 files listed above are
adapted from BirdNET-Go and remain under CC BY-NC-SA 4.0 (`LICENSES/CC-BY-NC-SA-4.0.txt`).
`species-data/` is under CC BY-SA 4.0 (`species-data/LICENSE`).
