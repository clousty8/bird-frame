---
name: build-app
description: |
  Construit l'interface (npm run build) puis lance bird-frame EN LOCAL, isolé de Railway et de
  local-test/, pour le tester comme il sera réellement servi (serveur + nœud de test + bridge en
  lecture seule, un seul process qui sert l'UI et l'API). Utilise ce skill quand :
  - L'utilisateur tape `/build-app`
  - L'utilisateur dit « build l'app », « lance l'app en local pour tester », « je veux tester
    l'interface », « teste ce que j'ai changé »
  - Tu as fini (ou veux essayer) une feature web/serveur et tu veux la voir tourner dans un vrai
    navigateur, pas juste en tests unitaires
  Jamais de mutation vers Railway (production) ni vers local-test/ (installation BirdNET-Go de
  développement, lue en lecture seule uniquement).
---

# Build-app — Lancer une pile locale isolée pour tester

Ce skill exécute `scripts/build-app.sh`, qui construit `web/dist` puis démarre une pile bird-frame
**complète mais isolée** : un serveur FastAPI qui sert à la fois l'API et l'interface buildée
(`BIRDFRAME_WEB_DIST=web/dist`), un nœud de test enregistré en lecture seule, et un bridge qui lit
`local-test/data/birdnet.db` sans jamais y écrire. Toutes les données de cette pile (base SQLite,
clips, config du nœud, logs, pids) vivent sous `.dev/build-app/<slug>/` du dépôt, où `<slug>` est
le nom du worktree courant (`main` sur le worktree principal) — une pile par worktree, aucune
collision de données entre deux features testées en parallèle.

## ⚠️ L'invariant à ne jamais casser : jamais Railway

`scripts/build-app.sh` ne connaît qu'une seule URL de serveur, `http://localhost:<port>` — ni le
script ni ce skill n'acceptent de la faire pointer ailleurs. Le script contient un garde-fou
explicite qui neutralise les variables d'environnement ambiantes susceptibles de faire fuiter une
URL Railway vers `register_node.py`, et refuse de démarrer s'il détecte une coïncidence avec
`deploy/production.env`. **N'invente jamais de flag pour pointer ce script vers Railway** — si un
test contre la prod est vraiment nécessaire, c'est hors du périmètre de ce skill.

## Étape 1 — Vérifier qu'aucune autre pile n'occupe déjà le port

Par défaut, le serveur écoute sur `:8090` — le même port par défaut que `scripts/dev-up.sh`. Si
`dev-up.sh` tourne déjà (ou un autre `build-app.sh` sur un autre worktree), lance avec
`--port <autre-port>` :

```bash
./scripts/build-app.sh --port 8091
```

Le script détecte un port déjà occupé et donne une erreur claire plutôt que d'échouer
silencieusement ou de perturber l'autre pile.

## Étape 2 — Lancer

```bash
./scripts/build-app.sh
```

Ce que ça fait, dans l'ordre : `npm run build` dans `web/` (installe les dépendances npm si
`node_modules` est absent) → démarre le serveur isolé (`BIRDFRAME_ENV=dev`,
`BIRDFRAME_WEB_DIST=web/dist`, données sous `.dev/build-app/<slug>/data/`) → enregistre, une
seule fois, un nœud de test en lecture seule via `scripts/register_node.py --node-readonly`
(jamais de mutation contre `localhost:8080`, l'API BirdNET-Go de `local-test/`) → démarre le
bridge correspondant, qui lit `local-test/data/birdnet.db` en lecture seule → ouvre
`http://localhost:<port>` avec `open`.

Si `local-test/data/birdnet.db` n'existe pas encore (jamais lancé `local-test/start.sh`), le
script démarre quand même le serveur et l'UI (testables à vide) mais saute l'enregistrement du
nœud et le bridge — il le dit clairement plutôt que d'échouer.

Idempotent : relancer ne redémarre pas ce qui tourne déjà (comme `dev-up.sh`). Les données
persistent entre deux lancements — pour repartir de zéro, supprimer `.dev/build-app/<slug>/` à
la main.

## Étape 3 — Tester

Le navigateur s'ouvre sur `http://localhost:<port>` (ou l'ouvrir soi-même si `open` a échoué,
par ex. en environnement sans interface graphique). C'est un serveur unique qui sert l'UI
buildée ET l'API — pas de rechargement à chaud : toute modification du code source nécessite de
relancer `./scripts/build-app.sh` pour reconstruire `web/dist`.

## Étape 4 — Arrêter

```bash
./scripts/build-app.sh --stop
```

Arrête le serveur et le bridge de **ce worktree** uniquement (autre worktree = autre pile, non
affectée). Ne touche jamais à `local-test/` (BirdNET-Go continue de tourner si c'était déjà le
cas) ni à `web/dist`.

## Rapporter

Indique à l'utilisateur :
- l'URL ouverte (`http://localhost:<port>`),
- que la pile est **isolée** (`.dev/build-app/<slug>/`) → aucun impact sur Railway, sur
  `local-test/`, ni sur une autre feature en cours de test dans un autre worktree,
- comment tout arrêter (`./scripts/build-app.sh --stop`).

## `/build-app` vs `./scripts/dev-up.sh` — lequel utiliser

Ce sont deux outils différents, pas des redondances :

- **`/build-app`** (ce skill) : teste l'interface **telle qu'elle sera vraiment servie** — un
  seul process, UI buildée en statique, comme en production. C'est le bon choix pour valider une
  feature avant de la considérer terminée, dans un worktree isolé, sans jamais risquer Railway
  ni la base de développement partagée.
- **`./scripts/dev-up.sh`** : mode développement actif, avec Vite en rechargement à chaud
  (`:5173`) — pour itérer rapidement sur du code frontend/serveur en le voyant se recharger tout
  seul. Il pointe sur la pile de démo S1 partagée (`server/data/`, nœud « pornic »), **pas**
  isolée par worktree : à utiliser depuis le worktree où l'on développe activement, pas pour
  valider plusieurs features en parallèle.

En résumé : `dev-up.sh` pendant qu'on écrit le code, `/build-app` une fois qu'on veut vérifier
que ça marche pour de vrai avant de dire que c'est fini.

## Ce que ce skill ne fait PAS

- Toucher à Railway, de quelque façon que ce soit (garde-fou explicite dans le script)
- Modifier `local-test/` (le bridge de cette pile est toujours en lecture seule)
- Fusionner sur `dev` ou publier quoi que ce soit (→ `/release`)
- Offrir du rechargement à chaud (→ `./scripts/dev-up.sh` pour ça)
- Nettoyer `.dev/build-app/<slug>/` automatiquement (les données persistent entre deux
  lancements, exprès, pour ne pas perdre l'état pendant qu'on teste)
