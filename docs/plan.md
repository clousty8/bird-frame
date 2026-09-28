# bird-frame — Plan de lots de travail

> **État au 27/09/2026 (soir)** : vagues 1, 2 et 3 livrées et vérifiées de bout en bout sur le Mac
> (WP-01 → WP-16, avec les amendements : clips poussés par le bridge, spectrogrammes sox côté serveur,
> stats en SQL serveur, fiches = fichiers `species-data/`). WP-11 : boucle de commandes implémentée
> et testée, mais **jamais exercée contre un vrai nœud** (S1 en lecture seule) ; `start_live` /
> `live_heartbeat` / `stop_live` non testés en réel. Reste : vagues 4 et 5.

Compagnon de `docs/architecture.md` (à lire avant tout lot). Chaque lot est pensé pour être confié à
un sous-agent sans qu'il ait besoin de relire les rapports R0-R10 : l'objectif, les fichiers à créer,
les dépendances et le critère de démonstration suffisent. Tailles : **S** (quelques heures), **M**
(une session), **L** (plusieurs sessions/plusieurs jours).

**Règle absolue pour tous les lots de la vague 1 et 2** : aucun fichier sous `local-test/` ou
`birdnet-go-ui/` n'est jamais modifié. Le bridge lit `local-test/data/birdnet.db` uniquement en mode
lecture seule (`sqlite3.connect("file:...birdnet.db?mode=ro", uri=True)`), et n'appelle l'API HTTP du
binaire (`http://localhost:8080`) que par des requêtes déjà exercées ailleurs sans incident
(`GET /api/v2/audio/:id`, `GET /api/v2/spectrogram/:id`, cycle settings/HLS en lecture avant toute
mutation).

---

## Vague 1 — Fondations (S1, Mac, visible vite)

### WP-01 — Squelette serveur FastAPI + SQLite

**Objectif** : un serveur qui démarre, expose `/health`, et a une base SQLite créée par migration.

**Contenu** :
- `server/pyproject.toml` (FastAPI, SQLAlchemy 2.x, Alembic, uvicorn, pytest, httpx, ruff)
- `server/app/main.py` — app FastAPI, route `GET /health` → `{"status": "ok"}`
- `server/app/config.py` — lecture d'un `.env` (chemin DB, port, secret de session)
- `server/app/db.py` — engine SQLAlchemy (`sqlite:///server/data/bird-frame.db`), `SessionLocal`,
  dépendance FastAPI `get_db()`
- `server/app/models/__init__.py`, `server/app/models/base.py` (`DeclarativeBase`)
- `server/migrations/` — Alembic initialisé (`alembic init`), première révision vide
- `server/tests/test_health.py`

**Dépendances** : aucune.
**Taille** : S.
**Démonstration** : `cd server && uvicorn app.main:app --reload` puis `curl localhost:8090/health` →
`{"status":"ok"}`.
**Tests attendus** : `pytest server/tests/test_health.py` vert.

---

### WP-02 — Bridge : lecture seule de `birdnet.db`

**Objectif** : un module Python qui sait lire `local-test/data/birdnet.db` en lecture seule et
produire des objets détection + prédictions déjà résolus (noms scientifiques, tri par confiance).

**Contenu** :
- `node/pyproject.toml`
- `node/bridge/sqlite_reader.py` :
  - `connect_readonly(path: str) -> sqlite3.Connection` (`mode=ro`, `uri=True`)
  - `fetch_detections_since(conn, since_id: int, limit: int = 200) -> list[DetectionRow]` — requête
    exacte donnée dans `architecture.md` §3.1 (JOIN `labels`, LEFT JOIN `audio_sources`)
  - `fetch_predictions(conn, detection_ids: list[int]) -> dict[int, list[PredictionRow]]` — JOIN
    `detection_predictions`/`labels`, **`ORDER BY confidence DESC`**, jamais `ORDER BY rank`
  - Dataclasses `DetectionRow`, `PredictionRow`
- `node/bridge/__main__.py` — CLI de test : `python -m bridge --db <path> --since-id 0` imprime le
  JSON des détections trouvées (outil de vérification manuelle, pas encore de réseau)
- `node/tests/test_sqlite_reader.py` — utilise une base SQLite de test **construite en mémoire**
  avec un schéma minimal reproduisant `detections`/`labels`/`detection_predictions`/`audio_sources`
  (ne touche jamais à `local-test/`)

**Dépendances** : aucune (indépendant de WP-01).
**Taille** : M.
**Démonstration** : `python -m bridge --db ../local-test/data/birdnet.db --since-id 0 --limit 5`
affiche 5 vraies détections de Pornic (espèce, confiance, prédictions triées), **sans avoir touché
au fichier** (vérifiable par `stat` avant/après : `mtime` inchangé).
**Tests attendus** : `pytest node/tests/test_sqlite_reader.py` vert, y compris un cas avec des
prédictions à `rank=1` partout (reproduit le comportement réel de la base) pour vérifier que le tri
se fait bien sur `confidence`.

---

### WP-03 — Sync bout-en-bout (premier résultat vivant)

**Objectif** : le bridge pousse réellement les détections de Pornic vers le serveur, de façon
idempotente. C'est le premier lot où l'on peut interroger la base serveur et voir des vraies données.

**Contenu** :
- `server/app/models/node.py` — `Node(id, site_id, name, bridge_shared_secret_hash, ...)` (schéma
  complet de `architecture.md` §4, mais pour ce lot un seul enregistrement suffit)
