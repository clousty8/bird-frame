# bird-frame — Architecture finale (synthèse)

Statut : architecture de référence, issue de la synthèse de trois conceptions concurrentes
(A « Capteur + serveur », B « BirdNET-Go au centre », C « Exploitation d'abord ») jugées par trois
juges indépendants (exigences, terrain, faisabilité). **Conception C a gagné les trois votes**
(exigences 42/50, terrain 38/50, faisabilité 39/50) et sert de socle. Ce document greffe les
meilleures idées de A et B sur C, corrige les erreurs factuelles relevées par les juges, et tranche
tous les points laissés ouverts. Il est conçu pour être exécuté par des sous-agents **sans avoir à
relire les rapports R0-R10** : tout ce qui compte pour implémenter est ici.

Contexte complet (exigences d'Armand, cartographie du code BirdNET-Go) : voir
`research/` et les rapports ayant servi à cette synthèse restent dans le scratchpad de la session —
ce document ne dépend plus d'eux pour être compris.

---

## 0. Arborescence du dépôt et conventions

### 0.1 Arborescence cible

```
bird-frame/
├── CLAUDE.md                      # inchangé
├── docs/                          # ce document + plan.md + futures notes
├── local-test/                    # INCHANGÉ, lecture seule pour tout le nouveau code
├── birdnet-go-ui/                 # INCHANGÉ, sert de référence (fork BirdNET-Go, licence CC BY-NC-SA 4.0)
├── research/                      # inchangé
├── species-data/
│   └── species_universe_fr.json   # copie canonique (368 espèces, scores ville×mois)
├── server/                        # FastAPI companion — "le serveur"
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py                  # SQLAlchemy engine/session
│   │   ├── models/                # modèles SQLAlchemy (un fichier par table ou par domaine)
│   │   ├── schemas/                # schémas Pydantic (requêtes/réponses)
│   │   ├── api/                    # routers FastAPI (sites, nodes, species, detections, ...)
│   │   ├── ingest/                 # logique de synchro nœud→serveur, idempotence, top-5
│   │   ├── commands/                # file node_commands, création/consommation
│   │   ├── live/                    # relais HLS/SSE (proxy direct + délégation bridge)
│   │   ├── species_sheets/          # pipeline agents Haiku (fiches espèces)
│   │   ├── shadow_birdnet/          # (WP tardif) rejeu vers instance BirdNET-Go headless
│   │   └── auth.py                  # login famille (session simple)
│   ├── migrations/                  # Alembic
│   ├── tests/                       # pytest
│   └── pyproject.toml
├── node/                            # le "bridge", déployé à côté de chaque BirdNET-Go
│   ├── bridge/
│   │   ├── main.py                   # boucle principale (sync + commandes + relais pending)
│   │   ├── sqlite_reader.py           # lecture birdnet.db en lecture seule
│   │   ├── pusher.py                  # POST vers /api/v1/nodes/{id}/sync
│   │   ├── commands.py                # poll + exécution locale (CSRF)
│   │   ├── csrf_client.py             # cycle cookie+X-CSRF-Token contre localhost:8080
│   │   ├── pending_relay.py           # abonnement SSE local → relais quasi temps réel
│   │   └── live.py                    # start/heartbeat HLS local sur demande serveur
│   ├── tests/                         # pytest
│   └── pyproject.toml
├── web/                               # Vite + Svelte 5 + Tailwind v4 — "le frontend"
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/            # génériques copiés/adaptés + neufs
│   │   │   ├── charts/                # infra D3 copiée (BaseChart, utils/*)
│   │   │   ├── stores/
│   │   │   └── api/                   # client HTTP vers le serveur (neuf, pas api.ts de BirdNET-Go)
│   │   ├── routes/                    # ou App.svelte + routeur maison (voir §8)
│   │   └── styles/                    # tailwind.css + schemes.css copiés
│   ├── static/messages/               # i18n fr.json/en.json (copie structurelle, contenu réécrit)
│   ├── NOTICE.md                      # attribution des fichiers copiés (voir §8.3)
│   ├── tests/                         # vitest
│   └── package.json
└── scripts/
    └── migrate_legacy_site.py         # backfill Le Mans / Pornic (voir §11)
```

### 0.2 Conventions

- **Python 3.13** partout (`server/`, `node/`, `scripts/`). FastAPI + SQLAlchemy 2.x (style déclaratif
  2.0) + Alembic pour les migrations. **SQLite d'abord** (fichier unique, `server/data/bird-frame.db`) :
  aucune dépendance à Postgres pour le MVP ; une bascule Postgres reste possible plus tard (SQLAlchemy
  rend le changement de moteur mécanique) si le volume l'exige un jour — pas nécessaire à l'échelle
  familiale visée. Le bridge n'a **aucune base propre** au-delà d'un petit état de reprise local
  (fichier JSON ou SQLite minuscule, jamais `birdnet.db`).
- **Tests** : `pytest` (+ `httpx.AsyncClient`/`TestClient` FastAPI) côté `server/` et `node/` ;
  `vitest` + `@testing-library/svelte` côté `web/`. Chaque lot de travail du plan liste les tests
  attendus.
- **Style** : `ruff` + `black` côté Python (config minimale, pas de bikeshedding) ; `eslint` +
  `prettier` + `svelte-check` côté frontend (repris tel quel du fork si simple à extraire, sinon
  config minimale neuve).
- **Frontend** : Svelte 5 (runes uniquement, pas de legacy slots), TypeScript **strict**
  (`"strict": true` dans `tsconfig.json`), Vite, Tailwind v4 natif (pas de bibliothèque de composants
  — même choix que BirdNET-Go, qui n'utilise pas DaisyUI). Pas de SvelteKit : SPA Vite pure, routeur
  maison (voir §8).
- **Aucune ligne de Go n'est jamais écrite ni recompilée.** Toute interaction avec BirdNET-Go passe
  par son API HTTP existante (`internal/api/v2/*`) ou par lecture directe de son fichier SQLite.
- **`local-test/` et `birdnet-go-ui/` ne sont jamais modifiés** par le nouveau code. Le bridge lit
  `local-test/data/birdnet.db` en mode `ro` uniquement pendant les WP de démarrage (S1) ; une fois un
  vrai nœud Pi déployé, le bridge de production pointe vers **sa propre** copie de `local-test/`
  (dossier de déploiement dédié au nœud), jamais vers le dossier de développement d'Armand.

### 0.3 Licence — code copié de BirdNET-Go

Tout fichier copié ou adapté depuis `birdnet-go-ui/frontend` (tokens CSS, composants Svelte,
i18n, utilitaires D3) reste sous **CC BY-NC-SA 4.0** (licence du projet amont BirdNET-Go). Deux
mécanismes concrets et vérifiables :
1. **`web/NOTICE.md`** — un tableau à jour : `fichier copié | fichier d'origine (chemin dans
   birdnet-go-ui) | nature de l'adaptation | licence`.
2. **En-tête de licence par fichier copié**, en tête de chaque fichier concerné :
   ```
   // Adapté de BirdNET-Go (birdnet-go-ui, fork bird-frame, tag 20260823).
   // Licence d'origine : CC BY-NC-SA 4.0. Voir web/NOTICE.md.
   // Modifications : <description courte>.
   ```
   Un test (`web/tests/notice.test.ts`, WP dédié) vérifie que tout fichier listé dans `NOTICE.md`
   existe bien et porte l'en-tête — évite la dérive silencieuse.

---

## 1. Vision en une page

```
S1 — aujourd'hui, sur le Mac d'Armand (cohabitation stricte avec local-test/)
┌───────────────────────────────────────────────────────────┐
│ local-test/  (INCHANGÉ, lecture seule)                     │
│   micro USB → BirdNET-Go natif → birdnet.db (SQLite, WAL)  │
│   → UI native :8080 (fork bird-frame actuel, inchangée)    │
└───────────────────────────────────────────────────────────┘
        │ lecture seule (sqlite3 mode=ro)     │ GET HTTP (audio/spectro/settings CSRF local)
        ▼                                      ▼
┌────────────────────────┐   POST outbound   ┌──────────────────────────┐
│ Bridge (Python, natif)  │ ─── HTTPS ───────▶│ Serveur FastAPI + SQLite │
│ :8091 (local uniquement)│ ◀── commandes ────│  (natif, même Mac : 8090)│
└────────────────────────┘                    └──────────────┬───────────┘
                                                               │ HTTP
                                                    ┌──────────▼──────────┐
                                                    │ Frontend Svelte 5    │
                                                    │ (Vite dev :5173)     │
                                                    └──────────────────────┘

S2 — un site distant (Pi 5 chez un proche, box sans IP fixe)
┌─ Domicile du proche (Pi 5) ──────────────┐        ┌─ Serveur (VPS ou machine chez Armand) ─┐
│ Micro → BirdNET-Go (binaire officiel      │        │ FastAPI + SQLite, joignable en HTTPS   │
│ linux-arm64, même tag) → birdnet.db local │        │ public (Caddy + Let's Encrypt)         │
│ + Bridge colocalisé, :8091 local          │        │                                         │
│   push sortant (HTTPS) ───────────────────┼───────▶│ ingestion (secret par nœud)             │
│   poll commandes sortant ─────────────────┼───────▶│ file node_commands                      │
│   (aucun port entrant requis)             │        │                                         │
│   Tailscale (mesh) pour : live audio HLS  │◀──────▶│ proxy live (GET direct via Tailscale)   │
│   + settings CSRF exécutés LOCALEMENT     │        │                                         │
└────────────────────────────────────────────┘        └──────────────────────────────────────────┘

S3 — plusieurs sites → un seul serveur (généralisation de S2)
 Le Mans(Pi5)   Rennes(Pi5)   Poitiers(Pi5)   Pornic(Pi5/Mac)
 BirdNET-Go + Bridge, chacun avec son secret propre, identité assignée par le serveur
        │              │              │               │
        └──────────────┴──── push sortant HTTPS ───────┘
                               │
                    ┌──────────▼───────────┐
                    │ Serveur central       │  (unique, public HTTPS)
                    │ SQLite → Postgres si  │
                    │ le volume l'exige     │
                    └──────────┬────────────┘
                     Dashboard multi-sites (sélecteur de site)
```

**Principe directeur (hérité de C, corrigé) : le nœud (BirdNET-Go inchangé) reste l'unique autorité
d'écriture, toujours autonome — sa base SQLite locale continue de grossir même hors ligne.** Le
bridge colocalisé ne **pousse jamais rien en direct dans une base distante** (ce qui aurait été le
piège de B, confirmé par lecture de code : `output.mysql` sans réseau = perte silencieuse et
définitive des détections, cf. §13). Deux canaux, bien séparés :

1. **Canal de données cœur (détections, calendrier, espèces, stats, commandes)** — le bridge **pousse**
   en HTTPS sortant pur, sans jamais avoir besoin d'un port entrant ni de Tailscale. C'est le point
   emprunté à la conception A pour corriger la faiblesse de C notée par le juge terrain (« découpler
   le chemin de données cœur de la disponibilité de Tailscale — si Tailscale tombe, seul le live
   dégrade, jamais le cœur du produit »).
2. **Canal live (audio HLS, spectrogramme dépliable)** — nécessite que le serveur puisse *joindre* le
   nœud (le nœud héberge le flux). Ce sens-là dépend de Tailscale (ou d'un tunnel équivalent). S'il est
   indisponible, seul ce bloc dégrade proprement (« site hors ligne »), jamais le reste du produit.

Le pilotage des réglages du nœud (seuils, exclusions, démarrage HLS) est **toujours exécuté
localement par le bridge** (same-origin `localhost:8080`), jamais par le serveur central directement
à travers Tailscale — ceci résout d'un coup la faiblesse CSRF partagée par les trois conceptions
(§7) et l'exigence explicite « piloter les mutations de settings via l'agent/bridge colocalisé »
(greffe de A).

---

## 2. Composants

| # | Composant | Rôle | Techno | Où il tourne | Réutilisé de BirdNET-Go | Neuf |
|---|---|---|---|---|---|---|
| 1 | **BirdNET-Go** | Capture micro + inférence + base locale + API v2/HLS | Go, binaire figé (tag `20260823`, ou tag officiel équivalent linux-arm64 sur les Pi) | Chaque nœud | Tout, **inchangé** | — |
| 2 | **Bridge** | Lit `birdnet.db` en lecture seule, pousse détections+prédictions, poll les commandes, exécute localement les mutations CSRF (settings, HLS start/heartbeat), relaie les événements « en écoute » quasi temps réel | Python 3.13, `sqlite3` stdlib, `httpx` | Colocalisé avec chaque nœud, process natif (jamais Docker — cf. §10) | Requêtes SQL sur le schéma v2 (`detections`, `detection_predictions`, `audio_sources`, `labels`), appels HTTP CSRF vers `localhost:8080` | Tout le code |
| 3 | **Serveur** | Ingestion idempotente, modèle multi-sites, top-5 clips, règles par site, fiches espèces, agrégations stats (proxy puis shadow), API pour le frontend | Python 3.13, FastAPI, SQLAlchemy + SQLite | VPS ou machine chez Armand (Mac en S1) | Reprend la *forme* de plusieurs familles d'endpoints analytics à titre de référence, aucun code Go copié | Tout le code + schéma DB |
| 4 | **Tailscale** | Réseau privé mesh pour joindre un nœud NATé, réservé au **live** et aux appels GET directs de clips | Binaire Tailscale | Chaque nœud + serveur | — | Configuration seule |
| 5 | **Frontend** | Dashboard, base espèces, stats, système | Vite + Svelte 5 + Tailwind v4 + TypeScript strict | Servi par le serveur (build statique) | Tokens CSS, composants génériques, i18n, infra D3 — copiés/adaptés, CC BY-NC-SA 4.0 (§0.3) | Toute la couche données (stores, client API), dashboard, fiche espèce, pages système |
| 6 | **Pipeline fiches espèces** | Génère les 368 fiches | Agents Claude Haiku + script d'orchestration Python | Exécuté ponctuellement (machine d'Armand ou serveur) | `species_universe_fr.json` en entrée ; `GET /api/v2/species/taxonomy` d'un nœud accessible pour famille/genre/ordre (jamais copié depuis le dépôt Go, pour rester en zone de licence claire) | Tout |
| 7 | **Instance BirdNET-Go « shadow »** (WP tardif, voir §9bis/§13) | Réexpose gratuitement `/api/v2/analytics/*`, `/insights/*`, `/species/taxonomy` sur une copie agrégée multi-sites, jamais sur l'écriture temps réel | Go, même binaire, Docker | Serveur | Binaire + API REST entière | Juste le job de rejeu qui alimente sa base MySQL dédiée |

---

## 3. Flux de données nœud → serveur

### 3.1 Canal détections + prédictions (push, HTTPS sortant pur)

**Curseur** : `id` croissant de `detections`, **jamais** `detected_at` (l'ordre d'insertion et
l'ordre temporel divergent sur une fraction non négligeable des lignes — un traitement concurrent de
segments audio peut insérer une détection « ancienne » après une détection « récente »). **L'état
canonique « jusqu'où ce nœud est synchronisé » est porté par le SERVEUR** (table
`node_sync_state`, §4), pas par le bridge — correction explicite de la faiblesse notée sur C : après
restauration d'une sauvegarde serveur plus ancienne, le serveur redemande légitimement depuis un
`id` antérieur, et l'idempotence (`UNIQUE(node_id, node_local_id)`) absorbe les doublons sans jamais
créer de duplicata. Le bridge garde une copie locale du curseur uniquement comme optimisation
(éviter de relire toute la base à chaque cycle), mais **doit** se resynchroniser sur la valeur
renvoyée par le serveur à chaque appel — jamais l'inverse.

**Requête locale du bridge** (contre `birdnet.db`, lecture seule, `mode=ro`) :
```sql
SELECT d.id, d.detected_at, d.confidence, d.clip_name, d.source_id,
       l.scientific_name, s.display_name AS source_display_name
FROM detections d
JOIN labels l ON l.id = d.label_id
LEFT JOIN audio_sources s ON s.id = d.source_id
WHERE d.id > :last_synced_id
ORDER BY d.id ASC
LIMIT 200;

SELECT p.detection_id, l.scientific_name, p.confidence
FROM detection_predictions p
JOIN labels l ON l.id = p.label_id
WHERE p.detection_id IN (...)
ORDER BY p.confidence DESC;   -- JAMAIS ORDER BY rank (colonne inutilisable, toujours =1 sur le
                                -- chemin d'écriture v2-only actif)
```
Rappel structurel : la prédiction **primaire** n'est pas dans `detection_predictions`, elle vient de
`detections.label_id` (déjà résolue via le premier `JOIN`) — le bridge doit l'inclure explicitement
en tête de la liste `predictions` envoyée au serveur (confiance = celle de la détection elle-même).

**Cadence** : cycle de push toutes les ~20-30 s (pas critique en latence — voir §3.3 pour le « en
écoute » quasi temps réel, qui emprunte un canal séparé plus rapide).

**Format du message** — voir §5.2 pour le schéma JSON exact (`POST /api/v1/nodes/{node_id}/sync`).

**Idempotence** : contrainte `UNIQUE(node_id, node_local_id)` côté serveur → un `POST` rejoué après
coupure est un no-op silencieux (compté dans `duplicates`, jamais une erreur).

**NAT / hors-ligne / reprise** : le lien est **toujours initié par le bridge** — aucun port entrant
requis sur le nœud, compatible box familiale sans IP fixe, **sans avoir besoin de Tailscale pour ce
canal**. Hors ligne : le bridge continue de suivre `birdnet.db` (qui grossit normalement, BirdNET-Go
n'est jamais affecté) et retente avec backoff exponentiel (base 5 s, plafond 5 min, jitter ±25 %) ;
au retour du réseau, il rejoue depuis le curseur serveur — aucune perte, `birdnet.db` local restant
la source de vérité définitive pour ce nœud.

### 3.2 Top-5 clips par site et par espèce — qui décide, quand, quoi supprimer

**Amendement du 27/09/2026 (Armand/Claude, après synthèse) : le transfert des clips est un PUSH du
bridge, jamais un GET du serveur vers le nœud.** Raison : le canal de données cœur (détections,
calendrier, espèces, top-5) ne doit dépendre ni de Tailscale ni d'un port entrant sur le nœud. Seul
le live (§6) garde une dépendance à Tailscale.

- **Qui décide** : le **serveur**, dès réception d'un lot dans `POST /sync`. Pour chaque détection
  reçue avec `has_clip=true`, il compare sa confiance au 5ᵉ meilleur score connu pour
  `(site, espèce)` dans `kept_clips`. Les candidats retenus sont renvoyés **dans la réponse du sync**
  (`want_clips: [node_local_id, …]`).
- **Transfert** : le bridge lit le fichier WAV **sur le disque du nœud** (`<clips_dir>/<clip_name>`,
  `clips_dir` = `realtime.audio.export.path` de BirdNET-Go, soit `local-test/data/clips` en S1) et
  l'envoie en `POST /api/v1/nodes/{node_id}/clips/{node_local_id}` (multipart, champ `audio`).
  Si le fichier a déjà été purgé localement (course avec `clip-retention.py`), le bridge répond
  `POST …/clips/{node_local_id}/missing` et le serveur marque `kept_clips.fetched_at = NULL,
  missing = 1` ; le rang est alors libéré pour le candidat suivant.
- **Spectrogramme** : généré **côté serveur** à partir du WAV reçu (`sox in.wav -n spectrogram …`,
  sox disponible sur le Mac et installable dans l'image Docker du serveur). Un seul chemin de code
  pour le direct et pour le backfill hors ligne du Mans (§11), aucune dépendance à l'API du nœud.
- **Marge de sécurité côté nœud** : politique locale inchangée (`clip-retention.py`, top-10 par
  confiance, jamais de purge avant 30 min). Le cycle de push (20-30 s) laisse une marge confortable.
- **Quoi supprimer** : quand un nouveau clip entre dans le top-5 serveur d'un couple site/espèce, le
  serveur supprime **son propre fichier stocké** (jamais celui du nœud) et met à jour
  `kept_clips.evicted_at` — l'historique des détections/prédictions n'est jamais perdu, seul le média
  part. Les détections verrouillées côté nœud n'ont pas de statut particulier côté serveur (le top-5
  serveur est purement par confiance).

### 3.3 « En écoute » quasi temps réel (bloc dashboard)

Canal séparé, plus léger et plus rapide que le push de détections : le bridge maintient un
abonnement **local** persistant à `GET /api/v2/detections/stream` (SSE `pending`, public sur le
nœud) et relaie chaque événement, immédiatement, par un `POST` sortant léger vers
`/api/v1/nodes/{node_id}/pending` (fire-and-forget, retry best-effort, jamais bloquant). Ce canal
reste **push pur** (bridge → serveur, aucune dépendance à Tailscale) — c'est ce qui alimente le bloc
« En écoute » du dashboard (nom d'espèce, statut, compteur de coups) en quasi temps réel, y compris
pour un site distant derrière NAT. Seul le **spectrogramme live** (audio réel, dans l'accordéon
déplié) nécessite le relais HLS via Tailscale (§6).

### 3.4 Commandes serveur → nœud (settings, démarrage live)

Canal de poll **rapide et séparé** du push de détections (car la latence compte pour « démarrer
l'écoute live ») : `GET /api/v1/nodes/{node_id}/commands`, cadence ~3-5 s pendant qu'une session live
est active, sinon repli à une cadence plus lente (~30 s) pour ne pas gaspiller de requêtes quand rien
n'est en attente. Détail complet en §7.

### 3.5 Labels multi-espèces

Chaque détection poussée embarque déjà ses prédictions secondaires (≤9, triées `confidence DESC`) —
aucun appel réseau supplémentaire n'est nécessaire pour peupler les chips « Rouge-gorge 100 %, Pie
bavarde 20 % » sur la fiche espèce : elles sont dans le payload initial (§3.1).

---

## 4. Modèle de données serveur (SQLite, SQLAlchemy 2.x)

Principe directeur (hérité de C, corrigé) : **le serveur ne dérive jamais l'identité d'un site depuis
un champ interne à BirdNET-Go** (`main.name`/`audio_sources.node_name`) — cette colonne n'a
**aucune garantie d'unicité** entre nœuds (deux installations neuves partagent la valeur par défaut
`"BirdNET-Go"`, R10-1/R10-6). L'identité de site/nœud est assignée **par le serveur lui-même** à
l'enregistrement (token + `node_id`), jamais dérivée de l'amont. Par discipline et par confort
opérationnel, le bridge **règle automatiquement** `main.name` sur le nœud pour qu'il corresponde au
slug du site assigné par le serveur (voir §7.3) — mais le rattachement de site côté serveur ne
dépend jamais de la valeur réelle de ce champ.

```sql
-- Identité et supervision

CREATE TABLE sites (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  slug          TEXT NOT NULL UNIQUE,          -- ex. "pornic", "le-mans" — assigné par le serveur
  timezone      TEXT NOT NULL DEFAULT 'Europe/Paris',
  lat           REAL,
  lon           REAL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE nodes (
  id                        INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id                   INTEGER NOT NULL REFERENCES sites(id),
  name                      TEXT NOT NULL,             -- libellé humain, ex. "Pi salon Rennes"
  tailscale_hostname        TEXT,                       -- ex. "pornic.tailXXXX.ts.net", NULL si local
  api_base_url              TEXT,                        -- ex. "http://localhost:8080" ou via Tailscale
  bridge_shared_secret_hash TEXT NOT NULL,               -- SHA-256, secret en clair jamais stocké
  bearer_token_hash         TEXT,                        -- Bearer natif BirdNET-Go, activé dès Tailscale (§7.4)
  birdnet_go_version        TEXT,
  created_at                TEXT NOT NULL DEFAULT (datetime('now')),
  decommissioned_at         TEXT
);

CREATE TABLE node_sync_state (
  node_id                   INTEGER PRIMARY KEY REFERENCES nodes(id),
  last_synced_detection_id  INTEGER NOT NULL DEFAULT 0,   -- id LOCAL au nœud (BirdNET-Go), pas un id serveur
  last_sync_at              TEXT
);

CREATE TABLE node_status (
  node_id                     INTEGER PRIMARY KEY REFERENCES nodes(id),
  last_seen_at                TEXT,
  last_detection_at           TEXT,
  mic_device_name             TEXT,
  mic_healthy                 INTEGER,     -- bool 0/1
  disk_free_pct                REAL,
  birdnet_go_pid_alive          INTEGER,
  bridge_version                TEXT,
  dynamic_thresholds_snapshot_json TEXT     -- miroir lecture seule de GET /dynamic-thresholds
);

CREATE TABLE node_commands (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id       INTEGER NOT NULL REFERENCES nodes(id),
  kind          TEXT NOT NULL CHECK (kind IN (
                    'set_species_threshold', 'exclude_species', 'include_species',
                    'reset_dynamic_threshold', 'start_live', 'live_heartbeat', 'stop_live')),
  payload_json  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'delivered', 'applied', 'failed')),
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  delivered_at  TEXT,
  applied_at    TEXT,
  error_message TEXT
);

-- Détections (copie serveur, jamais les tables natives de BirdNET-Go)

CREATE TABLE detections (
  id                            INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id                       INTEGER NOT NULL REFERENCES nodes(id),
  site_id                       INTEGER NOT NULL REFERENCES sites(id),   -- dénormalisé, évite un JOIN à chaque requête
  node_local_id                 INTEGER NOT NULL,        -- detections.id côté BirdNET-Go du nœud
  detected_at_utc               TEXT NOT NULL,
  scientific_name               TEXT NOT NULL,
  confidence                    REAL NOT NULL,
  source_id                     INTEGER,                  -- audio_sources.id côté nœud, informatif
  source_display_name           TEXT,
  clip_name                     TEXT,                      -- chemin relatif côté nœud (clips/...)
  has_clip                      INTEGER NOT NULL DEFAULT 0,
  redirected_to_scientific_name TEXT,                       -- règle "rediriger" : affichage seul, jamais la donnée brute
  ingested_at                   TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (node_id, node_local_id)
);
CREATE INDEX idx_detections_site_species ON detections(site_id, scientific_name);
CREATE INDEX idx_detections_detected_at ON detections(detected_at_utc);

CREATE TABLE predictions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  detection_id  INTEGER NOT NULL REFERENCES detections(id) ON DELETE CASCADE,
  scientific_name TEXT NOT NULL,
  confidence     REAL NOT NULL
  -- ORDER BY confidence DESC à la lecture, jamais de colonne "rank" (héritage inutilisable de BirdNET-Go)
);
CREATE INDEX idx_predictions_detection ON predictions(detection_id);

CREATE TABLE kept_clips (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id               INTEGER NOT NULL REFERENCES sites(id),
  scientific_name       TEXT NOT NULL,
  detection_id          INTEGER NOT NULL REFERENCES detections(id),
  confidence            REAL NOT NULL,
  audio_path            TEXT,             -- chemin local serveur, NULL tant que non rapatrié
  spectrogram_path      TEXT,
  rank_in_site_species  INTEGER NOT NULL, -- 1..5
  fetched_at            TEXT,
  evicted_at            TEXT,
  missing               INTEGER NOT NULL DEFAULT 0,   -- 1 si le nœud a signalé le clip déjà purgé
  UNIQUE (site_id, scientific_name, detection_id)
);
CREATE INDEX idx_kept_clips_lookup ON kept_clips(site_id, scientific_name, evicted_at);

-- Revues / signalements

CREATE TABLE reviews (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  detection_id      INTEGER NOT NULL REFERENCES detections(id),
  kind              TEXT NOT NULL CHECK (kind IN ('correct', 'false_positive')),
  note              TEXT,
  created_by        TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  synced_to_node_at TEXT     -- rempli une fois POST /detections/:id/review réussi côté nœud (best-effort)
);

CREATE TABLE false_negative_reports (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id       INTEGER NOT NULL REFERENCES sites(id),
  scientific_name TEXT NOT NULL,
  reported_at   TEXT NOT NULL DEFAULT (datetime('now')),
  reported_by   TEXT,
  approx_time   TEXT,
  notes         TEXT
);

-- Règles espèce/site

CREATE TABLE species_site_rules (
  id                              INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id                         INTEGER NOT NULL REFERENCES sites(id),
  scientific_name                 TEXT NOT NULL,
  rule                             TEXT NOT NULL CHECK (rule IN ('present', 'impossible', 'redirect')),
  threshold_override               REAL,
  redirect_to_scientific_name      TEXT,
  reason                            TEXT,
  updated_at                        TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (site_id, scientific_name)
);

-- Fiches espèces (368 + toute espèce détectée hors univers)

CREATE TABLE species_sheets (
  scientific_name       TEXT PRIMARY KEY,
  common_name_fr        TEXT,
  taxonomy_json         TEXT,     -- {class, order, family, family_common_fr, genus}
  photo_url             TEXT,
  photo_license          TEXT,
  photo_author            TEXT,
  wikipedia_url            TEXT,
  summary_fr                TEXT,
  habitat                    TEXT,
  diet                        TEXT,
  activity_pattern              TEXT,      -- "diurne" | "nocturne" | "crépusculaire"
  migration_json                 TEXT,      -- {hiverne, niche, passage}
  rarity_note                      TEXT,
  france_universe_json               TEXT,  -- copie de l'entrée species_universe_fr.json (maxScore, cities, months)
  generated_at                        TEXT,
  generator_model                       TEXT,
  reviewed_by_human                       INTEGER NOT NULL DEFAULT 0,
  sources_json                              TEXT
);
```

---

## 5. API serveur

Toutes les routes sous `/api/v1`, JSON. Deux familles d'authentification distinctes :
- **Ingestion nœud→serveur** : `Authorization: Bearer <bridge_shared_secret>` (secret propre par
  nœud, §7.4).
- **Navigateur (famille)** : session cookie issue d'un login simple (§10.4) — lecture publique en
  invité possible plus tard si Armand le souhaite (non retenu par défaut, voir décisions ouvertes).

### 5.1 Ingestion (bridge → serveur)

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/nodes/register` | Enregistrement initial d'un nœud (normalement invoqué une fois par Armand via un script admin, pas en libre-service) — retourne `{node_id, bridge_shared_secret}` |
| POST | `/nodes/{node_id}/sync` | Pousse un lot de détections + prédictions (§5.2) |
| POST | `/nodes/{node_id}/pending` | Relaie un événement « en écoute » (§3.3) |
| POST | `/nodes/{node_id}/clips/{node_local_id}` | Upload multipart (`audio` = WAV) d'un clip demandé via `want_clips` (§3.2) |
| POST | `/nodes/{node_id}/clips/{node_local_id}/missing` | Le clip a déjà été purgé sur le nœud (§3.2) |
| POST | `/nodes/{node_id}/heartbeat` | Statut nœud (micro, disque, version, seuils dynamiques) |
| GET | `/nodes/{node_id}/commands` | Poll des commandes en attente (§3.4) |
| POST | `/nodes/{node_id}/commands/{cmd_id}/ack` | Accusé de réception/résultat d'une commande |

### 5.2 Format des messages — détail

**`POST /nodes/{node_id}/sync`** — corps :
```json
{
  "detections": [
    {
      "node_local_id": 4512,
      "detected_at_utc": "2026-09-27T13:30:12Z",
      "scientific_name": "Erithacus rubecula",
      "confidence": 0.98,
      "source_id": 1,
      "source_display_name": "Sound Card 1",
      "clip_name": "2026/09/erithacus_rubecula_98p_20260927T133012Z.wav",
      "has_clip": true,
      "predictions": [
        {"scientific_name": "Turdus merula", "confidence": 0.0207},
        {"scientific_name": "Bubo bubo", "confidence": 0.0066}
      ]
    }
  ]
}
```
Réponse :
```json
{
  "accepted": 1,
  "duplicates": 0,
  "synced_up_to_id": 4512,
  "want_clips": [4512],
  "commands": [
    {"id": 88, "kind": "set_species_threshold",
     "payload": {"scientific_name": "Larus argentatus", "threshold": 0.4}}
  ]
}
```
`synced_up_to_id` est **la valeur canonique** que le bridge doit adopter comme nouveau curseur —
même si son propre fichier local suggérait autre chose (reprise après restauration serveur, §3.1).
`commands` est un bonus opportuniste (pas de round-trip supplémentaire) ; le canal principal de
livraison des commandes reste le poll dédié (§5.3), plus réactif.

**`GET /nodes/{node_id}/commands`** — réponse :
```json
{ "commands": [ {"id": 89, "kind": "start_live", "payload": {"session_id": "abcd1234"}} ] }
```

**`POST /nodes/{node_id}/commands/{cmd_id}/ack`** — corps :
```json
{
  "status": "applied",
  "result": {"stream_token": "…", "playlist_url": "http://localhost:8080/api/v2/streams/hls/t/XXXX/playlist.m3u8"},
  "error": null
}
```

**`POST /nodes/{node_id}/pending`** — corps :
```json
{
  "scientific_name": "Erithacus rubecula",
  "common_name": "Rougegorge familier",
  "status": "active",
  "confidence_hint": 0.8,
  "hit_count": 3,
  "thumbnail_url": null,
  "first_detected_unix": 1790399000,
  "last_updated_unix": 1790399005
}
```

**`POST /nodes/{node_id}/heartbeat`** — corps :
```json
{
  "mic_device_name": "HyperX QuadCast 2",
  "mic_healthy": true,
  "disk_free_pct": 62.4,
  "birdnet_go_version": "20260823",
  "birdnet_go_pid_alive": true,
  "bridge_version": "0.3.0",
  "dynamic_thresholds_snapshot": [{"scientific_name": "Erithacus rubecula", "level": 3, "current_value": 0.2}]
}
```

### 5.3 Navigateur (dashboard / espèces / stats / système)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/sites` | Liste des sites (sélecteur) |
| GET | `/sites/{site}/now` | Dernier `pending` connu + `node_status` (bloc « en écoute ») |
| GET | `/sites/{site}/pending/stream` | SSE navigateur, relaie les événements poussés par le bridge |
| GET | `/sites/{site}/calendar?date=&limit=0` | Activité quotidienne, toutes espèces, sans limite |
| GET | `/sites/{site}/species` | Espèces réellement détectées sur ce site |
| GET | `/species` | Univers France (368, `species_sheets` + `species_universe_fr.json`) + flag « déjà détecté » |
| GET | `/species/{scientific_name}` | Fiche complète |
| GET | `/species/{scientific_name}/sites/{site}/top-clips` | ≤5 enregistrements + prédictions, URLs média |
| GET | `/species/{scientific_name}/presence?site=` | Présence dans le temps (agrégation `detections`) |
| GET | `/recordings/{kept_clip_id}/audio` | Sert le fichier audio rapatrié |
| GET | `/recordings/{kept_clip_id}/spectrogram` | Sert le PNG rapatrié |
| GET | `/sites/{site}/stats/kpis` \| `/daily` \| `/heatmap` \| `/ridgeline` \| `/phenology` \| `/confidence` \| `/insights` | Statistiques (proxy live vers le nœud en MVP, shadow BirdNET-Go plus tard — §9bis) |
| GET | `/sites/{site}/live/hls/*`, POST `/sites/{site}/live/start`, POST `.../heartbeat` | Relais live (§6) |
| GET | `/sites/{site}/live/audio-level` (SSE) | Découverte de sources pour le sélecteur micro |
| GET | `/nodes` | Liste des nœuds + statut |
| GET, PUT | `/sites/{site}/species-rules/{scientific_name}` | Règle présente/impossible/redirection (déclenche une `node_command` si applicable) |
| GET | `/sites/{site}/dynamic-thresholds`, `/{species}/events` | Transparence (miroir lecture seule, mis à jour via heartbeat) |
| DELETE | `/sites/{site}/dynamic-thresholds/{species}` | Reset (mutation → `node_command`, exécutée localement par le bridge) |
| POST | `/sites/{site}/reviews` | Faux positif **ou** confirmation, sur une détection existante |
| POST | `/false-negatives` | Signalement manuel (aucune détection associée, par construction) |
| POST | `/species/{scientific_name}/sheet/regenerate` | Relance le pipeline Haiku pour une fiche |
| POST | `/auth/login`, `/auth/logout` | Session famille (§10.4) |

---

## 6. Audio et spectrogramme live à distance

BirdNET-Go n'a **aucun** flux bas niveau réutilisable hors HLS : le pipeline (routeur audio interne
→ FFmpeg/encodeur natif → segments) vit entièrement dans le process qui a le micro. Le spectrogramme
live est calculé **côté navigateur** (Web Audio API, `AnalyserNode`) à partir de l'audio HLS déjà
reçu — donc un relais HLS correctement fait suffit à faire marcher le spectrogramme, sans code
serveur dédié à l'image.

**Correction factuelle appliquée** (erreur commune aux trois conceptions d'origine) : le skipper
CSRF de BirdNET-Go n'exempte les préfixes `/api/v2/streams/` (et voisins) **que pour les méthodes
HTTP sûres** (GET/HEAD/OPTIONS). Les appels **`POST /streams/hls/:sourceID/start`** et
**`POST /streams/hls/heartbeat`** restent des mutations soumises à la validation CSRF complète
(cookie + `X-CSRF-Token`), y compris pour un client Bearer/Tailscale — il n'y a « rien à
réimplémenter côté auth » **uniquement** pour les GET (playlist, segments, niveau audio).

**Mécanisme retenu (hybride, corrigé)** :

1. **Démarrage/maintien du flux (mutant) — exécuté localement par le bridge**, jamais par le serveur
   central à travers Tailscale. Le serveur crée une `node_command` `start_live` (§5.2) ; le bridge la
   récupère au prochain poll (cadence rapide, §3.4), exécute localement le cycle CSRF complet
   (`GET /api/v2/app/config` → cookie + token → `POST .../streams/hls/:sourceID/start` avec
   `X-CSRF-Token`, same-origin sur `localhost:8080`), puis renvoie `{stream_token, playlist_url}`
   dans l'ack de la commande. Le heartbeat (`POST .../streams/hls/heartbeat`, requis toutes les
   ~20 s pour garder le flux vivant) est ensuite maintenu **par le bridge lui-même** tant qu'une
   session live est active — jamais par le serveur.
2. **Lecture du flux (GET, exempté de CSRF) — proxiée directement par le serveur via Tailscale**,
   sans passer par le bridge : `GET .../streams/hls/t/:token/playlist.m3u8` et ses segments, ainsi
   que `GET /api/v2/streams/audio-level` (SSE, découverte de sources). Le `stream_token` généré par
   le nœud reste l'unique jeton de session HLS pour ce sens-là.

Cette séparation (mutant → bridge local ; lecture → proxy direct serveur) est **strictement** la
greffe demandée depuis la conception A, appliquée au modèle de C : elle corrige à la fois l'erreur
CSRF partagée par les trois conceptions d'origine et le principe « le serveur ne parle jamais
directement à l'API mutante d'un nœud », cohérent avec le traitement déjà appliqué aux settings
(§7).

**Dégradation gracieuse** : si le nœud est hors tailnet ou ne répond pas (timeout 3-5 s), le proxy
échoue proprement ; le frontend affiche « {site} hors ligne » à la place du bloc live, sans bloquer
le reste du dashboard (le bloc « en écoute » textuel, lui, continue de fonctionner via le canal push
du §3.3, indépendant de Tailscale).

**Limite assumée à documenter pour Armand** : HLS est un flux par nœud, un seul à la fois (changer de
source arrête puis redémarre un nouveau flux) — cohérent avec un sélecteur de site (« on écoute un
site à la fois »), mais on ne pourra jamais écouter deux sites simultanément dans la même page.

---

## 7. Pilotage des nœuds depuis le serveur

### 7.1 Ce qui est pilotable (hot-reload, jamais de redémarrage requis)

- Seuil par espèce : `PATCH /settings/species` avec `config.<espèce>.threshold` → implémente
  `species_site_rules.rule = 'present'` (seuil abaissé).
- Exclusion : `Species.Exclude` → implémente `rule = 'impossible'`, prioritaire même sans filtre de
  zone actif.
- Reset d'un seuil dynamique : `DELETE /dynamic-thresholds/:species`.
- `main.name` (voir §7.3).

### 7.2 CSRF — traité une fois, jamais recontourné

Le middleware CSRF de BirdNET-Go est **global**, s'exécute **avant** l'authentification dans la
chaîne Echo, et son skipper ne connaît **aucune** exemption Bearer token — vrai pour toutes les
routes mutantes (`review`, `lock`, `ignore`, `batch/*`, `PATCH`/`PUT settings`, `range/rebuild`,
`DELETE dynamic-thresholds`, et, cf. §6, les `POST` HLS). **Décision d'architecture (héritée de C,
renforcée par la greffe de A) : le serveur central ne parle JAMAIS directement en mutation à l'API
BirdNET-Go d'un nœud, même via Tailscale.** Seul le **bridge**, qui tourne localement
(`localhost:8080`, même origine que le binaire), exécute ces mutations — il peut trivialement
compléter le cycle CSRF/session (pas de Bearer cross-NAT à maintenir). Le client CSRF est écrit
**une fois**, en bibliothèque testée (`node/bridge/csrf_client.py`), puis réutilisé pour tous les
types de mutation (settings, review, HLS start/heartbeat, dynamic-thresholds reset).

Flux complet pour une règle :
1. Armand enregistre une règle (`PUT /sites/{site}/species-rules/{scientific_name}`).
2. Le serveur écrit la règle dans `species_site_rules` **et** crée une `node_command` correspondante
   (statut `pending`) — motif **explicite pending/applied/failed** repris de la conception A (plus
   auditable qu'un simple champ `pushed_to_node_at` nullable) : Armand voit exactement quelles règles
   ont réellement été appliquées, sur quel nœud, et quand.
3. Le bridge la récupère au prochain poll (§3.4), exécute le cycle CSRF local, applique, `ack` avec
   `status: applied` ou `failed` + `error_message`.
4. En cas d'échec (nœud hors ligne au moment du poll), la commande reste `pending` — retentée au
   cycle suivant, jamais perdue.

### 7.3 Discipline `main.name` — automatisée, pas seulement documentée

Greffe de B, renforcée : à l'enregistrement d'un nœud, le bridge **règle automatiquement**
`PATCH /settings/main` avec `name = <slug du site assigné par le serveur>`, puis **vérifie** via
`GET /settings/main` que la valeur a bien été appliquée (pas seulement une checklist humaine). Ceci
n'est **jamais** la source de vérité du rattachement de site côté serveur (§4) — c'est une hygiène
pour la propre UI native du nœud et pour un futur usage MQTT, rien de plus. Le bridge refuse de
démarrer sa boucle de push tant que cette vérification n'a pas réussi une première fois (log clair,
pas de crash silencieux).

### 7.4 Sécurité de l'API nœud

- **`bridge_shared_secret`** : secret opaque long, propre à chaque nœud, généré côté serveur à
  l'enregistrement, présenté par le bridge sur chaque appel (`Authorization: Bearer`), stocké
  **hashé** (SHA-256) côté serveur, en clair uniquement dans le fichier de config local du nœud
  (permissions 600). Protège contre un appareil compromis du même tailnet qui tenterait d'usurper un
  autre nœud.
- **Bearer token natif BirdNET-Go** (greffe de B) : activé sur chaque nœud **dès qu'il rejoint le
  tailnet** (pas seulement si un incident le justifie — décision par défaut, §« décisions pour
  Armand »), en plus de `security.privatemode: true`. Comble la faiblesse « API nœud grande ouverte
  sur le mesh » : même un appareil du tailnet qui réussirait à joindre `nœud:8080` directement
  (contournant le bridge) ne pourrait rien muter sans ce token. Le bridge, qui exécute déjà le cycle
  CSRF localement, ajoute simplement l'en-tête `Authorization: Bearer <token>` à ses appels — coût
  d'implémentation nul, le mécanisme est déjà natif au binaire.

### 7.5 Faux positif / faux négatif

**Faux positif** (détection existante) : le serveur enregistre la revue dans `reviews`
(authoritative côté serveur, jamais bloquant) **et** la pousse, en best-effort, vers
`POST /detections/:id/review` **du nœud d'origine** via le bridge (même cycle CSRF que les settings)
— pour que l'UI native du nœud reste cohérente si Armand la consulte localement. **Ne jamais écrire
directement dans `detection_reviews`** en contournant l'API : une écriture directe contourne
`invalidateDetectionCache()` (le cache mémoire des listes de détections du binaire), ce qui laisserait
l'UI native du nœud afficher un statut `verified` périmé pendant un temps indéterminé — c'est
l'erreur identifiée dans une des conceptions écartées, explicitement évitée ici.

Côté UI, le point d'entrée est le motif `ActionMenu.svelte` de BirdNET-Go (déjà câblé avec
`onMarkCorrect`/`onMarkFalsePositive`/`onToggleSpecies`/`onToggleLock`) — greffe de B : à réutiliser
comme référence d'implémentation pour le nouveau composant de reclassement plutôt que d'inventer une
UX différente depuis zéro (voir §8).

**Faux négatif** : BirdNET-Go n'a, par construction, **aucune notion de faux négatif** (le schéma
`detection_reviews` ne connaît que `correct`/`false_positive` ; l'absence de ligne = non vérifié,
jamais « manqué »). C'est donc **exclusivement** un enregistrement serveur
(`false_negative_reports`), sans aucune tentative de créer une fausse ligne côté nœud (créer des
lignes `detections`/`labels` depuis un écrivain externe casserait les invariants gérés par GORM/
AutoMigrate côté binaire — à ne jamais faire).

