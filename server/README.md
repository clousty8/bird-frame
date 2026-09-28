# bird-frame — serveur

Serveur FastAPI : ingestion des nœuds (bridges BirdNET-Go), API navigateur (dashboard,
espèces, calendrier), fiches espèces, top-5 clips. Contrat d'API complet :
[`docs/api-contract.md`](../docs/api-contract.md). Architecture :
[`docs/architecture.md`](../docs/architecture.md).

## Démarrage rapide (S1, sur le Mac)

```bash
cd server
cp .env.example .env          # puis éditer BIRDFRAME_ADMIN_TOKEN au minimum
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8090
```

- `GET http://localhost:8090/health` → `{"status": "ok", "version": "..."}`.
- `GET http://localhost:8090/api/v1/species` → l'univers France (368 espèces, si
  `species-data/base/` est peuplé) + toute espèce détectée hors univers.

Les migrations Alembic sont appliquées **automatiquement au démarrage**
(`BIRDFRAME_AUTO_MIGRATE=1`, valeur par défaut) : pas d'étape séparée nécessaire pour
S1. Pour les piloter à la main (production, CI) :

```bash
uv run alembic upgrade head
```

## Variables d'environnement

Toutes préfixées `BIRDFRAME_`, lues depuis `server/.env` (voir `.env.example` pour la
liste complète et les valeurs par défaut — contrat §7.2). Les plus importantes :

| Variable | Rôle |
|---|---|
| `BIRDFRAME_ADMIN_TOKEN` | requis pour `POST /nodes/register` et `POST /admin/species-data/reload` (401 sinon) |
| `BIRDFRAME_ENV` | `dev` (défaut) ou `production` — voir « Authentification navigateur » ci-dessous |
| `BIRDFRAME_UI_PASSWORD_HASH` | hash du mot de passe de l'interface (`scripts/hash_password.py`) |
| `BIRDFRAME_SESSION_SECRET` | secret de signature des cookies de session (≥ 32 caractères) |
| `BIRDFRAME_PORT` | port d'écoute (défaut 8090) |
| `BIRDFRAME_DB_PATH` | base SQLite du serveur (défaut `data/bird-frame.db`, gitignoré) |
| `BIRDFRAME_DATA_DIR` | racine de `clips/` et `photos/` (défaut `data`) |
| `BIRDFRAME_SPECIES_DATA_DIR` | dossier `species-data/` (univers, `base/`, `sheets/`, `aliases.json`) — défaut `../species-data` |
| `BIRDFRAME_SOX_PATH` | exécutable `sox` pour les spectrogrammes (défaut `sox`, dans le `PATH`) |
| `BIRDFRAME_AUTO_MIGRATE` | `1` (défaut) = migrations Alembic appliquées au démarrage |

## Authentification navigateur (contrat §2.2)

**Lecture libre pour tout le monde ; mot de passe pour modifier et pour écouter les sons**
(les enregistrements peuvent contenir des voix privées). Un seul mot de passe, pas de comptes.

- Protégées (🔒, 401 `auth_required` sans session) : toute route navigateur non-GET (règles,
  revues, faux négatifs, réinitialisation des seuils) et `GET /recordings/{id}/audio`. Tout le
  reste (stats, photos, spectrogrammes, SSE…) est public. Ingestion (Bearer du nœud) et admin
  (`X-Admin-Token`) inchangées.
- Session : `POST /api/v1/auth/login {"password": …}` pose le cookie `bf_session` (HttpOnly,
  SameSite=Lax, 30 jours, `Secure` en https) ; `POST /api/v1/auth/logout` ; `GET /api/v1/auth/me`
  → `{"authenticated", "auth_enabled"}`.
- Anti-force brute : 5 échecs en 5 min pour une IP → 429 pendant 5 min. Mutations avec un en-tête
  `Origin` étranger → 403 `origin_mismatch`.
- Code : `app/browser_auth.py` (dépendances `require_browser_session` / `require_same_origin`),
  `app/passwords.py` (scrypt), `app/api/auth.py`. **Toute nouvelle route mutante ou qui sert de
  l'audio** prend `dependencies=[Depends(require_browser_session)]` ;
  `tests/test_route_protection.py` énumère toutes les routes et échoue sinon (une nouvelle route
  GET publique doit aussi y être ajoutée consciemment à `PUBLIC_GET_ROUTES`).