- `server/app/models/site.py` — `Site(id, name, slug, timezone, lat, lon)`
- `server/app/models/detection.py` — `Detection`, `Prediction` (DDL §4)
- `server/app/models/sync_state.py` — `NodeSyncState(node_id, last_synced_detection_id, last_sync_at)`
- Migration Alembic correspondante
- `server/app/schemas/sync.py` — schémas Pydantic du corps/réponse de `POST /sync` (format exact
  §5.2 de `architecture.md`)
- `server/app/api/ingest.py` — route `POST /api/v1/nodes/{node_id}/sync` :
  - vérifie `Authorization: Bearer` contre `bridge_shared_secret_hash` (comparaison en temps
    constant)
  - insère les détections avec `INSERT ... ON CONFLICT (node_id, node_local_id) DO NOTHING`
    (idempotence), insère les prédictions liées
  - met à jour `node_sync_state.last_synced_detection_id` au **max** des `node_local_id` acceptés
  - répond `{"accepted": N, "duplicates": M, "synced_up_to_id": ..., "commands": []}`
    (`commands` vide pour ce lot, sera peuplé en WP-11)
- `node/bridge/pusher.py` :
  - boucle : lit le curseur local (fichier `node/state/cursor.json`, **jamais** faisant foi seul —
    voir la note ci-dessous), appelle `fetch_detections_since`, construit le payload JSON, `POST`
    vers `/api/v1/nodes/{node_id}/sync`, **adopte `synced_up_to_id` de la réponse comme nouveau
    curseur** (même s'il diffère du fichier local), retry avec backoff exponentiel (base 5 s, max
    5 min, jitter ±25 %) sur toute erreur réseau/5xx
  - cadence configurable, défaut 20 s
- `node/bridge/main.py` — point d'entrée qui lance la boucle de `pusher.py`
- `server/tests/test_ingest.py` : idempotence (deux fois le même payload → `accepted` la 1ʳᵉ fois,
  `duplicates` la 2ᵉ, pas de doublon en base), rejet si Bearer invalide (401), curseur bien mis à
  jour
- `node/tests/test_pusher.py` : simulateur de serveur (via `respx`/`httpx` mock) vérifiant le retry
  et l'adoption du curseur serveur

**Dépendances** : WP-01, WP-02.
**Taille** : M.
**Démonstration** : lancer le serveur (WP-01) puis le bridge pointé sur
`local-test/data/birdnet.db`, laisser tourner 1 minute, puis :
```
sqlite3 server/data/bird-frame.db "SELECT COUNT(*), COUNT(DISTINCT scientific_name) FROM detections;"
```
affiche des chiffres cohérents avec `local-test` (des milliers de détections, ~56+ espèces) —
**sans que `local-test/data/birdnet.db` ait été modifié** (vérifier `mtime`/somme de contrôle avant/
après sur ce fichier précis, pas sur le WAL qui bouge normalement à cause du binaire lui-même).
**Tests attendus** : `pytest server/tests/test_ingest.py node/tests/test_pusher.py` verts.

---

### WP-04 — Frontend skeleton + tableau des dernières détections (visible en navigateur)

**Objectif** : première chose que Armand peut ouvrir dans un navigateur.

**Contenu** :
- `web/package.json` (Vite, Svelte 5, TypeScript strict, Tailwind v4 + `@tailwindcss/vite`, vitest)
- `web/vite.config.ts`, `web/tsconfig.json` (`"strict": true`)
- `web/index.html`, `web/src/main.ts`, `web/src/App.svelte` (squelette, pas encore de routeur réel)
- `web/src/styles/tailwind.css` — **copié** depuis
  `birdnet-go-ui/frontend/src/styles/tailwind.css` (bloc `@theme` uniquement, nettoyé des classes
  spécifiques BirdNET-Go non utilisées), en-tête de licence (§0.3 `architecture.md`)
- `web/src/styles/schemes.css` — **copié** depuis `birdnet-go-ui/frontend/src/styles/schemes.css`
- `web/NOTICE.md` — créé, première entrée pour ces deux fichiers
- `server/app/api/detections_debug.py` — route temporaire
  `GET /api/v1/sites/{site}/recent-detections?limit=50` (liste brute triée par date desc — **sera
  remplacée** par `GET /sites/{site}/now` en WP-06, gardée jusque-là pour avoir un signal visible
  tôt)
- `web/src/lib/api/client.ts` — petit client `fetch` typé vers le serveur
- `web/src/routes/RecentDetectionsPage.svelte` — tableau simple (espèce, confiance, heure)
- `web/tests/RecentDetectionsPage.test.ts` (rendu avec des données mockées)

**Dépendances** : WP-03.
**Taille** : M.
**Démonstration** : `npm run dev` dans `web/`, ouvrir `http://localhost:5173`, voir un tableau des
dernières détections réelles de Pornic (peuplé via le serveur, lui-même peuplé par le bridge).
**Tests attendus** : `npm run test` (vitest) vert dans `web/`.

---

## Vague 2 — Fonctionnalités cœur (toujours sans matériel supplémentaire)

### WP-05 — Calendrier d'activité quotidienne, sans limite d'espèces

**Objectif** : le bloc « Activité quotidienne » demandé par Armand — calculé **directement sur les
détections déjà ingérées côté serveur** (pas de proxy vers le nœud nécessaire pour cette vue : plus
robuste, et la donnée est déjà là).