### 7.6 Redirection d'espèce

Aucun mécanisme natif (confirmé : ni `SpeciesConfig`, ni `SpeciesAction`, ni `TaxonomySynonyms` — ce
dernier ne sert qu'à la résolution d'image, pas à la détection). La redirection reste **un
remappage d'affichage côté serveur uniquement** : `detections.redirected_to_scientific_name` est
calculé à l'ingestion (ou recalculé si la règle change après coup, via un job de rattrapage), sans
jamais toucher `scientific_name` d'origine — la donnée brute reste intacte pour l'audit.

---

## 8. Frontend

**Stack** : Vite + Svelte 5 (runes) + TypeScript strict + Tailwind v4 (CSS natif, aucune
bibliothèque de composants). Routeur maison minimal (History API + résolution de composant), sur le
modèle du `App.svelte` de BirdNET-Go mais réécrit en propre (trop petit pour justifier une copie).

### 8.1 Composants copiés/adaptés (licence CC BY-NC-SA 4.0, cf. §0.3)

- `frontend/src/styles/tailwind.css` (bloc `@theme`) + `schemes.css` (6 palettes clair/sombre).
- Mécanique i18n (`lib/i18n/config.ts`, `store.svelte.ts`, `utils.ts`) — structure copiée, **contenu**
  (`messages/*.json`) réécrit pour notre propre vocabulaire.