| `BIRDFRAME_ENV` | Hash | Secret | Comportement |
|---|---|---|---|
| `dev` (défaut) | absent | — | authentification **désactivée** (tout autorisé), WARNING au démarrage |
| `dev` | présent | absent | appliquée ; secret aléatoire par process (sessions perdues au redémarrage), WARNING |
| `dev` / `production` | présent | présent | appliquée normalement |
| `production` | absent | — | **refus de démarrer** (message explicite) |
| `production` | présent | absent | **refus de démarrer** (message explicite) |

Un hash mal formé ou un secret de moins de 32 caractères empêche le démarrage dans tous les modes.

Générer le hash (sans écho ; ou `--stdin` pour un script) et le secret :

```bash
uv run scripts/hash_password.py          # depuis la racine du dépôt ; demande le mot de passe 2 fois
printf '%s' "$MOT_DE_PASSE" | python3 scripts/hash_password.py --stdin
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # BIRDFRAME_SESSION_SECRET
```

Le hash (`scrypt$32768$8$1$<sel>$<hash>`) contient des `$` : tel quel dans `server/.env` et dans
les variables Railway, entre apostrophes dans un shell, `$$` dans un fichier docker-compose.
Changer le mot de passe ou `BIRDFRAME_SESSION_SECRET` déconnecte toutes les sessions.

Derrière un proxy (Railway) : lancer uvicorn avec `--proxy-headers --forwarded-allow-ips=…` pour
que l'IP client (anti-force brute) et le schéma https (attribut `Secure` du cookie) viennent de
`X-Forwarded-For` / `X-Forwarded-Proto`.

## Migrations (Alembic)

```bash
# Nouvelle révision après avoir modifié un modèle sous app/models/
uv run alembic revision --autogenerate -m "description courte"

# Appliquer / revenir en arrière
uv run alembic upgrade head
uv run alembic downgrade -1
```

`migrations/env.py` résout l'URL de connexion depuis `app/config.py`
(`BIRDFRAME_DB_PATH`) quand aucune URL n'est fournie explicitement — c'est ce que fait
`run_migrations()` (`app/main.py`) au démarrage, pour cibler la base de l'instance en
cours plutôt que celle du `.env` (utile aux tests, une base temporaire par test).

## Enregistrer un nœud

Fait par `scripts/register_node.py` (à la racine du dépôt), qui appelle
`POST /nodes/register` et écrit `node/config/<slug>.env` (lu ensuite par le bridge) :

```bash
uv run scripts/register_node.py \
  --slug pornic --site-name Pornic --node-name "Mac Armand — Pornic" \
  --lat 47.1155 --lon -2.1046 \
  --node-readonly   # obligatoire en S1 : le nœud visé (local-test/) ne doit jamais être muté
```

## Tests

```bash
uv run pytest -q
```

Chaque test construit sa propre application (`create_app()`, `app/main.py`) avec sa
propre base SQLite temporaire (migrée via Alembic, comme en production) et son propre
`species-data/` de test (`tests/fixtures/species-data/`, 2-3 espèces synthétiques —
jamais le vrai dossier `species-data/` du dépôt). `sox` est utilisé réellement dans les
tests de clips/spectrogramme (détecté via `PATH`, repli sur `/opt/homebrew/bin/sox`) :
s'il est absent, ces tests précis échoueront (pas de mock, conformément à la consigne
« sox mocké ou testé si présent »).

## Qualité

```bash
uv run ruff check app tests
```

## Système et statistiques (WP-12 à WP-15, ce lot)

En plus du cœur ci-dessus :

- **Règles espèce/site** (WP-12) : `GET`/`PUT`/`DELETE /sites/{slug}/species-rules[/{name}]`
  (`app/api/species_rules.py`). Un `PUT`/`DELETE` (a) écrit `species_site_rules`, (b)
  recalcule `detections.redirected_to_scientific_name` pour les détections déjà en base
  de ce (site, espèce) — `app/ingest/redirect_recompute.py` — et (c) crée les
  `node_commands` requises (algorithme §5.4 du contrat, `app/ingest/rule_commands.py`).