**Contenu** :
- `server/app/api/calendar.py` — route `GET /api/v1/sites/{site}/calendar?date=` : requête SQL
  `GROUP BY scientific_name` sur `detections` du jour demandé (toutes les espèces, aucune troncature
  — pas de paramètre `limit` côté cette route, contrairement à `summaryLimit` côté BirdNET-Go qui,
  lui, plafonnait par défaut à 30), avec compte horaire (24 buckets) par espèce
- `server/tests/test_calendar.py`
- `web/src/lib/components/DailyActivityCalendar.svelte` — reprend l'esprit de `SeasonalHeatmap`/
  `DailySummaryCard` de BirdNET-Go (grille espèce × heure) mais **composant neuf** (les données ne
  viennent plus du même contrat JSON) ; **pas** de copie du fichier Svelte d'origine ici (payload trop
  différent), seule l'idée visuelle est reprise
- `web/src/routes/DashboardPage.svelte` — remplace `RecentDetectionsPage` comme page d'accueil,
  intègre `DailyActivityCalendar`
- `web/tests/DailyActivityCalendar.test.ts`

**Dépendances** : WP-03, WP-04.
**Taille** : M.
**Démonstration** : le dashboard affiche toutes les espèces détectées le jour courant (pas seulement
les 30 premières), avec répartition horaire.
**Tests attendus** : test serveur avec >30 espèces synthétiques dans une journée → toutes renvoyées.

---

### WP-06 — Bloc « En écoute » quasi temps réel

**Objectif** : le bloc « en écoute », première chose visible en haut du dashboard, alimenté par un
relais SSE quasi temps réel — pas par polling.

**Contenu** :
- `node/bridge/pending_relay.py` — se connecte en local à `GET http://localhost:8080/api/v2/
  detections/stream` (SSE public du nœud), filtre l'événement `event: pending`, `POST` immédiat
  (fire-and-forget, retry best-effort sans bloquer le flux) vers
  `/api/v1/nodes/{node_id}/pending`
- `server/app/api/pending.py` :
  - `POST /api/v1/nodes/{node_id}/pending` — stocke le dernier état en mémoire (ou table
    `node_status`-like légère), diffuse aussi aux abonnés SSE navigateur du site concerné
  - `GET /api/v1/sites/{site}/now` — snapshot du dernier `pending` connu
  - `GET /api/v1/sites/{site}/pending/stream` — SSE navigateur (relais simple, `event: pending`)
- `web/src/lib/components/CurrentlyHearingBlock.svelte` — s'abonne au SSE serveur, affiche espèce en
  cours + statut ; contient un `CollapsibleSection` (voir WP-19 pour le vrai spectrogramme live —
  ici, replié et affichant « spectrogramme live : indisponible pour l'instant » tant que WP-19 n'est
  pas fait)
- `web/src/lib/components/ui/CollapsibleSection.svelte` — **copié/adapté** depuis
  `birdnet-go-ui/frontend/src/lib/desktop/components/ui/CollapsibleSection.svelte`, entrée ajoutée à
  `NOTICE.md`
- Réordonnancement de `DashboardPage.svelte` : `CurrentlyHearingBlock` **en premier**, puis
  `DailyActivityCalendar` — **le bloc « détections récentes » n'existe nulle part dans le code neuf**
  (pas de composant équivalent créé, contrairement à un simple `enabled:false` qui laisserait du code
  mort)
- `node/tests/test_pending_relay.py`, `server/tests/test_pending.py`,
  `web/tests/CurrentlyHearingBlock.test.ts`

**Dépendances** : WP-03 (bridge en place), WP-04 (frontend en place).
**Taille** : M.
**Démonstration** : parler devant le micro du Mac → le bloc « en écoute » du dashboard change en
quelques secondes (pas 20-30 s comme le cycle de sync des détections confirmées).
**Tests attendus** : tests ci-dessus verts ; test manuel de latence noté dans le lot (pas
automatisable simplement).

---

### WP-07 — Modèle sites/nodes formalisé + script d'enregistrement

**Objectif** : remplacer le nœud unique codé en dur des lots précédents par le vrai modèle
d'enregistrement (nécessaire avant le multi-site, mais fait tôt pour ne pas retoucher WP-03/06 plus
tard).

**Contenu** :
- `server/app/api/admin.py` — route protégée (réservée à Armand, pas au bridge) `POST
  /api/v1/nodes/register` : crée `Site` si besoin (par `slug`), crée `Node`, génère
  `bridge_shared_secret` (32+ octets aléatoires), le hash et le stocke, **renvoie le secret en clair
  une seule fois** (jamais relisible ensuite)
- `scripts/register_node.py` — CLI qui appelle cette route et écrit le résultat
  (`node_id` + secret) dans `node/config/<slug>.env` (permissions 600)
- Migration : ajout des colonnes manquantes sur `nodes`/`sites` si WP-03 avait simplifié le schéma
- `node/bridge/config.py` — lit `node/config/<slug>.env` au lieu de valeurs codées en dur
- `server/tests/test_admin.py`

**Dépendances** : WP-03.
**Taille** : S.
**Démonstration** : `python scripts/register_node.py --slug pornic --name "Mac Armand — Pornic"`
crée le site + le nœud, le bridge redémarré avec le nouveau fichier de config continue de pousser
sans interruption de service perceptible (curseur conservé côté serveur via `node_id`).
**Tests attendus** : `pytest server/tests/test_admin.py`.