- Infra D3 : `BaseChart.svelte`, `utils/theme.ts`, `utils/axes.ts`, `utils/scales.ts`,
  `utils/interactions.ts`, `utils/labels.ts`, `utils/speciesColor.ts` — nécessaire car le nouveau
  frontend ne réutilise pas les pages BirdNET-Go telles quelles, seulement leurs données via l'API
  serveur (§5.3) : les graphes doivent être re-rendus côté nouveau frontend.
- `components/ui/Modal.svelte`, `CollapsibleSection.svelte` — **ce dernier est le candidat direct**,
  identifié précisément (pas une supposition), pour le spectrogramme live « dépliable, replié par
  défaut, flèche vers le bas » demandé par Armand. **Correction factuelle appliquée** : contrairement
  à ce qu'une conception écartée affirmait, `MiniSpectrogram.svelte` n'a **jamais** été confirmé
  comme ayant un vrai mécanisme accordéon (aucune balise `<details>` trouvée dans le fichier lu) —
  `MiniSpectrogram.svelte` est repris seulement comme **référence d'implémentation** du pipeline HLS
  + Web Audio API (câblage interne), enveloppé dans un vrai `CollapsibleSection.svelte` côté nouveau
  frontend pour le comportement de pliage.
- `components/ui/image-utils.ts` (`handleBirdImageError`) — logique de retry anti-flash sur le proxy
  image, à respecter telle quelle pour toute nouvelle fiche espèce affichant des photos.
