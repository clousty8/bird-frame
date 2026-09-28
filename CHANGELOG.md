# Changelog

Ce qui change à chaque version, en français et orienté utilisateur (pas le détail technique).

Convention : une section `## vX.Y.Z` par version (la plus récente en haut), avec 3 à 6 puces
courtes. Le skill `/release` (`.claude/skills/release/SKILL.md`) ajoute automatiquement la
section de la nouvelle version à partir des commits depuis le dernier tag, et reprend cette
même section comme description de la release GitHub (`gh release create --notes`).

## v0.1.0

Première version.

- Tableau de bord temps réel des détections (photo de l'espèce, nom, confiance, clip audio)
- Fiches espèces illustrées, avec les synonymes de noms gérés automatiquement
- Statistiques (par espèce, par période)
- Page Système : état de chaque nœud (micro, disque, version, dernière détection)
- Multi-sites : plusieurs lieux suivis en parallèle, avec sélecteur
- Interface accessible en ligne (Railway) pendant que la détection continue de tourner
  localement sur le Mac