---

### WP-08 — Top-5 clips par site et par espèce

**Objectif** : rapatrier et conserver exactement 5 enregistrements par `(site, espèce)`, triés par
confiance, avec purge des évincés.

**Contenu** :
- `server/app/models/kept_clip.py` — `KeptClip` (DDL §4)
- `server/app/ingest/top5.py` :
  - fonction appelée à la fin de `POST /sync` (WP-03) pour chaque détection avec `has_clip=true` :
    compare à la 5ᵉ meilleure confiance connue pour `(site_id, scientific_name)`
  - si elle entre dans le top-5 : `GET http://<node_host>/api/v2/audio/:id` et
    `GET http://<node_host>/api/v2/spectrogram/:id?size=lg` (méthodes sûres, **aucun cycle CSRF
    nécessaire** — vérifié : ces routes passent par `PrivateModeAuth`, pas `AuthMiddleware`, et le
    skipper CSRF exempte les préfixes `/api/v2/audio/`/`/api/v2/spectrogram/` en GET), écrit les
    fichiers sous `server/data/clips/<site>/<espèce>/`, marque `fetched_at`
  - évince et supprime le fichier physique du 5ᵉ précédent le cas échéant (jamais la ligne
    `detections`)
  - `node_host` pour ce lot = `http://localhost:8080` (S1, avant Tailscale) ; le champ est déjà
    paramétrable par nœud (`nodes.api_base_url`, posé en WP-07) pour ne pas avoir à retoucher ce code
    en WP-18
- `server/app/api/recordings.py` — `GET /api/v1/recordings/{kept_clip_id}/audio`,
  `.../spectrogram` (sert les fichiers stockés)
- `server/tests/test_top5.py` — simule 7 détections d'une même espèce avec confiances différentes,
  vérifie qu'il n'en reste que 5, la meilleure en tête, les fichiers évincés supprimés du disque

**Dépendances** : WP-03, WP-07.
**Taille** : M.
**Démonstration** : après quelques minutes de fonctionnement, `ls server/data/clips/pornic/
erithacus_rubecula/` contient au plus 5 fichiers `.wav` + 5 `.png`, cohérents avec les 5 meilleures
confidences visibles dans `SELECT * FROM kept_clips WHERE scientific_name='Erithacus rubecula'`.
**Tests attendus** : `pytest server/tests/test_top5.py`.

---

### WP-09 — Fiche espèce : route dédiée + enregistrements + labels multi-espèces