- `features/analytics/components/modals/SpeciesDetailModal.svelte` — repris comme **coquille**
  seulement (wrapper `Modal`, gestion `isOpen`/cache anti-flash, header nom localisé + scientifique,
  footer) : son corps (`children` snippet) n'a **aucune** trace de liste d'enregistrements, de
  spectrogramme ou de trivia (vérifié ligne à ligne) — à reconstruire presque entièrement.
  `ActionMenu.svelte` (§7.5) comme référence pour le point d'entrée reclassement.

### 8.2 Composants neufs

- `SiteSelector.svelte` — sélecteur global de site.
- `RecordingList.svelte` — les ≤5 enregistrements, chacun avec spectrogramme jouable et chips de
  labels multi-espèces (`MultiSpeciesLabels.svelte`).
- `SpeciesSheet.svelte` — bloc trivia structuré (taxonomie, aire, comportement, migration
  hiverne/niche/passage, rareté locale par site).
- Page/route **`/species/:id`** — fiche espèce **dédiée, deep-linkable** (greffe de A, doublement
  endossée par les juges terrain et faisabilité) : lien partageable, retour navigateur fonctionnel —
  en plus de l'accès depuis la liste (pas seulement une modale comme l'héritage BirdNET-Go).
- Pages « Règles par espèce et par site », « Faux négatifs », « Statut des nœuds ».
- `CurrentlyHearingBlock.svelte` — consomme `GET /sites/{site}/pending/stream` (SSE serveur, §5.3),
  avec le `CollapsibleSection` du spectrogramme live à l'intérieur (§8.1), replié par défaut.
