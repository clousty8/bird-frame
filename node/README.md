# node/ — le bridge bird-frame

Bridge Python colocalisé avec chaque installation BirdNET-Go. Lit `birdnet.db` **en lecture
seule**, pousse les détections/prédictions/clips vers le serveur bird-frame, relaie le bloc
« en écoute » quasi temps réel, envoie un heartbeat de supervision, et exécute localement (cycle
CSRF) les commandes de pilotage créées par le serveur.

Référence normative : `docs/api-contract.md` (en particulier §4 ingestion, §5 commandes, §7.1
configuration). `docs/architecture.md` pour le contexte général, `docs/plan.md` pour les lots
(WP-02, WP-03, WP-06, WP-08, WP-11 côté bridge).

## Installer

```bash
cd node
uv sync
```

## Lancer

```bash
uv run python -m bridge --config node/config/pornic.env            # boucle continue
uv run python -m bridge --config node/config/pornic.env --once     # un seul cycle de sync, puis sortie
```

`node/config/pornic.env.example` donne un exemple complet (S1, Mac d'Armand). Le vrai fichier
`node/config/<slug>.env` est produit par `scripts/register_node.py` (hors du périmètre de ce
lot — voir la racine du dépôt) et n'est **jamais** versionné (`.gitignore` : `node/config/*.env`).

Sans réseau, pour vérifier que la lecture de `birdnet.db` fonctionne :

```bash
uv run python -m bridge.inspect --db /chemin/vers/birdnet.db --since-id 0 --limit 5
```

## Tester

```bash
uv run pytest              # 142 tests, aucun ne touche local-test/ ni ne mute BirdNET-Go
uv run ruff check bridge/ tests/
uv run ruff format bridge/ tests/
```

Toutes les bases SQLite de test sont construites dans `tmp_path` (jamais `local-test/`) ; tous
les appels HTTP sont mockés avec `respx` (jamais de vraie mutation contre BirdNET-Go).

## Mode `BRIDGE_NODE_READONLY=1` (S1, contrat §7.1)

Sur le Mac d'Armand, le nœud BirdNET-Go **est** l'installation de développement `local-test/` :
BirdNET-Go réécrirait `local-test/config.yaml` à la moindre mutation de settings (`main.name`
notamment). En S1, `node/config/<slug>.env` DOIT donc porter `BRIDGE_NODE_READONLY=1` :

- la boucle de commandes (`node/bridge/commands.py::run_commands_loop`) n'est **jamais** lancée —
  aucune requête `PATCH`/`PUT`/`DELETE`/`POST` mutante n'est jamais émise contre
  `BRIDGE_NODE_API` ;
- à la place, `run_readonly_reminder_loop` journalise en WARNING, au démarrage puis toutes les
  heures, le nombre de commandes en attente côté serveur (lecture seule de
  `GET /nodes/{id}/commands`, sans jamais les exécuter ni les acquitter) ;
- sync, clips, relais « en écoute » et heartbeat continuent de fonctionner normalement (ce sont
  des lectures, ou des écritures vers le **serveur**, jamais vers BirdNET-Go) ;
- `scripts/register_node.py --node-readonly` (hors périmètre de ce lot) écrit
  `BRIDGE_NODE_READONLY=1` et enregistre le nœud avec `"auto_main_name": false`, pour que le
  serveur ne mette même pas la commande `set_main_name` en file.

## Vérifié en conditions réelles (lecture seule)

```bash
uv run python -m bridge.inspect \
  --db /Users/armand_mounsi/Documents/repositories/bird-frame/local-test/data/birdnet.db \
  --since-id 0 --limit 5
```

imprime 5 vraies détections de Pornic (espèce, confiance, prédictions triées par confiance). Le
`mtime` et le `sha256` de `local-test/data/birdnet.db` sont strictement inchangés avant/après —
vérifié aussi après un `--once` complet (config `BRIDGE_NODE_READONLY=1`, pointé sur ce
`birdnet.db`, serveur bird-frame injoignable puisqu'il n'existe pas encore) : le bridge lit le
dictionnaire FR réel du nœud (`GET /api/v2/species/dictionary/fr`, 13 837 entrées), échoue
proprement sur le `POST /sync` (connexion refusée), journalise un WARNING clair et sort avec le
code 0 — jamais de crash silencieux ni de mutation.

## Les quatre boucles (mode continu, sans `--once`)

| Boucle | Module | Cadence | Ce qu'elle touche |
|---|---|---|---|
| Synchro (WP-03) + clips demandés (WP-08 amendé) | `bridge/pusher.py` | `BRIDGE_SYNC_INTERVAL_S` (20 s), immédiat si lot plein | lecture `birdnet.db`, `POST` serveur |
| Relais « en écoute » (WP-06) | `bridge/pending_relay.py` | évènementiel (SSE local) + 30 s | `GET` SSE local, `POST` serveur |
| Heartbeat | `bridge/heartbeat.py` | `BRIDGE_HEARTBEAT_INTERVAL_S` (60 s) | `GET` locaux (app/config, settings/audio, dynamic-thresholds), `POST` serveur |
| Commandes (WP-11) | `bridge/commands.py` | `BRIDGE_COMMANDS_INTERVAL_S`/`_FAST_INTERVAL_S` | `GET`/`POST` serveur, mutations CSRF locales (**sauf en mode readonly**) |
| Mise à jour (§12, en plus des quatre) | `bridge/updater.py` | démarrage, puis `BRIDGE_UPDATE_INTERVAL_S` (600 s) ou dès que le heartbeat annonce une version plus récente | `GET` serveur ; fichiers de l'installation gérée seulement (ne fait rien hors installation gérée) |

Chaque boucle a son propre backoff exponentiel (`bridge/backoff.py`, base 5 s, plafond 5 min,
jitter ±25 %) et sa propre classification d'erreur (`bridge/http_errors.py`, la table commune du
contrat §4.1). Une panne d'une boucle n'affecte jamais les autres.