- **Revues et faux négatifs** (WP-13) : `POST`/`GET /sites/{slug}/reviews`,
  `POST`/`GET /sites/{slug}/false-negatives` (`app/api/reviews.py`). Une revue crée en
  best-effort une commande `mark_detection_reviewed` vers le nœud d'origine (jamais
  d'écriture directe dans les tables BirdNET-Go, cf. `architecture.md` §7.5) et
  redéclenche le calcul du top-5 clips (une revue `false_positive` évince, un `correct`
  qui l'annule peut faire redevenir candidat).
- **Seuils dynamiques** (WP-14) : `GET`/`DELETE /sites/{slug}/dynamic-thresholds[/{name}]`
  (`app/api/dynamic_thresholds.py`), miroir lecture seule du dernier heartbeat ; le
  `DELETE` met en file une commande `reset_dynamic_threshold` par nœud concerné.
- **Commandes** (reste de WP-11, complété ici) : `GET /nodes/{id}/commands` et
  `POST /nodes/{id}/commands/{cmd_id}/ack` côté bridge (Bearer), et
  `GET /sites/{slug}/commands` côté navigateur pour l'audit (`app/api/commands.py`).
- **Statistiques** (WP-15, version amendée : calculées sur la table `detections` du
  serveur, jamais un proxy vers le nœud) : `GET /sites/{slug}/stats/{kpis,daily,hourly,
  species,heatmap,confidence}` (`app/api/stats.py`). Vue **effective** partout (§1.7) :
  détections valides, espèce après redirection, règles `impossible` exclues.
- **Revue brute** : `GET /sites/{slug}/detections` (`app/api/detections.py`) — liste
  **sans** exclusion, avec revue courante, règle et prédictions par détection.

## Alias taxonomiques (`species-data/aliases.json`)

BirdNET-Go (binaire 20260823) enregistre la détection **primaire** sous le nom scientifique
actuel (table OpenFauna embarquée, `birdnet-go-ui/internal/openfauna/data/aliases.json`,
nom BirdNET v2.4 → nom eBird/Clements récent), mais les prédictions secondaires et la
liste de zone gardent l'ancien label — celui de l'univers et de `base/`. Exemple réel :
`Coloeus monedula` en base de Pornic, `Corvus monedula` partout ailleurs.
`species-data/aliases.json` contient donc l'inverse de cette table, restreint aux
espèces de l'univers (8 entrées au 27/09/2026 : Choucas des tours, Autour des palombes,
Martinet à ventre blanc, Héron garde-bœufs, Pluvier à collier interrompu, Pluvier petit-gravelot,
Pluvier guignard, Blongios nain). À régénérer si l'on met à jour BirdNET-Go.

- À l'ingestion, tout nom est canonicalisé ; une espèce détectée absente de l'univers et
  de `base/` est journalisée une fois (WARNING « espèce ingérée absente de l'univers ») :
  c'est le signal pour compléter le fichier.
- Le chargement refuse les chaînes (`A → B`, `B → C`) et signale un canonique inconnu.
- **Rattrapage des données déjà ingérées** (le contrat ne le prévoit pas dans
  `POST /admin/species-data/reload`) : serveur arrêté,
  ```bash
  uv run python scripts/recanonicalize.py --dry-run   # compte
  uv run python scripts/recanonicalize.py             # applique
  ```
  Renomme `detections` (nom brut conservé dans `raw_scientific_name`), `predictions`,
  `kept_clips`, règles, faux négatifs, cache `species_names`, puis recalcule redirections
  et top-5 des espèces touchées. Idempotent. Logique : `app/ingest/recanonicalize.py`.

## Ce qui n'est PAS dans ce lot

Volontairement hors périmètre (autres lots du plan, `docs/plan.md`) : live audio
(WP-19), migration historique Le Mans/Pornic (WP-17), Tailscale (WP-18), sécurité
renforcée (WP-20), instance BirdNET-Go « shadow » (WP-21).

## Décisions hors contrat

- **`node_commands.origin_batch` / `species_site_rules.last_command_batch`** (colonnes
  ajoutées, migration `eed8a20222f8`) : le contrat §6.20 demande que `GET
  /species-rules` retrouve « les commandes créées par le dernier PUT » d'une règle.
  Regrouper seulement par `created_at == updated_at` (précision à la seconde, imposée
  par le contrat §1.3) se casse dès que deux `PUT` de la même règle arrivent à moins
  d'une seconde d'écart (script, double-clic) : les deux lots de commandes fusionnent à
  tort. `origin_batch` est une clé opaque (uuid4) commune aux commandes d'un même appel ;
  `last_command_batch` retient celle du dernier `PUT` sur la règle. N'apparaît dans
  aucune réponse API, purement un détail d'implémentation serveur.
- **`GET /sites/{slug}/commands`** (route #40 de l'index du contrat) n'était assignée à
  aucun lot explicite du plan — logiquement du ressort système/commandes (ce lot), donc
  implémentée ici pour couvrir l'index de routes en entier.
