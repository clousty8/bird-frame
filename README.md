# bird-frame

Cadre photo e-ink qui affiche les oiseaux détectés autour de chez Armand, sous forme de planches
naturalistes. Détection par **BirdNET-Go** (micro), synchronisée vers un serveur compagnon
multi-sites, avec un dashboard web dédié. Contexte complet, décisions et historique :
`CLAUDE.md` (racine).

## Architecture en 10 lignes

- **`local-test/`** — installation BirdNET-Go de développement (binaire natif, micro du Mac,
  base SQLite `birdnet.db`). **Jamais modifiée par le reste du dépôt.**
- **`node/`** — le **bridge** : lit `birdnet.db` en lecture seule, pousse détections/clips vers le
  serveur, relaie le bloc « en écoute » en quasi temps réel, envoie un heartbeat, exécute
  localement les commandes de pilotage (sauf en mode lecture seule, voir plus bas).
- **`server/`** — API FastAPI + SQLite (`server/data/bird-frame.db`) : ingestion multi-nœuds,
  top-5 clips par espèce/site, fiches espèces, calendrier, statistiques, règles, API navigateur.
- **`web/`** — dashboard Vite + Svelte 5 + Tailwind v4 : tableau de bord, espèces, statistiques,
  système.
- **`species-data/`** — univers France (368 espèces) + fiches générées, chargés par le serveur.
- **`scripts/`** — `register_node.py` (enregistrement d'un nœud), `dev-up.sh`/`dev-down.sh`
  (démo locale S1, ce document).

Référence normative complète : `docs/architecture.md` (vue d'ensemble, décisions) et
`docs/api-contract.md` (**LE contrat** : tout nom de champ/route/format vient de là). Lots de
travail : `docs/plan.md`.

## Lancer la démo S1 (sur ce Mac, cohabitation avec `local-test/`)

Prérequis : `local-test/start.sh` déjà lancé (BirdNET-Go tourne sur `:8080`), `uv` et `npm`
installés.

```bash
./scripts/dev-up.sh
```

Démarre, en arrière-plan, idempotent (relancer ne redémarre pas ce qui tourne déjà) :

1. le **serveur** FastAPI sur `http://localhost:8090` (`server/.env` généré au premier lancement
   avec un jeton admin aléatoire s'il n'existe pas encore) ;
2. l'**enregistrement du nœud** « pornic » (une seule fois, via `scripts/register_node.py
   --node-readonly` — voir plus bas) ;
3. le **bridge** en boucle continue, pointé sur `local-test/data/birdnet.db` ;
4. le **frontend** Vite sur `http://localhost:5173` (proxy `/api` et `/health` vers `:8090`).

Ouvrir **http://localhost:5173**. Logs sous `.dev/logs/{server,bridge,vite}.log`, pids sous
`.dev/pids/`. Tout arrêter (sans toucher à `local-test/`) :

```bash
./scripts/dev-down.sh
```

### Mode « nœud en lecture seule » (S1, obligatoire sur ce Mac)

En S1, le nœud visé par le bridge **est** l'installation de développement `local-test/` : la
moindre mutation de settings (ex. `main.name`) ferait réécrire `local-test/config.yaml` par
BirdNET-Go. `dev-up.sh` enregistre donc toujours le nœud avec `--node-readonly`
(`BRIDGE_NODE_READONLY=1` dans `node/config/pornic.env`) : le bridge ne lance **jamais** sa
boucle de commandes et n'émet **aucune** requête mutante (`PATCH`/`PUT`/`POST`/`DELETE`) contre
`localhost:8080`. Sync, clips, relais « en écoute » et heartbeat restent actifs (lectures, ou
écritures vers le serveur uniquement). Détail : `docs/api-contract.md` §7.1, `node/README.md`.

## Où sont les docs

| Document | Contenu |
|---|---|
| `docs/architecture.md` | vue d'ensemble, composants, flux de données, décisions |
| `docs/api-contract.md` | **le contrat** — routes, schémas JSON, codes d'erreur, config |
| `docs/plan.md` | lots de travail (WP-xx), dépendances, critères de démonstration |
| `server/README.md` | démarrage serveur, migrations Alembic, variables d'environnement |
| `node/README.md` | démarrage bridge, les 4 boucles, mode lecture seule |
| `web/README.md`, `web/NOTICE.md` | démarrage frontend, attribution du code copié (CC BY-NC-SA 4.0) |
| `CLAUDE.md` | historique du projet, décisions prises au fil de l'eau |