## WP-11 : ce qui est testé, ce qui ne l'est pas

Handlers de commandes **implémentés et testés** (respx, contre un faux serveur BirdNET-Go) :
`set_species_threshold` (y compris la clé « nom commun FR » qui masquerait sinon la nôtre — via le
nom canonique **ou** un alias, cf. correctif du 27/09/2026 ci-dessous — et le retrait de seuil via
`PUT /settings` complet), `exclude_species`, `unexclude_species`, `include_species`,
`uninclude_species`, `reset_dynamic_threshold`, `set_main_name`, `mark_detection_reviewed`.

Handlers `start_live` / `live_heartbeat` / `stop_live` (vague 4, WP-19) : squelette conforme aux
routes et payloads figés par le contrat (§5.3), testés avec un serveur BirdNET-Go **mocké**
(respx) mais **jamais contre le vrai binaire** — pas de session HLS disponible pendant ce lot.
Point d'attention explicite avant la vague 4 : les noms de champs JSON de la réponse HLS
(`streamToken`, `playlistUrl`, `playlistReady`, `streamEpoch`) sont une hypothèse cohérente avec
le reste de l'API v2 observée (camelCase), jamais vérifiée contre un vrai flux. La session live
s'auto-termine désormais aussi après 60 s sans `live_heartbeat` (§5.3), pas seulement sur
`stop_live` explicite.

Un `kind` du contrat qui n'aurait toujours pas de handler (évolution future du contrat) est
journalisé en ERROR et **jamais acquitté** — il reste visible et sera redélivré par le serveur
plutôt que silencieusement perdu.

## Correctifs du 27/09/2026 (revue de code du bridge)