- `DailyActivityCalendar.svelte` — consomme `GET /sites/{site}/calendar?limit=0`, aucune troncature
  (la limite `0` = illimité est déjà le comportement natif de l'API BirdNET-Go sous-jacente, aucun
  plafond serveur codé en dur côté binaire).

### 8.3 Pages

`/dashboard` (sélecteur de site, en écoute en tête + calendrier sans limite, bloc détections
récentes **définitivement absent** du code — pas seulement désactivé), `/species` (liste par site +
univers France) et `/species/:id`, `/stats` (mêmes familles de graphes que BirdNET-Go, sur les
données proxiées/rejouées), `/system` (nœuds, règles, revue, transparence seuils dynamiques),
`/sites` (admin).

---

## 9. Génération des fiches espèces (368 espèces)

**Schéma JSON** (= la table `species_sheets`, §4) :
```json
{
  "scientific_name": "Erithacus rubecula",
  "common_name_fr": "Rougegorge familier",
  "taxonomy": {
    "class": "Aves", "order": "Passeriformes",
    "family": "Muscicapidae", "family_common_fr": null, "genus": "Erithacus"
  },
  "photo": {
    "url": "https://upload.wikimedia.org/…",
    "license": "CC BY-SA 4.0", "author": "…", "source": "wikipedia"
  },
  "wikipedia_url": "https://fr.wikipedia.org/wiki/Rougegorge_familier",
  "summary_fr": "≈150 mots, ton trivia, rédigé par l'agent",
  "habitat": "jardins, sous-bois, haies, parcs…",
  "diet": "insectivore, baies en hiver…",
  "activity_pattern": "diurne",
  "migration": {
    "hiverne": "…", "niche": "…", "passage": "…"
  },
  "rarity_note": "commun, présent toute l'année dans l'ouest de la France",
  "france_universe": {
    "max_score": 0.9996,
    "cities": {"Le Mans": 0.998, "Pornic": 0.994, "…": 0},
    "months": [1,2,3,4,5,6,7,8,9,10,11,12]
  },
  "generated_at": "2026-…",
  "generator_model": "claude-haiku-4.5",
  "reviewed_by_human": false,
  "sources": ["wikipedia:fr", "species_universe_fr.json", "GET /api/v2/species/taxonomy"]
}
```

