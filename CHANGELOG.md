# Changelog

Ce qui change à chaque version, en français et orienté utilisateur (pas le détail technique).

Convention : une section `## vX.Y.Z` par version (la plus récente en haut), avec 3 à 6 puces
courtes. Le skill `/release` (`.claude/skills/release/SKILL.md`) ajoute automatiquement la
section de la nouvelle version à partir des commits depuis le dernier tag, et reprend cette
même section comme description de la release GitHub (`gh release create --notes`).

## v0.2.0

- Le calendrier d'activité quotidienne affiche de nouveau le nombre de détections dans chaque case horaire.
- Fiche espèce remise en page façon Wikipédia : photo entière jamais recadrée, « À propos » juste sous le nom, une seule colonne avec des titres clairs.
- Nouvelle section « Peut-on l'entendre ici ? » : une frise des 12 mois et une phrase simple disent si l'oiseau est normalement présent sur ton site à cette période.
- Le Mans rejoint Pornic : l'archive du 21 au 23 septembre est consultable comme second site dans le sélecteur.
- Plus de badge « généré par IA » sur les fiches.

## v0.1.0

Première version.

- Tableau de bord temps réel des détections (photo de l'espèce, nom, confiance, clip audio)
- Fiches espèces illustrées, avec les synonymes de noms gérés automatiquement
- Statistiques (par espèce, par période)
- Page Système : état de chaque nœud (micro, disque, version, dernière détection)
- Multi-sites : plusieurs lieux suivis en parallèle, avec sélecteur
- Interface accessible en ligne (Railway) pendant que la détection continue de tourner
  localement sur le Mac