- **Une boucle en panne ne tue plus les trois autres.** Les quatre boucles tournent toujours dans
  un seul `asyncio.TaskGroup` (`bridge/__main__.py`), mais chacune est maintenant enveloppée par
  `_supervised(...)` : une exception inattendue y est journalisée en CRITICAL au lieu de se
  propager et d'annuler les tâches sœurs. En complément, les erreurs de lecture locale de
  `birdnet.db` (`SqliteReaderError`, y compris depuis `fetch_max_detection_id`, qui ne les
  enveloppait pas jusqu'ici) sont maintenant capturées à la racine dans `sync_once` et
  `run_heartbeat_loop`, avec le même backoff que pour les erreurs réseau — elles n'ont donc plus
  besoin du filet `_supervised` en pratique.
- **Relais « en écoute » (`pending_relay.py`)** : un item SSE `pending` mal formé (champ manquant)
  est désormais ignoré et journalisé en WARNING au lieu de tuer silencieusement `_consume_sse` pour
  le reste du process. Le backoff de reconnexion est aussi remis à zéro dès qu'une connexion SSE
  réussit, pas seulement à la réception d'un évènement.
- **Session HLS live (`commands.py`)** : le garde-fou de 60 s sans `live_heartbeat` (§5.3, déjà
  écrit dans `expires_at_monotonic` mais jamais lu) est maintenant appliqué par
  `_hls_heartbeat_loop`, qui arrête la session et libère le nœud plutôt que de la laisser orpheline.
- **Déduplication des commandes (`commands.py`)** : `handle_batch` ne marque une commande « vue »
  que si elle a été effectivement acquittée. Une commande en échec transitoire (nœud injoignable)
  peut donc de nouveau être réexécutée à sa redélivrance, au lieu d'être sautée en silence pendant
  30 min.
- **Upload de clip (`pusher.py`)** : un clip dépassant 25 Mo (§4.3) n'est plus relu en mémoire à
  chaque cycle ; il est signalé `missing` sans upload. Une réponse 413 du serveur est aussi
  maintenant traitée explicitement (signalement `missing`) au lieu de tomber dans la branche
  générique qui laissait le serveur redemander indéfiniment le même clip. Le 404
  `detection_not_found` sur `POST .../missing` (§4.4) est désormais journalisé en WARNING, comme
  son équivalent déjà loggé sur l'upload de clip.

## Décisions prises hors contrat (à confirmer ou corriger par la suite)

1. **Jeton CSRF = valeur du cookie `csrf`, pas le champ JSON `csrfToken`.** Une vérification
   `curl` réelle (fournie en amont de ce lot : `POST /api/v2/range/species/test`) a montré que ces
   deux valeurs diffèrent sur le nœud local, et que c'est la valeur du **cookie** que le
   middleware CSRF accepte dans `X-CSRF-Token`. `bridge/csrf_client.py` lit donc le jeton depuis
   `client.cookies["csrf"]` après le `GET /api/v2/app/config`, pas depuis le corps JSON. Documenté
   en tête du module.
2. **`BRIDGE_MIC_STATUS_TOOL`** (variable d'environnement non listée au contrat §7.1) : chemin
   optionnel vers `local-test/tools/mic-status` (macOS 14+, cf. `CLAUDE.md` racine), utilisé par le
   heartbeat pour déterminer `mic_device_name`/`mic_healthy`. Le contrat référence cet outil par
   convention (« S1 macOS : `local-test/tools/mic-status <PID>` ») sans lui donner de variable
   dédiée ; vide/absent (défaut) laisse simplement ces deux champs à `null`, comportement conforme
   au contrat (« si déterminable »).
3. **Bug corrigé pendant les tests, pas seulement pour eux** : la boucle SSE du relais « en
   écoute » (`_consume_sse`) pouvait reconnecter en boucle chaude, sans aucun délai, si le flux
   local se terminait proprement (sans exception) — par ex. un redémarrage du nœud fermant la
   connexion sans erreur réseau côté client. Corrigé : **toute** sortie de la boucle de lecture
   (succès sans évènement, ou exception) passe désormais par le backoff avant de reconnecter, et
   l'arrêt (`stop_event`) annule explicitement les tâches en cours plutôt que de compter sur une
   simple relecture de l'évènement (une lecture réseau bloquée ne verrait jamais le `stop_event`
   sinon). Repéré par un test d'intégration qui, sans ce correctif, ne terminait jamais.

## Fichiers

```
node/
├── pyproject.toml
├── README.md                     # ce fichier
├── config/
│   └── pornic.env.example        # exemple documenté (§7.1) — le vrai .env n'est jamais versionné
├── state/                        # BRIDGE_STATE_FILE (curseur JSON), ignoré par git
├── bridge/
│   ├── __main__.py                # point d'entrée (--config, --once)
│   ├── config.py                  # chargement/validation de node/config/<slug>.env
│   ├── sqlite_reader.py           # WP-02 : lecture seule birdnet.db
│   ├── inspect.py                 # CLI de vérification sans réseau
│   ├── state.py                   # curseur local (optimisation, jamais faisant foi seul)
│   ├── pusher.py                  # WP-03 + WP-08 amendé : sync + clips demandés
│   ├── pending_relay.py           # WP-06 : relais SSE « en écoute »
│   ├── sse.py                     # parseur SSE minimal
│   ├── heartbeat.py                # supervision (micro, disque, version, PID, seuils dynamiques)
│   ├── species_dictionary.py       # cache GET /api/v2/species/dictionary/fr (résolution common_name)
│   ├── csrf_client.py              # WP-11 : cycle CSRF unique contre BirdNET-Go local
│   ├── commands.py                 # WP-11 : dispatch par kind, dédup, ack
│   ├── backoff.py                  # backoff exponentiel commun
│   ├── http_errors.py              # classification des réponses HTTP (§4.1)
│   ├── updater.py                  # §12 : mise à jour automatique (installation gérée)
│   └── time_utils.py               # formatage des instants UTC (§1.3)
├── deploy/
│   ├── run-bridge.sh               # §12.5 : superviseur (lance current, retour arrière)
│   ├── fr.birdframe.bridge.plist.template     # agent launchd (macOS)
│   └── bird-frame-bridge.service.template     # service systemd (Pi, installation manuelle)
└── tests/                          # pytest, respx — jamais local-test/, jamais de vraie mutation
```

## Installation gérée et mise à jour automatique (contrat §12)

Pour qu'un nœud se mette à jour tout seul à chaque release, le bridge est installé hors du dépôt,
dans une « installation gérée », lancée par launchd (macOS) et mise à jour par le serveur :

```bash
scripts/install-node.sh --config node/config/pornic.env            # racine ~/.bird-frame-node
scripts/install-node.sh --config node/config/pornic.env --no-launchd --root /tmp/essai   # sans agent
tail -f ~/.bird-frame-node/logs/bridge.log
launchctl print gui/$(id -u)/fr.birdframe.bridge | grep -E 'state|pid|last exit'
scripts/uninstall-node.sh                 # garde config/ et state/ ; --purge pour tout supprimer
```

`install-node.sh` (idempotent ; en cas d'échec, l'installation précédente est restaurée) copie le
bridge du dépôt dans `~/.bird-frame-node/versions/<VERSION>`, y fait `uv sync --frozen --no-dev` et
un essai à blanc, copie la configuration dans `config/bridge.env` (chmod 600) en y **forçant**
`BRIDGE_INSTALL_ROOT`, `BRIDGE_AUTO_UPDATE=1`, `BRIDGE_UV` (chemin absolu de `uv`) et
`BRIDGE_STATE_FILE=<racine>/state/<slug>.json` (l'ancien curseur est repris s'il existe), bascule le
lien `current`, installe `bin/run-bridge.sh` et charge l'agent `fr.birdframe.bridge`
(`~/Library/LaunchAgents/`, `RunAtLoad` + `KeepAlive`). Il refuse une racine située dans
`local-test/` et n'y écrit jamais rien. Linux (Pi) : mêmes fichiers avec `--no-launchd` (automatique
hors macOS), puis `node/deploy/bird-frame-bridge.service.template` à installer à la main.