**Objectif** : la fiche espèce demandée par Armand, sans le contenu trivia (WP-10) pour l'instant —
photo (provisoire, WP-10 l'améliore), présence, 5 enregistrements jouables avec spectrogramme et
labels.

**Contenu** :
- `server/app/api/species.py` :
  - `GET /api/v1/species` — liste (pour ce lot : uniquement les espèces réellement détectées,
    l'univers des 368 arrive en WP-10)
  - `GET /api/v1/species/{scientific_name}` — fiche minimale (nom, présence par site)
  - `GET /api/v1/species/{scientific_name}/sites/{site}/top-clips` — les `KeptClip` du couple,
    chacun avec `audio_url`, `spectrogram_url` (routes WP-08), et ses `predictions` (déjà en base
    depuis WP-03, triées `confidence DESC`)
  - `GET /api/v1/species/{scientific_name}/presence?site=` — agrégation `detections` par mois/site
- `web/src/routes/SpeciesPage.svelte` — liste des espèces du site sélectionné
- `web/src/routes/SpeciesDetailPage.svelte` — **route dédiée `/species/:id`**, deep-linkable (pas une
  modale) : photo (provisoire), stats, `RecordingList`
- `web/src/lib/components/RecordingList.svelte` — neuf : 5 lecteurs audio + spectrogramme (image
  statique servie par WP-08 — le lecteur audio HTML natif suffit, pas besoin de `SpectrogramPlayer`
  complexe du fork pour un fichier déjà généré)
- `web/src/lib/components/MultiSpeciesLabels.svelte` — chips « Rouge-gorge 100 %, Pie bavarde 20 % »
- `web/src/lib/router.ts` — introduit le vrai routeur maison (History API), remplace le switch minimal
  de WP-04
- Tests : `server/tests/test_species.py`, `web/tests/SpeciesDetailPage.test.ts`

**Dépendances** : WP-05 (routeur pas encore critique mais cohérent), WP-08.
**Taille** : M/L.
**Démonstration** : cliquer sur une espèce depuis la liste, ou coller directement l'URL
`http://localhost:5173/species/Erithacus%20rubecula` dans un nouvel onglet → la fiche s'affiche
directement (deep-link fonctionnel), avec jusqu'à 5 enregistrements jouables et leurs labels.
**Tests attendus** : ceux listés ci-dessus verts.

---

### WP-10 — Pipeline fiches espèces (368, agents Haiku)

**Objectif** : remplir `species_sheets` pour les 368 espèces de `species_universe_fr.json`, plus la
taxonomie/nom FR récupérés une fois depuis le nœud.

**Contenu** :
- `species-data/species_universe_fr.json` — copié depuis le scratchpad de recherche vers cet
  emplacement canonique du dépôt
- `server/app/models/species_sheet.py` — `SpeciesSheet` (DDL §4)
- `server/app/species_sheets/taxonomy_fetch.py` — appelle une fois, pour chaque espèce,
  `GET http://localhost:8080/api/v2/species/taxonomy?scientific_name=&locale=fr` et
  `GET /api/v2/species/dictionary/fr` (téléchargé une seule fois, mis en cache local) ; **aucune
  copie de fichier du dépôt Go**
- `server/app/species_sheets/wikipedia_fetch.py` — `GET https://fr.wikipedia.org/api/rest_v1/page/
  summary/<Nom_scientifique>`, extrait + `originalimage`
- `server/app/species_sheets/haiku_agent.py` — construit le prompt (extrait Wikipédia + entrée
  `species_universe_fr.json` de l'espèce, **présentée comme fait établi, jamais comme supposition**),
  appelle l'API Claude (modèle Haiku), parse la sortie JSON contrainte au schéma §9 de
  `architecture.md`
- `server/app/species_sheets/validate.py` — vérifie champs non vides, `wikipedia_url` en `HEAD`
  200, cohérence basique `rarity_note`/`france_universe.max_score`
- `server/app/species_sheets/pipeline.py` — orchestre les 368 espèces (parallélisme raisonnable,
  ex. 5-10 en simultané), écrit en base avec `reviewed_by_human=false`
- `server/app/api/species_sheets.py` — `POST /api/v1/species/{name}/sheet/regenerate`
- `server/tests/test_species_sheets_pipeline.py` (avec des réponses Wikipédia/Haiku mockées)

**Dépendances** : WP-07 (accès au nœud pour la taxonomie), WP-09 (la fiche a un endroit où afficher
le résultat).
**Taille** : L.
**Démonstration** : `python -m server.app.species_sheets.pipeline --limit 5` remplit 5 fiches
réelles (ex. Merle noir, Rouge-gorge, Pigeon ramier, Corneille noire, Mésange charbonnière),
visibles complètes sur `/species/:id` (taxonomie, photo HD, brief structuré hiverne/niche/passage).
Lancer sur les 368 ensuite (peut tourner en tâche de fond, pas bloquant pour la démo).
**Tests attendus** : `pytest server/tests/test_species_sheets_pipeline.py`.

---

## Vague 3 — Système et pilotage (toujours sur le nœud local, pas de matériel supplémentaire)

### WP-11 — Client CSRF du bridge + file de commandes

**Objectif** : la brique commune qui permettra tout pilotage à distance des réglages (WP-12 à WP-14,
et plus tard WP-19 pour le live) — écrite une fois, testée, jamais reconstruite ad hoc.

**Contenu** :
- `node/bridge/csrf_client.py` :
  - `get_csrf_token(base_url) -> (cookie_jar, token)` — `GET /api/v2/app/config`
  - `authenticated_request(method, path, json=None, bearer=None)` — pose le cookie + header
    `X-CSRF-Token`, retry une fois sur 403 en rafraîchissant le token (même logique que le client
    JS de BirdNET-Go)
- `node/bridge/commands.py` :
  - boucle de poll `GET /api/v1/nodes/{node_id}/commands` (cadence rapide par défaut 5 s, repli à
    30 s si aucune commande depuis longtemps — implémentation simple : cadence adaptative avec
    compteur d'échecs consécutifs à vide)
  - dispatch par `kind` vers un handler (`set_species_threshold`, `exclude_species`,
    `include_species`, `reset_dynamic_threshold` pour ce lot ; `start_live`/`live_heartbeat` seront
    branchés en WP-19)
  - `POST /api/v1/nodes/{node_id}/commands/{cmd_id}/ack` après exécution (`applied` ou `failed` +
    `error_message`)
- `server/app/models/node_command.py` — `NodeCommand` (DDL §4)
- `server/app/api/commands.py` — `GET /nodes/{id}/commands`, `POST /nodes/{id}/commands/{id}/ack`
- `server/app/commands/queue.py` — helper `enqueue_command(node_id, kind, payload)` réutilisé par
  WP-12/13/14
- `node/tests/test_csrf_client.py` (contre un faux serveur HTTP local simulant le cycle CSRF de
  BirdNET-Go), `node/tests/test_commands.py`, `server/tests/test_commands_api.py`

**Dépendances** : WP-07.
**Taille** : M.
**Démonstration** : un script manuel `python scripts/enqueue_test_command.py --kind
exclude_species --scientific-name "Columba livia"` crée une commande ; dans les secondes qui
suivent, le bridge l'applique (vérifiable par `GET http://localhost:8080/api/v2/detections/ignored`
qui liste bien l'espèce), et le statut passe à `applied` côté serveur.
**Tests attendus** : ceux listés ci-dessus verts.

---

### WP-12 — Règles par espèce et par site

**Objectif** : « présente ici → seuil bas », « impossible ici → non », « rediriger vers telle
espèce ».

**Contenu** :
- `server/app/models/species_site_rule.py` — `SpeciesSiteRule` (DDL §4)
- `server/app/api/species_rules.py` — `GET`/`PUT /api/v1/sites/{site}/species-rules/
  {scientific_name}` :
  - `rule='present'` → `enqueue_command('set_species_threshold', {scientific_name, threshold})`
  - `rule='impossible'` → `enqueue_command('exclude_species', {scientific_name})`
  - `rule='redirect'` → **aucune commande nœud** (aucun mécanisme natif) : seulement mis à jour côté
    serveur, déclenche le recalcul de `detections.redirected_to_scientific_name` pour les détections
    existantes et futures de cette espèce sur ce site (job simple, synchrone pour ce volume)
- `web/src/routes/SpeciesRulesPage.svelte` — formulaire par espèce (radio présente/impossible/
  redirection + seuil/cible), affiche le statut de la dernière `node_command` associée
  (`pending`/`applied`/`failed`, jamais un simple horodatage nullable)
- `server/tests/test_species_rules.py`

**Dépendances** : WP-11.
**Taille** : M.
**Démonstration** : marquer « Pigeon biset — impossible ici » depuis l'UI → quelques secondes après,
`GET /api/v2/detections/ignored` sur le nœud local liste bien l'espèce, et la page règles affiche
`applied`.
**Tests attendus** : `pytest server/tests/test_species_rules.py`.

---

### WP-13 — Reclassement faux positif / faux négatif

**Objectif** : les deux flux demandés par Armand — l'un existe déjà côté BirdNET-Go (à rejouer
proprement), l'autre est entièrement neuf.

**Contenu** :
- `server/app/models/review.py`, `server/app/models/false_negative_report.py` (DDL §4)
- `server/app/api/reviews.py` :
  - `POST /api/v1/sites/{site}/reviews` — écrit `Review` **et** enqueue une commande
    `mark_detection_reviewed` (nouveau `kind` à ajouter à l'énumération de `node_commands` si non
    prévu) qui, côté bridge, appelle `POST /detections/:id/review` du nœud (jamais d'écriture directe
    dans `detection_reviews` — cf. `architecture.md` §7.5, pour ne pas contourner
    `invalidateDetectionCache()`)
  - `POST /api/v1/false-negatives` — écrit `FalseNegativeReport`, **aucune commande nœud** (rien à
    répercuter, par construction)
- `node/bridge/commands.py` — ajoute le handler `mark_detection_reviewed` (POST CSRF vers
  `/detections/:id/review` avec `{"verified": "correct"|"false_positive"}`)
- `web/src/lib/components/ActionMenuAdapter.svelte` — **s'inspire directement** de `ActionMenu.svelte`
  de BirdNET-Go (déjà câblé avec `onMarkCorrect`/`onMarkFalsePositive` dans le fork) comme référence
  d'implémentation UX (pas une copie mécanique : le composant d'origine est couplé aux stores
  BirdNET-Go, on en reprend le motif d'interaction, pas le fichier)
- `web/src/routes/FalseNegativeFormPage.svelte`
- `server/tests/test_reviews.py`

**Dépendances** : WP-11.
**Taille** : S/M.
**Démonstration** : marquer une détection comme faux positif depuis l'UI → visible comme
`false_positive` à la fois côté serveur et, après application de la commande, sur l'UI native du nœud
(`http://localhost:8080`) pour la même détection.
**Tests attendus** : `pytest server/tests/test_reviews.py`.

---

### WP-14 — Transparence des seuils dynamiques

**Objectif** : comprendre le mécanisme qui abaisse automatiquement le seuil d'une espèce.

**Contenu** :
- `server/app/api/dynamic_thresholds.py` :
  - `GET /api/v1/sites/{site}/dynamic-thresholds` — miroir lecture seule, alimenté par le champ
    `dynamic_thresholds_snapshot_json` de `node_status`, lui-même mis à jour par le heartbeat du
    bridge (`node/bridge/heartbeat.py`, à créer si pas déjà fait — interroge localement
    `GET /dynamic-thresholds` et `/stats` du nœud, envoie le résumé dans `POST .../heartbeat`)
  - `GET .../dynamic-thresholds/{species}/events` — idem, proxy direct du nœud (lecture, pas besoin
    de passer par le bridge : GET public)
  - `DELETE .../dynamic-thresholds/{species}` — enqueue une commande `reset_dynamic_threshold`
    (mutation, doit passer par le bridge)
- `node/bridge/heartbeat.py` — boucle périodique (60 s), `POST /api/v1/nodes/{id}/heartbeat`
  (format §5.2), lit micro/disque via des commandes système simples + l'état seuils dynamiques
- `web/src/routes/SystemStatusPage.svelte` — statut micro/disque + table des seuils dynamiques avec
  bouton reset
- `server/tests/test_dynamic_thresholds.py`, `node/tests/test_heartbeat.py`

**Dépendances** : WP-11.
**Taille** : M.
**Démonstration** : la page système affiche les seuils dynamiques réels de Pornic (niveaux 0-3,
historique d'événements), le bouton « réinitialiser » fonctionne (vérifiable par
`GET /dynamic-thresholds/:species` sur le nœud avant/après).
**Tests attendus** : ceux listés.

---

### WP-15 — Statistiques long terme (proxy)

**Objectif** : reprendre les graphes que BirdNET-Go fait déjà bien (décision §9bis-a de
`architecture.md` : proxy pour le MVP, shadow BirdNET-Go plus tard en WP-21).

**Contenu** :
- `server/app/api/stats.py` — `GET /api/v1/sites/{site}/stats/{kind}` où `kind` ∈
  `kpis|daily|heatmap|ridgeline|phenology|confidence|insights`, chacun proxie directement
  (méthode GET, pas de CSRF nécessaire) l'endpoint natif correspondant du nœud (`dashboard/kpis`,
  `analytics/time/daily`, `analytics/time/heatmap`, `analytics/time/distribution/species`,
  `analytics/species/phenology`, `analytics/confidence/distribution`, `insights/*`) ; timeout court
  (5 s), erreur propre si le nœud est injoignable (pas de blocage de page)
- `web/src/lib/charts/` — infra D3 **copiée/adaptée** depuis `birdnet-go-ui/frontend/src/lib/desktop/
  features/analytics/components/{BaseChart.svelte, utils/*.ts}` (entrées `NOTICE.md`)
- `web/src/routes/StatsPage.svelte` + un composant par famille de graphe
- `server/tests/test_stats_proxy.py` (mock du nœud, cas nœud injoignable)

**Dépendances** : WP-07.
**Taille** : M/L.
**Démonstration** : la page stats affiche les mêmes familles de graphes que le dashboard BirdNET-Go
natif (heatmap saisonnier, tendance quotidienne, phénologie, distribution de confiance), sur les
données réelles de Pornic.
**Tests attendus** : `pytest server/tests/test_stats_proxy.py`.

---

### WP-16 — Licence : NOTICE.md + en-têtes + test de conformité

**Objectif** : rendre vérifiable, pas seulement documentée, la conformité CC BY-NC-SA 4.0.

**Contenu** :
- `web/tests/notice.test.ts` — lit `web/NOTICE.md`, pour chaque fichier listé vérifie (a) qu'il
  existe, (b) qu'il porte l'en-tête de licence attendu (regex simple sur les 5 premières lignes)
- Passe en revue tous les fichiers copiés dans les lots précédents (WP-04, WP-06, WP-15) et complète
  les en-têtes manquants

**Dépendances** : WP-04, WP-06, WP-15 (ou peut être fait en continu, mais formalisé ici).
**Taille** : S.
**Démonstration** : `npm run test -- notice.test.ts` vert, `NOTICE.md` à jour.
**Tests attendus** : le test lui-même est le livrable.

---

## Vague 4 — Multi-site réel (nécessite un Pi 5 + Tailscale)

### WP-17 — Migration historique (Le Mans + Pornic)

**Contenu** : `scripts/migrate_legacy_site.py` — réutilise `server/app/ingest/` en mode « backfill »
(`since_id=0`), deux modes : (a) Pornic, lecture directe de `local-test/data/birdnet.db` pendant que
le binaire tourne (sûr, WAL) ; (b) Le Mans, base arrêtée dans `local-test/sauvegardes/
lieu-1_le-mans_.../`, lecture directe des fichiers `.wav`/`.png` archivés pour peupler `kept_clips`
(pas d'appel HTTP possible, binaire arrêté pour cette base).

**Dépendances** : WP-08, WP-09.
**Taille** : M.
**Démonstration** : `python scripts/migrate_legacy_site.py --slug le-mans --source local-test/
sauvegardes/lieu-1_le-mans_2026-09-21_au_2026-09-23` peuple le site « Le Mans » avec ses 878
détections et ses vrais clips.
**Tests attendus** : `pytest scripts/tests/test_migrate_legacy_site.py` (sur un dossier de test
minimal, pas sur les vraies sauvegardes).

---

### WP-18 — Tailscale + premier nœud distant

**Contenu** : documentation d'installation (`node/README-pi.md`) : image Raspberry Pi OS, binaire
BirdNET-Go linux-arm64 officiel (même tag ou proche), scripts `start.sh`/`stop.sh` adaptés (sans le
contournement CoreAudio, avec la supervision micro générique de WP-14/`architecture.md` §13),
bridge en service `systemd` (`node/deploy/bridge.service`), Tailscale (`tailscale up`), exécution de
`scripts/register_node.py` à distance.

**Dépendances** : WP-11 à WP-15 (le nœud local doit déjà tout savoir faire avant de le répliquer).
**Taille** : L (dépend surtout de la logistique matérielle, pas du code).
**Démonstration** : un Pi 5 sur le réseau d'un proche (ou simulé en local avec un néttoyage de
`main.name`) apparaît dans `GET /api/v1/nodes`, pousse ses détections, répond aux commandes.
**Tests attendus** : tests d'intégration déjà couverts par les lots précédents ; validation manuelle
sur le vrai Pi.

---

### WP-19 — Audio et spectrogramme live à distance

**Objectif** : le canal live complet, tel que décrit en `architecture.md` §6 (mutant → bridge local,
lecture → proxy direct serveur).

**Contenu** :
- `node/bridge/live.py` — handlers `start_live`/`live_heartbeat`/`stop_live` dans
  `node/bridge/commands.py` : `start_live` exécute `POST /streams/hls/:sourceID/start` via
  `csrf_client.py`, renvoie `{stream_token, playlist_url}` dans l'ack ; `live_heartbeat` est
  reprogrammé automatiquement par le bridge toutes les ~20 s tant qu'une session est active (pas
  besoin d'une nouvelle commande serveur à chaque fois)
- `server/app/live/proxy.py` — `GET /api/v1/sites/{site}/live/hls/*` : relaie directement (pas de
  CSRF, méthode sûre) vers `http://<tailscale_hostname>:8080/api/v2/streams/hls/t/:token/...` ;
  timeout court, erreur propre si injoignable
- `server/app/api/live.py` — `POST /api/v1/sites/{site}/live/start` (enqueue `start_live`, attend
  l'ack avec un timeout raisonnable, ~10 s, avant de répondre au navigateur), `GET .../live/
  audio-level` (SSE, même principe de proxy direct)
- `web/src/lib/components/LiveSpectrogram.svelte` — **remplace** le placeholder de WP-06 dans
  `CollapsibleSection` ; réutilise le pipeline HLS + Web Audio API de `MiniSpectrogram.svelte`
  comme référence d'implémentation (câblage `hls.js` + `AnalyserNode`), pointé sur les URLs proxiées
  serveur
- `server/tests/test_live_proxy.py` (mock du nœud), `node/tests/test_live_commands.py`

**Dépendances** : WP-11, WP-18 (pour un vrai test à distance ; fonctionne aussi en local sur le Mac
avant Tailscale, en pointant `nodes.api_base_url` sur `localhost`).
**Taille** : L.
**Démonstration** : ouvrir l'accordéon spectrogramme du bloc « en écoute » → audio live du site
sélectionné après quelques secondes de latence (4-8 s, cohérent avec HLS), spectrogramme animé.
Débrancher Tailscale (ou couper le nœud) → le reste du dashboard continue de fonctionner, seul ce
bloc affiche « site hors ligne ».
**Tests attendus** : ceux listés.

---

## Vague 5 — Durcissement (nécessite un 2ᵉ site réel pour avoir du sens)

### WP-20 — Sécurité renforcée

**Contenu** : activer `security.privatemode: true` + Bearer token natif BirdNET-Go sur chaque nœud
Tailscale (généré à l'enregistrement WP-07, appliqué par une commande `enable_bearer_auth` exécutée
une fois par le bridge), rotation des secrets documentée, `node/bridge/csrf_client.py` et
`server/app/live/proxy.py` mis à jour pour présenter systématiquement `Authorization: Bearer` en plus
du cycle CSRF/cookie.

**Dépendances** : WP-18, WP-19.
**Taille** : S/M.
**Démonstration** : une requête directe vers `http://<tailscale_hostname>:8080/api/v2/detections`
sans Bearer échoue (401) depuis un autre appareil du tailnet ; le bridge et le proxy serveur
continuent de fonctionner normalement.

---

### WP-21 — Instance BirdNET-Go « shadow » pour les stats multi-sites

**Objectif** : remplacer le proxy live de WP-15 par une vue agrégée « toutes stations », sans
dépendre de la disponibilité d'un nœud particulier (décision §9bis-b de `architecture.md`).

**Contenu** :
- `server/docker/shadow-birdnet/docker-compose.yml` — MySQL dédié + binaire BirdNET-Go headless
  (`Realtime.Audio.Sources: []`, `output.mysql` pointé sur ce MySQL, `webserver.enabled: true`, port
  dédié)
- `server/app/shadow_birdnet/replay.py` — job périodique : pour chaque détection ingérée avec succès
  dans le SQLite serveur (jamais sur l'écriture temps réel des nœuds), rejoue l'insertion dans le
  schéma natif BirdNET-Go (`labels`/`audio_sources`/`ai_models`/`detections`/`detection_predictions`)
  via le motif find-then-create transactionnel documenté (créer/résoudre chaque table de référence
  puis `INSERT` détection + prédictions dans la même transaction) — `audio_sources.node_name` assigné
  ici = **le slug du site côté serveur**, jamais `main.name` du nœud d'origine (garanti unique par
  construction, contrairement à l'amont)
- `server/app/api/stats.py` — bascule progressive : `kind` interroge la shadow instance si elle a des
  données pour ce site, sinon repli sur le proxy live de WP-15
- `server/tests/test_shadow_replay.py`

**Dépendances** : WP-15, WP-18 (a du sens surtout à partir de 2 sites).
**Taille** : L.
**Démonstration** : couper le nœud d'un site (débrancher/éteindre) → sa page stats continue de
répondre (servie par la shadow instance), alors que sa page « en écoute »/live affiche « hors
ligne ».

---

### WP-22 — Sauvegardes, restauration, onboarding d'un nœud chez un proche

**Contenu** : `scripts/backup_server.sh` (copie SQLite + `rsync`/`restic` des clips vers un stockage
hors site), `docs/runbook-onboarding-noeud.md` (checklist : `main.name`, Tailscale, secret, premier
`heartbeat` reçu, premier `sync` reçu), test de restauration effectivement exécuté (pas seulement
documenté) avant le premier déploiement chez un proche non technique.

**Dépendances** : WP-18, WP-20, WP-21.
**Taille** : M.
**Démonstration** : restauration d'une sauvegarde sur une machine propre, le serveur restauré
redemande correctement l'historique manquant aux nœuds actifs (idempotence `UNIQUE(node_id,
node_local_id)` vérifiée en conditions réelles, pas seulement en test unitaire).

---

## Résumé des dépendances (vue graphe simplifiée)

```
WP-01 ─┬─▶ WP-03 ─┬─▶ WP-04 ─┬─▶ WP-05 ─▶ WP-06
WP-02 ─┘          │          └─▶ (routeur, WP-09)
                   ├─▶ WP-07 ─┬─▶ WP-08 ─▶ WP-09 ─▶ WP-10
                   │          ├─▶ WP-11 ─┬─▶ WP-12
                   │          │          ├─▶ WP-13
                   │          │          └─▶ WP-14
                   │          └─▶ WP-15 ─▶ WP-16
                   │
                   └─▶ WP-17 (backfill, peut attendre)

WP-11 + WP-18 ──▶ WP-19 ──▶ WP-20 ──▶ WP-22
WP-15 + WP-18 ──▶ WP-21 ──▶ WP-22
```