**Sources** :
1. `species-data/species_universe_fr.json` (368 espèces, scores par ville × mois, déjà calculé) —
   copié tel quel dans `france_universe`, utilisé aussi comme **signal objectif de plausibilité**
   côté fiche (le « but explicite » demandé par Armand : « cet oiseau ne se trouve pas ici en été,
   c'est probablement une fausse détection ») et pour la **validation automatique** du brief généré
   (alerte si le texte dit « très rare en France » alors que `max_score` est élevé sur plusieurs
   villes).
2. Taxonomie + nom FR : appel **live**, une fois, à `GET /api/v2/species/taxonomy?scientific_name=&
   locale=fr` et `GET /api/v2/species/dictionary/fr` d'un nœud accessible — **jamais** en copiant le
   fichier `internal/classifier/data/genus_taxonomy.json` du dépôt Go (zone de licence différente,
   pas nécessaire de trancher cette ambiguïté : on consomme l'API déjà publiquement exposée par le
   binaire, on ne copie aucune donnée/code backend).
3. Wikipédia REST (`fr.wikipedia.org/api/rest_v1/page/summary/<Nom_scientifique>`) — déjà vérifié
   fonctionnel par Armand avant la conception (titre FR, extrait, `originalimage` HD — ex. 3564 px
   pour le Rougegorge, très supérieur aux 320×240 d'avicommons).

**Pipeline (amendé le 27/09/2026)** : deux étapes. (1) `species-data/build_base.py` (Python,
déterministe, sans IA) pré-remplit pour chaque espèce : nom FR (dictionnaire du nœud), taxonomie
(`GET /api/v2/species/taxonomy` du nœud), résumé + photo HD + licence/auteur (Wikipédia REST FR/EN +
API Commons `imageinfo/extmetadata`), `france_universe` → `species-data/base/<Nom_scientifique>.json`.
(2) Un sous-agent **Claude Haiku** par espèce, lancé depuis la session Claude Code (workflow), lit la
base pré-remplie et les pages Wikipédia, et écrit uniquement les champs rédactionnels →
`species-data/sheets/<Nom_scientifique>.json`. Le serveur charge ces fichiers au démarrage
(`species_sheets` = cache de ces JSON, source de vérité = les fichiers versionnés). L'endpoint
`POST /species/{name}/sheet/regenerate` (appel API Claude) est optionnel et tardif (clé API requise).
Chaque agent Haiku : lit l'extrait Wikipédia, complète si besoin par
une recherche web ciblée (habitat, régime, migration), reçoit `france_universe` comme fait établi
(jamais une supposition à inventer), rédige le brief structuré selon le schéma ci-dessus, cite au
moins la source Wikipédia.

**Validation** : passe automatique (champs requis non vides, `wikipedia_url` résolvable, cohérence
basique brief/`france_universe`) puis `reviewed_by_human = false` par défaut — badge « généré par
IA, à vérifier » dans l'UI plutôt qu'un fait établi, cohérent avec l'usage annoncé (aide au jugement,
pas vérité absolue). Armand peut relire/valider plus tard sans bloquer la publication.

**Stockage / mise à jour** : une ligne par espèce dans `species_sheets`. Génération unique pour les
368 espèces de l'univers ; génération à la demande pour toute espèce réellement détectée hors de cet
univers (cas rare) ; régénération manuelle (`POST /species/{name}/sheet/regenerate`) si Armand juge
une fiche fausse.

---

## 9bis. Statistiques long terme — décision et trajectoire

Armand a explicitement demandé : « pour l'instant reprendre globalement ce que propose BirdNET-Go,
jugé bien ». Deux options techniques existent pour honorer ça sans réimplémenter ~10 familles
d'agrégations SQL en Python (ce qu'une des conceptions écartées a fait, jugé disproportionné par les
trois juges) :

