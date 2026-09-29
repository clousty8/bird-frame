# bird-frame — cadre e-ink de détection d'oiseaux

## But
Reproduire pour Armand un cadre photo e-ink qui affiche les oiseaux détectés autour de chez lui,
sous forme de planches naturalistes façon XIXe siècle.

## Les deux projets de référence

### 1. Fugleramme — https://github.com/arnegiacomo/fugleramme
Détection **audio** (micro) via **BirdNET-Go** (modèle Cornell Lab of Ornithology / Univ. Chemnitz).
- Raspberry Pi 5 + refroidisseur actif (présenté comme obligatoire)
- Écran Pimoroni Inky Impression 13,3" (~200 €)
- Micro USB (ou analogique + carte son USB)
- Cadre IKEA RÖDALM 21x30 (A4)
- Budget annoncé : 380-450 €
- Affiche jusqu'à 40 espèces sur 24 h, tailles relatives basées sur la base **AVONET**
  (masse corporelle réelle), arrangement en spirale (les plus gros au centre)
- Ne redessine que si la liste change (économie e-ink). Version web alternative. MIT.
- Install : une commande curl.

### 2. Inky Bird Frame — https://github.com/veteranbv/inky-bird-frame
Pas de détection locale : agrège les **observations déclarées** autour de chez soi.
- Raspberry Pi Zero 2 W dans le cadre + un Pi 4 / Mac / Linux comme serveur
- Inky Impression 13,3" 6 couleurs, 1600x1200
- Sources de données : iNaturalist (défaut), eBird (rayon 50 km, 30 j), BirdWeather
- Planches générées par IA (OpenAI Codex via abonnement ChatGPT) + pipeline IA de validation
- Catalogue partagé de 71 espèces approuvées
- Rotation séquentielle / aléatoire / pondérée
- Notifs Pushover, Apprise (Discord, Slack, Home Assistant). MIT.
- Coût : ~360 USD le cadre (dont 275 USD l'écran), +350 USD avec un Pi 4.

## Différence clé
Fugleramme = ce que **mon** micro entend. Inky Bird Frame = ce que **les autres** ont observé près de chez moi.
Les deux sont combinables (BirdWeather est justement le pont entre les deux mondes).

## État
Phase recherche. Rapports dans `research/`.

## Décision issue de la recherche (21/09/2026)
Partir de **Fugleramme** + **BirdNET-Go**, pas d'Inky Bird Frame. Commencer par faire tourner
BirdNET-Go en Docker sur le Mac avant tout achat. Lire `research/00-SYNTHESE.md`.
⚠️ Les fichiers `research/02b` à `02e` sont des brouillons dont les prix sont faux.

## Étape 0 réalisée (21/09/2026) — `local-test/`
BirdNET-Go tourne en **binaire natif darwin-arm64** sur le micro intégré du Mac (pas Docker :
Colima/Docker Desktop ne donnent pas accès aux périphériques audio de l'hôte). UI native sur
http://localhost:8080, rien à développer. `local-test/start.sh` / `stop.sh`, réglages dans
`local-test/config.yaml`. Détection validée de bout en bout (Merle noir, Mésange charbonnière).
Localisation réglée sur Le Mans (lignes 213-214 de `local-test/config.yaml`) : 189 espèces retenues.

## Une base par lieu (25/09/2026)
La base active est toujours `local-test/data/birdnet.db` + `local-test/data/clips/` (inséparables :
chemins de clips relatifs). Les lieux archivés sont dans `local-test/sauvegardes/<lieu>/`, chacun avec
un README (stats + procédure de restauration). Lieu 1 (Le Mans, 21-23/09, 878 détections) archivé ;
une base neuve tourne pour le lieu 2 = **Pornic** (depuis le 26/09 : lat 47.1155, lon -2.1046,
mairie selon geo.api.gouv.fr, INSEE 44131 ; 198 espèces retenues). Les détections du 25/09 soir au
26/09 midi ont été faites avec les coordonnées du Mans encore en place. Bascule manuelle pour l'instant (stop → mv → start) ;
une appli de bascule entre lieux est prévue plus tard.

## Fork de l'interface + audio top 10 (26/09/2026)
- **Audio** : `local-test/clip-retention.py` (lancé/arrêté par start.sh/stop.sh, boucle 10 min) ne garde
  clip + spectrogrammes que des 10 meilleures détections (confiance) par espèce. Choix d'Armand :
  toutes les lignes restent en base (stats justes), seul l'audio part. Verrouillées épargnées.
- **Interface** : fork github.com/clousty8/birdnet-go, branche `bird-frame` basée sur le tag `20260823`
  (= version du binaire), cloné dans `birdnet-go-ui/`. Seul le frontend Svelte est modifié : grande
  photo, spectrogramme seulement pendant l'écoute. Pas de recompilation Go : le binaire sert
  `local-test/data/frontend/dist` s'il existe (dev mode, cwd = data/). `local-test/deploy-ui.sh` build + copie.
  Les photos avicommons font 320x240 (taille fixée côté Go) : les agrandir davantage demanderait de
  recompiler le binaire (Go 1.27 + CGO + TFLite).
- **Photos manquantes** : `dashboard.thumbnails.fallbackpolicy: all` (ligne 336 de config.yaml, activé le
  26/09) → si avicommons n'a pas l'espèce (ex. Goéland argenté, *Larus argentatus*), BirdNET-Go prend
  la photo principale de Wikimedia/Wikipédia.

## Bascule silencieuse de micro (27/09/2026)
Quand le micro USB disparaît un instant, macOS bascule la capture de BirdNET-Go sur le micro du Mac,
sans rien dans les logs BirdNET-Go (qui affichent toujours le QuadCast) et sans retour en arrière.
Constaté le 26/09 de 16h43 à 00h03 (349 détections via le micro du Mac). Parade : `local-test/mic-watchdog.sh`
(lancé par start.sh) qui interroge macOS via `local-test/tools/mic-status <PID>` (objets process CoreAudio,
macOS 14+) et relance BirdNET-Go. Ne jamais se fier à audio.log pour savoir quel micro est utilisé.


## Workflow de développement (28/09/2026)
Dépôt public `clousty8/bird-frame` (licences : code en MIT `LICENSE` ; 16 fichiers web adaptés de BirdNET-Go en CC BY-NC-SA 4.0 ; `species-data/` en CC BY-SA 4.0 — carte dans `NOTICE.md`), branches `dev` (travail) et `main` (production — Railway
redéploie automatiquement à chaque push sur `main`). CI sur PR `dev`→`main` et push `dev`
(`.github/workflows/ci.yml`, check requis `test`) ; fusion **automatique, sans pause de review**
(Armand seul sur ce dépôt). `/build-app` (`scripts/build-app.sh`) lance une pile locale isolée
(par worktree, jamais Railway, `local-test/` en lecture seule) pour tester visuellement ;
`scripts/dev-up.sh` reste le mode développement actif (Vite, rechargement à chaud). `/release`
(`.claude/skills/release/SKILL.md`) publie une version : bump → CHANGELOG.md → PR → CI → merge →
tag/release GitHub → suivi du déploiement Railway et de la mise à jour des nœuds.

## Production (28/09/2026)
- **Interface + serveur sur Railway** : https://web-production-6eb1d.up.railway.app (URL aussi dans
  `deploy/production.env`). Projet Railway `bird-frame` (id `fc859082-4d5b-4cfa-b3ea-eb2801b54bd5`),
  environnement `production` (`bc2f1518-507e-499e-8165-3891bc448089`), service `web`
  (`c4bde3f5-e9e1-4de0-b55c-9e412d6fe09f`), volume `bird-frame-data` sur `/data` (base SQLite, clips,
  photos). Build par le `Dockerfile` racine à chaque push sur `main`.
- **Accès** : lecture libre ; mot de passe unique pour modifier (règles, revues, faux négatifs,
  seuils) et pour **écouter les enregistrements** (voix privées possibles). Mot de passe dans le
  trousseau macOS (service « bird-frame », compte « interface ») ; secrets de prod dans
  `deploy/production.secrets.env` (gitignoré, jamais commité). Changer le mot de passe :
  `uv run --project server python scripts/hash_password.py` puis variable Railway
  `BIRDFRAME_UI_PASSWORD_HASH`.
- **Calcul en local** : BirdNET-Go (`local-test/`) + un bridge « installé » (`scripts/install-node.sh`,
  racine `~/.bird-frame-node`, agent launchd `fr.birdframe.bridge`) qui pousse vers Railway et **se met
  à jour tout seul** à chaque release (il télécharge le bundle servi par le serveur de la même version).
  Ne pas faire tourner en plus un bridge `dev-up.sh` configuré vers Railway.

## Refonte « nœud + serveur » (27/09/2026) — nouvelle application dans ce dépôt
Décision (workflow 3 architectes + 3 juges) : BirdNET-Go reste un **capteur inchangé** (une instance
par site) ; un **bridge** Python colocalisé (`node/`) lit `birdnet.db` en lecture seule et **pousse**
détections + prédictions secondaires + clips top-5 vers un **serveur FastAPI + SQLite** (`server/`)
qui porte la **nouvelle UI Svelte 5 + Tailwind 4** (`web/`, 4 sections : tableau de bord, espèces,
statistiques, système). Multi-sites natif (sélecteur de site). Docs de référence, à lire avant tout
lot : `docs/architecture.md` (vision, modèle de données), `docs/api-contract.md` (**fait foi** sur
architecture.md en cas d'écart, §10.1), `docs/plan.md` (lots WP-01…WP-22 ; vagues 1-3 livrées).
- Lancer / arrêter la pile de dev sur le Mac : `scripts/dev-up.sh` / `scripts/dev-down.sh`
  (serveur :8090, bridge, vite :5173 ; logs et pids sous `.dev/`). UI : http://localhost:5173.
  `local-test/start.sh` reste le seul moyen de lancer BirdNET-Go lui-même.
- **S1 = nœud en lecture seule** : `node/config/pornic.env` a `BRIDGE_NODE_READONLY=1` ; le bridge
  n'envoie jamais de mutation à `localhost:8080` (sinon BirdNET-Go réécrirait `local-test/config.yaml`).
  Les règles par espèce saisies dans l'UI restent « en attente » côté serveur tant qu'un vrai nœud
  (Pi) n'est pas déployé.
- Tests : `cd server && uv run pytest -q` · `cd node && uv run pytest -q` · `cd web && npm run test && npm run check`.
- Fiches espèces : `species-data/` (univers France 368 espèces `species_universe_fr.json`,
  `build_base.py` → `base/` sans IA, `sheets/` rédigées par agents Haiku, `aliases.json` pour les
  synonymes BirdNET ↔ noms actuels, ex. *Coloeus monedula* → *Corvus monedula* ; rattrapage :
  `server/scripts/recanonicalize.py`). Le serveur les charge au démarrage.
- Licence : tout ce qui est copié de `birdnet-go-ui/frontend` est listé dans `web/NOTICE.md`
  (CC BY-NC-SA 4.0) avec en-tête par fichier ; le reste du code est en MIT. Tout nouveau fichier
  copié de BirdNET-Go doit être ajouté à `web/NOTICE.md` ET à `NOTICE.md` (racine).
- Pas encore fait : audio live à distance (WP-19), Tailscale + premier Pi (WP-18), migration de
  l'archive Le Mans (WP-17).