Variables (dans le fichier de configuration, comme les autres `BRIDGE_*`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `BRIDGE_AUTO_UPDATE` | `0` | `1` = mise à jour automatique (forcé à 1 par `install-node.sh`) |
| `BRIDGE_INSTALL_ROOT` | vide | racine de l'installation gérée, chemin absolu |
| `BRIDGE_UPDATE_INTERVAL_S` | `600` | cadence de vérification (≥ 10 s) ; le heartbeat réveille aussi la vérification dès que le serveur annonce une version plus récente |
| `BRIDGE_UV` | `uv` | exécutable `uv` utilisé pour installer la nouvelle version |

Déroulé d'une mise à jour (`bridge/updater.py`) : `GET /nodes/{id}/update` ; si la version annoncée
est plus récente (`X.Y.Z` numérique), téléchargement (même origine que le serveur), vérification
taille + SHA-256, contrôle de chaque entrée de l'archive (ni chemin absolu, ni `..`, ni lien, ni
fichier spécial), extraction dans `versions/<v>`, `uv sync --frozen --no-dev`, essai à blanc
`python -m bridge --help`, `previous` ← version courante, bascule atomique de `current`, nettoyage des
versions plus anciennes que `previous`, puis sortie en **code 75** : `run-bridge.sh` relance aussitôt
la nouvelle version. Tout échec est journalisé en ERROR, laisse l'ancienne version en place, remonte
dans le heartbeat (`update_status = {state: "failed", target_version, error}`, visible dans
`GET /nodes`) et la même version n'est pas retentée avant 1 h.

Superviseur (`run-bridge.sh`) : si la version courante plante au démarrage (sortie non nulle en moins
de 60 s, hors code 2 = configuration ou `birdnet.db` inaccessibles) 3 fois en 5 minutes, il rebascule
`current` sur `previous`, l'écrit dans le journal et ajoute la version fautive à
`state/rolled-back-versions` : l'updater ne la retentera plus (retirer la ligne pour réessayer).
Codes de sortie du bridge : 0 arrêt normal, 2 configuration/`birdnet.db` inutilisable, 75 mise à jour
installée.

Vérifié en réel (28/09/2026, `uv` réel, serveur uvicorn réel, `--no-launchd`, dossier temporaire) :
bridge 0.1.0 installé par `install-node.sh`, serveur 0.1.1 publiant son bundle → bascule en 0.1.1 et
relance par le superviseur en ~1 s, heartbeat suivant `bridge_version = 0.1.1`,
`update_status.state = up_to_date`.

**À savoir sur le Mac d'Armand** :
- un agent launchd n'hérite pas des autorisations du Terminal : `BRIDGE_DB_PATH`/`BRIDGE_CLIPS_DIR`
  sont sous `~/Documents` (protégé par macOS). Si `logs/bridge.log` montre « Operation not
  permitted », donner l'accès complet au disque à l'interpréteur Python de la version installée (le
  chemin exact est affiché par `install-node.sh`) ;
- ne pas faire tourner en même temps le bridge de `scripts/dev-up.sh` et l'agent pour le même nœud
  (`install-node.sh` avertit si le bridge de dev tourne).