- **(a) Proxy live** vers les endpoints natifs du nœud (`/api/v2/analytics/*`, `/insights/*`,
  `dashboard/kpis` — confirmés fonctionnels en direct, `IsEnhancedDatabase()==true` vérifié par appel
  HTTP réel) : zéro code de réimplémentation, mais la page stats d'un site devient indisponible si ce
  site est hors ligne — alors que les détections brutes du même site sont déjà répliquées côté
  serveur (§4). C'est la faiblesse la plus nette relevée sur la conception gagnante par les trois
  juges.
- **(b) Instance BirdNET-Go « shadow » côté serveur** (greffe de B, corrigée pour ne jamais hériter
  du risque réseau de B) : une instance BirdNET-Go headless (confirmé : démarre sans source audio,
  `AudioPipelineService.Start` se contente d'un `Warn` si `Realtime.Audio.Sources` est vide) tourne
  en Docker sur le serveur, pointée sur **sa propre base MySQL dédiée**, alimentée **uniquement** par
  un job de rejeu asynchrone **après** ingestion réussie dans le SQLite du serveur (jamais sur
  l'écriture temps réel des nœuds — ce qui évite exactement le piège de B). Le `node_name` de cette
  base MySQL shadow est assigné par le **serveur** (le slug du site), donc garanti unique — aucune
  dépendance à la fragilité de `main.name` côté amont. Cette instance réexpose gratuitement tout le
  registre de charts existant, y compris pour des vues « toutes stations » agrégées.

**Décision retenue par défaut (amendée le 27/09/2026)** : **(a) pour le MVP** (S1, un seul site
toujours joignable localement) ; ensuite, **(c) réimplémentation progressive côté serveur, en SQL sur
la table `detections` déjà répliquée**, famille de graphes par famille de graphes (calendrier, KPIs,
distribution horaire, heatmap saisonnière, phénologie, top espèces, confiance) — ce que le serveur
sait déjà faire dès WP-05 pour le calendrier. L'option (b) « shadow BirdNET-Go » reste un plan de
secours documenté si (c) s'avère trop coûteuse, pas la trajectoire par défaut — c'est un lot de travail
dédié (WP tardif, voir `plan.md`), pas un blocage du démarrage. Si le rejeu (b) échoue ou prend du
retard, ça ne dégrade que la fraîcheur des stats, jamais l'intégrité des données (le SQLite serveur
reste la vérité, la shadow instance n'est qu'une vue dérivée, reconstructible).

---

## 10. Déploiement

### 10.1 S1 — aujourd'hui, sur le Mac, cohabitation stricte avec `local-test/`

- `local-test/` continue de tourner **sans aucune modification** (binaire, `config.yaml`,
  `start.sh`/`stop.sh` intouchés).
- Le **bridge** tourne en **process natif Python** (jamais Docker) — `output.sqlite` est en mode WAL,
  activement écrit par le binaire ; un bind-mount Docker/osxfs sur ce fichier ajoute un risque de
  lecture périmée sans bénéfice, alors qu'un accès fichier natif macOS est déjà éprouvé
  (`clip-retention.py` le fait en production depuis le 26/09 sans incident).
- Le **serveur** (FastAPI) tourne aussi en process natif (`uvicorn`) pour aller vite en S1 — pas de
  Docker Compose nécessaire tant qu'on est seul sur le Mac. Base SQLite dans `server/data/`.
- Le **frontend** tourne en `vite dev` pendant le développement ; un build statique (`vite build`)
  servi par FastAPI (`StaticFiles`) est introduit dès que le dashboard est présentable.
- **Aucune Tailscale, aucun secret réseau requis pour S1** — bridge et serveur communiquent en
  loopback (`http://localhost:8090`).

### 10.2 S2/S3 — Pi 5 + serveur séparé

- Chaque Pi 5 reçoit le binaire BirdNET-Go officiel **linux-arm64** du même tag (téléchargé depuis
  les releases upstream, jamais recompilé), les scripts `start.sh`/`stop.sh` adaptés (pas besoin du
  contournement CoreAudio macOS ; un équivalent générique de supervision micro est prévu, §13), et le
  **bridge** en service `systemd` natif (pas de Docker sur le Pi — un moving part de moins à
  maintenir chez un proche non technique).
- **Tailscale** installé sur chaque Pi (`curl -fsSL https://tailscale.com/install.sh | sh &&
  tailscale up --authkey=…`) — réservé au canal live (§6) et aux GET directs de clips (§3.2), **pas**
  au canal de données cœur (push HTTPS pur, §3.1).
- Le **serveur central** (VPS ou machine chez Armand) tourne en Docker Compose (FastAPI + son
  volume SQLite, plus tard la shadow instance MySQL+BirdNET-Go si §9bis-b est activé), derrière Caddy
  (HTTPS automatique Let's Encrypt) qui sert aussi le build Vite statique.

### 10.3 Sécurité

- `bridge_shared_secret` par nœud, hashé côté serveur (§7.4).
- Bearer token natif BirdNET-Go activé dès qu'un nœud rejoint le tailnet (§7.4), en plus du secret du
  bridge.
- `security.privatemode: true` sur tout nœud accessible via Tailscale (S2/S3) — reste `false` en S1
  (Mac local, pas d'exposition réseau).

### 10.4 Accès famille au dashboard

Login simple (session cookie FastAPI, pas d'OAuth) — un compte partagé unique par défaut (décision
ouverte, §« décisions pour Armand »). Le serveur peut être exposé en HTTPS public (nom de domaine +
Caddy) pour que la famille n'ait pas besoin d'installer Tailscale juste pour consulter le dashboard ;
l'ingestion nœud→serveur reste protégée séparément par le secret par nœud, indépendamment de ce
choix d'exposition du dashboard.

---

## 11. Migration des données existantes

Le Mans (archivé, `local-test/sauvegardes/lieu-1_le-mans_.../`, 878 détections, 42 espèces, clips
complets 1,3 Go) et Pornic (en cours, `local-test/data/`, ≥4373 détections) sont tous deux des bases
SQLite v2-only au même schéma. La migration réutilise **le même code d'ingestion** que la synchro
courante (`server/app/ingest/`), en mode « backfill » (démarre à `since_id=0`) :

- **Pornic** : un bridge de backfill pointe directement sur `local-test/data/birdnet.db`, en lecture
  seule, **pendant que le binaire continue de tourner** (sûr : mode WAL, lecteur externe déjà en
  production via `clip-retention.py`) ; un premier passage complet ramène tout l'historique, puis le
  service continue en mode incrémental normal — sans jamais interrompre `local-test/`.
- **Le Mans** : base arrêtée, aucun conflit d'accès. Le binaire n'étant pas en cours d'exécution pour
  cette base, le backfill ne peut pas appeler l'API HTTP pour les clips — il lit directement les
  fichiers `.wav`/`.png` sous `sauvegardes/lieu-1_.../clips/<clip_name>` pour alimenter `kept_clips`
  (mode « offline backfill » explicite dans `scripts/migrate_legacy_site.py`).
- Chaque backfill est explicitement rattaché au bon `site_id` par le choix du dossier/de la base
  source (jamais par les coordonnées lat/lon stockées par détection, qui portent une imprécision de
  géolocalisation documentée dans `CLAUDE.md` du projet pour la fenêtre du 25-26/09).

---

## 12. Plan par lots de travail

Détail complet, avec fichiers à créer, dépendances, tailles et critères de démonstration :
**voir `docs/plan.md`**. Vue d'ensemble en une page :

| Vague | Contenu | Sans matériel supplémentaire ni Tailscale |
|---|---|---|
| 1 — Fondations (S1, Mac) | Serveur squelette, bridge lecture seule, sync bout-en-bout, dashboard minimal visible | ✅ entièrement |
| 2 — Fonctionnalités cœur | Top-5 clips, fiche espèce, calendrier illimité, en écoute, pipeline fiches (368), stats proxy | ✅ entièrement |
| 3 — Système & pilotage | Règles par site, revue FP/FN, commandes, transparence seuils | ✅ entièrement (nœud local) |
| 4 — Multi-site réel | Tailscale, premier Pi distant, live audio, migration historique | Nécessite un Pi + Tailscale |
| 5 — Durcissement | Sécurité renforcée, shadow BirdNET-Go, sauvegardes, onboarding proches | Nécessite un 2ᵉ site réel |

---

## 13. Risques et inconnues

1. **Build linux-arm64 du tag `20260823` (ou tag proche)** : disponibilité non vérifiée dans cette
   synthèse. *Parade* : vérifier avant tout achat de Pi 5 ; à défaut, tag proche sur les nouveaux
   nœuds seulement (le Mac de référence reste sur `20260823`).
2. **Anti-rafale 15 s partagé par 6 canaux internes à BirdNET-Go** (`EventTracker`, `realtime.interval`
   par défaut) : ni la base SQLite du nœud, ni MQTT, ni le SSE natif n'ont la vérité brute de chaque
   inférence — deux détections de la même espèce à moins de 15 s d'écart ne produisent qu'une seule
   ligne, y compris en base. *Parade* : documenté, jamais promis un compte exact de vocalisations,
   seulement des événements dédupliqués — ceci vaut pour toute future fonctionnalité de comptage fin.
3. **Micro qui bascule silencieusement** (constaté sur macOS/CoreAudio, `mic-watchdog.sh` dédié) :
   équivalent sur Pi/ALSA non vérifié. *Parade* : supervision **générique** dès le premier lot système
   (dernière détection + niveau audio via `GET /api/v2/streams/audio-level`, un signal disponible sur
   toute plateforme), plutôt qu'un watchdog spécifique à CoreAudio à réécrire pour Linux.
4. **Fenêtre de rapatriement des clips trop courte** en cas de coupure Tailscale > 30 min (seuil de
   purge locale du nœud). *Parade* : perte occasionnelle acceptée (marge réelle souvent bien
   supérieure vu la cadence de push 20-30 s) ; augmenter `minclips`/`retention` côté nœud si le
   problème se matérialise en pratique.
5. **Charge d'exploitation** sur plusieurs années (sauvegardes, volumétrie). *Parade* : SQLite +
   `sqlite3 .backup`/copie de fichier en cron pour le serveur, rsync/restic pour les clips ;
   restauration testée avant tout déploiement chez un proche (lot dédié).
6. **Divergence de licence** si le frontend copié dérive trop de l'amont (CC BY-NC-SA 4.0). *Parade* :
   surface copiée limitée au générique (tokens CSS, `Modal`, `CollapsibleSection`, `image-utils.ts`,
   infra D3), couche données 100 % neuve, `NOTICE.md` + en-têtes vérifiés par test (§0.3).
7. **Fiches espèces générées par IA erronées.** *Parade* : source toujours citée, badge « généré, à
   vérifier », recoupement automatique avec `france_universe` plutôt qu'une confiance aveugle au
   texte libre.
8. **Instance BirdNET-Go headless « shadow » (§9bis-b)** : pas encore testée en pratique dans cette
   synthèse (confirmé seulement que le démarrage sans micro fonctionne). *Parade* : lot de travail
   dédié avec critère de démonstration explicite avant d'en dépendre pour la production.
9. **Bearer token + CSRF + secret bridge, trois mécanismes de sécurité côté nœud** : complexité réelle
   à maintenir. *Parade* : toute la logique vit dans une seule bibliothèque testée
   (`node/bridge/csrf_client.py` + client Bearer), jamais reconstruite ad hoc par endpoint.

---

## 14. Ce qui a été sciemment écarté, et pourquoi

- **Écrire directement dans `output.mysql` distant comme chemin d'écriture des détections** (c'était
  le cœur de la conception B, écartée) : confirmé par lecture de code — `CompositeAction` (Database +
  SSE + MQTT) n'a **aucun retry programmé** en cas d'échec (`getJobQueueRetryConfig` → `default:
  Enabled:false`), et le datastore est choisi une seule fois au démarrage, SQLite **ou** MySQL, jamais
  les deux (aucun repli local/dual-write). Une coupure réseau, même brève, sur un nœud chez un proche
  ferait perdre silencieusement et définitivement les détections de la période — exactement le
  scénario que le projet doit tolérer. Le nœud reste donc toujours l'autorité d'écriture locale ;
  seule la synchronisation est distante.
- **Recompiler/patcher BirdNET-Go** (colonne `site_id` native, endpoint « top-N » natif, redirection
  d'espèce native) : exclu par contrainte dure (Go absent du Mac, binaire figé).
- **`internal/backup` de BirdNET-Go** comme brique de synchro média : code mort côté application
  (`RegisterSource`/`RegisterTarget` jamais appelés en production), modèle « une archive tar par run »
  de toute façon inadapté à un flux continu de clips changeants.
- **MQTT ou le moteur d'alertes/webhook comme canal principal de synchronisation** : MQTT est soumis
  au **même** anti-rafale par espèce que l'écriture en base (même `EventTracker`, même fenêtre de
  15 s) — aucun gain de complétude, un broker en plus à déployer/sécuriser sur des sites NATés pour
  rien. Le webhook générique ne se déclenche par défaut que sur *nouvelle espèce*, pas par détection.
  Les deux restent disponibles plus tard comme canaux de notification complémentaires (Home Assistant,
  push téléphone), jamais comme source de vérité.
- **Redirection réelle des détections stockées** (réécrire `detections.label_id`, ou l'équivalent côté
  serveur) : rejeté — casserait la traçabilité et l'audit ; la redirection reste un remappage
  d'affichage uniquement (§7.6).
- **Garder le frontend BirdNET-Go tel quel avec un backend qui imite son contrat API** : figerait le
  serveur multi-sites sur des choix pensés pour un nœud unique (DTO différents entre `GET
  /detections`, `POST /search` et le SSE, sémantiques `verified` incohérentes selon l'endpoint, etc.)
  sans bénéfice réel sur un frontend neuf qui copie sélectivement le générique (§8).
- **Postgres dès le départ** : inutile à cette échelle (usage familial, quelques milliers de
  détections/mois multi-sites) ; SQLite + SQLAlchemy suffit et simplifie radicalement le déploiement
  S1 — une bascule reste possible plus tard sans réécriture (changement de chaîne de connexion).
- **Authentification OAuth (Google/GitHub)** côté serveur : hors scope pour un usage
  personnel/familial ; un login simple + session cookie suffisent.
