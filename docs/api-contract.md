# bird-frame — Contrat d'API (v1)

Statut : **contrat normatif** pour les trois équipes qui travaillent en parallèle sans se parler :
serveur FastAPI (`server/`), bridge Python (`node/`), frontend Svelte (`web/`). Couvre les vagues 1
à 3 de `docs/plan.md`. Rédigé le 27/09/2026 à partir de `docs/architecture.md` (y compris les
amendements du 27/09/2026) et d'une relecture du code BirdNET-Go (`birdnet-go-ui/`, tag `20260823`).

**Règle de préséance** : là où ce fichier et `architecture.md` divergent, **ce fichier fait foi**.
Les écarts voulus sont listés au §10. Tout ce qui n'est pas décrit ici est interdit par défaut :
pas de champ en plus dans une réponse sans mise à jour de ce fichier, pas de route en plus.

Mots-clés : **DOIT** = obligatoire ; **NE DOIT PAS** = interdit ; **PEUT** = optionnel, sans effet
sur les autres équipes.

---

## Sommaire

0. [Index des routes](#0-index-des-routes)
1. [Conventions générales](#1-conventions-générales)
2. [Authentification et CORS](#2-authentification-et-cors)
3. [Enregistrement d'un nœud et administration](#3-enregistrement-dun-nœud-et-administration)
4. [Ingestion bridge → serveur](#4-ingestion-bridge--serveur)
5. [Commandes serveur → nœud (`node_commands`)](#5-commandes-serveur--nœud-node_commands)
6. [API navigateur](#6-api-navigateur)
7. [Configuration (bridge, serveur, alias)](#7-configuration)
8. [Fichiers `species-data/` (base + fiches rédactionnelles)](#8-fichiers-species-data)
9. [Écarts de schéma SQL par rapport à `architecture.md` §4](#9-écarts-de-schéma-sql)
10. [Écarts voulus par rapport à `architecture.md` et hors périmètre](#10-écarts-voulus-et-hors-périmètre)
11. [Annexe : types TypeScript de référence](#11-annexe--types-typescript-de-référence)

---

## 0. Index des routes

Toutes les routes sont préfixées par **`/api/v1`**, sauf `/health`.

| # | Méthode | Route | Auth | Appelant | § |
|---|---|---|---|---|---|
| 1 | GET | `/health` (hors préfixe) | aucune | tous | 1.12 |
| 2 | POST | `/nodes/register` | `X-Admin-Token` | script admin | 3.1 |
| 3 | POST | `/admin/species-data/reload` | `X-Admin-Token` | Armand / script | 3.2 |
| 4 | POST | `/nodes/{node_id}/sync` | Bearer nœud | bridge | 4.2 |
| 5 | POST | `/nodes/{node_id}/clips/{node_local_id}` | Bearer nœud | bridge | 4.3 |
| 6 | POST | `/nodes/{node_id}/clips/{node_local_id}/missing` | Bearer nœud | bridge | 4.4 |
| 7 | POST | `/nodes/{node_id}/pending` | Bearer nœud | bridge | 4.5 |
| 8 | POST | `/nodes/{node_id}/heartbeat` | Bearer nœud | bridge | 4.6 |
| 9 | GET | `/nodes/{node_id}/commands` | Bearer nœud | bridge | 4.7 |
| 10 | POST | `/nodes/{node_id}/commands/{cmd_id}/ack` | Bearer nœud | bridge | 4.8 |
| 11 | GET | `/sites` | aucune (S1) | web | 6.2 |
| 12 | GET | `/nodes` | aucune (S1) | web | 6.2 |
| 13 | GET | `/sites/{slug}/now` | aucune (S1) | web | 6.3 |
| 14 | GET | `/sites/{slug}/pending/stream` (SSE) | aucune (S1) | web | 6.4 |
| 15 | GET | `/sites/{slug}/calendar` | aucune (S1) | web | 6.5 |
| 16 | GET | `/sites/{slug}/recent-detections` (transitoire WP-04) | aucune (S1) | web | 6.6 |
| 17 | GET | `/sites/{slug}/species` | aucune (S1) | web | 6.7 |
| 18 | GET | `/species` | aucune (S1) | web | 6.8 |
| 19 | GET | `/species/{scientific_name}` | aucune (S1) | web | 6.9 |
| 20 | GET | `/species/{scientific_name}/photo` | aucune (S1) | web | 6.10 |
| 21 | GET | `/species/{scientific_name}/sites/{slug}/top-clips` | aucune (S1) | web | 6.11 |
| 22 | GET | `/species/{scientific_name}/presence` | aucune (S1) | web | 6.12 |
| 23 | GET | `/recordings/{kept_clip_id}/audio` | aucune (S1) | web | 6.13 |
| 24 | GET | `/recordings/{kept_clip_id}/spectrogram` | aucune (S1) | web | 6.13 |
| 25 | GET | `/sites/{slug}/stats/kpis` | aucune (S1) | web | 6.14 |
| 26 | GET | `/sites/{slug}/stats/daily` | aucune (S1) | web | 6.15 |
| 27 | GET | `/sites/{slug}/stats/hourly` | aucune (S1) | web | 6.16 |
| 28 | GET | `/sites/{slug}/stats/species` | aucune (S1) | web | 6.17 |
| 29 | GET | `/sites/{slug}/stats/heatmap` | aucune (S1) | web | 6.18 |
| 30 | GET | `/sites/{slug}/stats/confidence` | aucune (S1) | web | 6.19 |
| 31 | GET | `/sites/{slug}/species-rules` | aucune (S1) | web | 6.20 |
| 32 | PUT | `/sites/{slug}/species-rules/{scientific_name}` | aucune (S1) | web | 6.21 |
| 33 | DELETE | `/sites/{slug}/species-rules/{scientific_name}` | aucune (S1) | web | 6.22 |
| 34 | GET | `/sites/{slug}/dynamic-thresholds` | aucune (S1) | web | 6.23 |
| 35 | DELETE | `/sites/{slug}/dynamic-thresholds/{scientific_name}` | aucune (S1) | web | 6.24 |
| 36 | POST | `/sites/{slug}/reviews` | aucune (S1) | web | 6.25 |
| 37 | GET | `/sites/{slug}/reviews` | aucune (S1) | web | 6.26 |
| 38 | POST | `/sites/{slug}/false-negatives` | aucune (S1) | web | 6.27 |
| 39 | GET | `/sites/{slug}/false-negatives` | aucune (S1) | web | 6.28 |
| 40 | GET | `/sites/{slug}/commands` | aucune (S1) | web | 6.29 |
| 41 | GET | `/sites/{slug}/detections` | aucune (S1) | web | 6.30 |

---

## 1. Conventions générales

### 1.1 Base, transport, versionnement

- Base : `http://<hôte>:<BIRDFRAME_PORT>/api/v1` (S1 : `http://localhost:8090/api/v1`).
- Toute évolution **incompatible** crée `/api/v2` ; les ajouts compatibles restent en v1 mais DOIVENT
  être ajoutés à ce fichier avant d'être codés.
- Requêtes et réponses JSON : `Content-Type: application/json`, **UTF-8**, sans BOM. Le serveur
  émet les caractères non ASCII tels quels (pas d'échappement `é`), en Unicode **NFC**.
- Exceptions au JSON : upload de clip (`multipart/form-data`, §4.3), médias (audio, PNG, JPEG),
  flux SSE (`text/event-stream`, §6.4).

### 1.2 Forme des objets JSON

- Noms de champs en **snake_case** partout (y compris côté bridge→serveur). Jamais de camelCase
  (le bridge convertit les champs BirdNET-Go `scientificName` → `scientific_name`, etc.).
- **Tout champ documenté est toujours présent** dans les réponses du serveur. Une valeur inconnue
  ou sans objet vaut **`null`**, jamais un champ absent. Les listes vides valent `[]`, jamais `null`,
  sauf mention contraire explicite (« liste ou `null` »).
- Dans les **corps de requête**, un champ marqué « optionnel » PEUT être absent ; absent ≡ `null`.
- Un champ inconnu dans un corps de requête est **ignoré** (pas d'erreur) — tolérance aux versions.
- Booléens : `true`/`false` JSON (jamais 0/1).
- Nombres : entiers JSON pour les compteurs/identifiants ; flottants pour confiances, seuils,
  scores, pourcentages.
- **Arrondis** (réponses navigateur uniquement) : confiances, seuils et scores arrondis à
  **4 décimales** ; `disk_free_pct` à 1 décimale ; `lat`/`lon` à 4 décimales. Les valeurs
  reçues à l'ingestion sont stockées telles quelles (non arrondies).

### 1.3 Dates et heures

| Forme | Format exact | Exemple | Usage |
|---|---|---|---|
| Instant UTC | `YYYY-MM-DDTHH:MM:SSZ` (secondes, **sans** fraction, suffixe `Z`) | `2026-09-27T14:39:01Z` | tout champ d'instant : `*_utc`, `*_at`, `generated_at`, `expires_at`… |
| Instant Unix | entier, secondes depuis l'époque | `1790519941` | champs `*_unix` (bloc « en écoute », relayés tels quels depuis BirdNET-Go) |
| Date locale | `YYYY-MM-DD` | `2026-09-27` | champs et paramètres `date`, `start`, `end`, `best_day.date`, `by_day[].date` |
| Heure locale | entier 0-23 | `16` | index des tableaux `hours` |

Règles :
- **Tout instant sérialisé en chaîne est en UTC avec `Z`**, quel que soit le nom du champ (le suffixe
  `_utc` est présent sur les champs de détection, mais `last_seen_at`, `created_at`, `generated_at`…
  suivent la même règle). Le serveur DOIT tronquer les fractions de seconde.
- En entrée, le serveur accepte aussi un décalage explicite (`+02:00`) et le convertit en UTC ;
  un instant **sans** fuseau est refusé (422).
- Le stockage SQLite des instants DOIT utiliser exactement ce format texte (comparaisons
  lexicographiques = chronologiques).

### 1.4 Fuseau du site, « journée » et « heure » locales

Chaque site a un fuseau IANA (`sites.timezone`, défaut `Europe/Paris`). **Toutes les agrégations
par jour, heure, mois, semaine ou année sont calculées dans le fuseau du site de la détection**,
jamais en UTC, jamais dans le fuseau du serveur ou du navigateur.

- **Journée locale D** = intervalle semi-ouvert `[D 00:00 local, D+1 00:00 local)` converti en UTC
  avec `zoneinfo.ZoneInfo(site.timezone)`. Elle dure 23 h ou 25 h les jours de changement d'heure.
- **Heure locale** d'une détection = heure « murale » (`0..23`) de `detected_at_utc` converti dans le
  fuseau du site. Jour de passage à l'heure d'hiver : l'heure 02:00-02:59 existe deux fois, les deux
  sont comptées dans l'index `2`. Jour de passage à l'heure d'été : l'index `2` vaut toujours `0`.
- **Mois local** = mois (1-12) de la date locale ; **année locale** idem.
- **Semaine (heatmap uniquement)** = `floor((jour_de_l_année_local − 1) / 7) + 1`, valeurs 1 à 53
  (la semaine 53 contient 1 ou 2 jours). **Ce n'est PAS la semaine ISO** : choix délibéré pour
  qu'une année civile = semaines 1..53 sans chevauchement.
- **« Aujourd'hui »** = date locale courante du site au moment de la requête.
- Paramètres `start`/`end` : dates locales **inclusives** des deux côtés.
- Recommandation d'implémentation serveur (fortement conseillée) : calculer à l'ingestion
  `detected_local_date` (TEXT `YYYY-MM-DD`) et `detected_local_hour` (INTEGER) et les stocker sur
  `detections` (§9), pour que tout `GROUP BY` reste du SQL pur. Si `sites.timezone` change, ces
  colonnes DOIVENT être recalculées pour le site.

### 1.5 Identifiants

| Identifiant | Type | Forme | Remarques |
|---|---|---|---|
| `slug` (site) | chaîne | `^[a-z0-9]+(?:-[a-z0-9]+)*$`, 2 à 40 caractères | identifiant de site **dans toutes les routes** (`/sites/{slug}/…`). Ex. `pornic`, `le-mans`. Immuable. |
| `site_id` | entier | ≥ 1 | interne ; exposé seulement par `/nodes/register` |
| `node_id` | entier | ≥ 1 | assigné par le serveur à l'enregistrement |
| `node_local_id` | entier | ≥ 1 | `detections.id` **côté BirdNET-Go** du nœud (= id de `/api/v2/detections/:id` du nœud) |
| `detection_id` | entier | ≥ 1 | `detections.id` **côté serveur**. Ne jamais confondre avec `node_local_id`. |
| `kept_clip_id` | entier | ≥ 1 | `kept_clips.id` serveur |
| `cmd_id` / `command_id` | entier | ≥ 1 | `node_commands.id` |
| `scientific_name` | chaîne | 1-200 caractères | identifiant d'espèce, voir §1.6 |

### 1.6 Noms d'espèces

**Identité** : une espèce est identifiée par son **nom scientifique canonique bird-frame** = le nom
utilisé dans `species-data/species_universe_fr.json` / `base/` / `sheets/` (ex.
`Erithacus rubecula`). Les étiquettes non taxonomiques de BirdNET (`Dog`, `Human vocal`, …) sont
traitées comme des « espèces » à part entière (elles apparaissent surtout dans les prédictions).

**Alias taxonomiques** : BirdNET-Go peut stocker un synonyme (constaté dans `birdnet.db` de Pornic :
`Coloeus monedula` alors que l'univers utilise `Corvus monedula`). Le serveur charge
`species-data/aliases.json` (§7.3) et DOIT **canonicaliser à l'ingestion** tout nom reçu (détection,
prédictions, bloc en écoute, seuils dynamiques) : `nom_canonique = aliases.get(nom_reçu, nom_reçu)`.
Le nom brut reçu est conservé pour audit (`detections.raw_scientific_name`, §9). Toutes les
réponses exposent le nom canonique. Les paramètres de route acceptent aussi un alias (résolu).

**Dans une URL** : le nom est encodé par pourcentage, espace = `%20`
(`encodeURIComponent` côté web, `urllib.parse.quote(name, safe="")` côté serveur). Exemple :
`/api/v1/species/Erithacus%20rubecula`. Le serveur accepte aussi `_` à la place de l'espace
(`Erithacus_rubecula`) et compare **sans tenir compte de la casse** ; il répond toujours avec la
forme canonique (`Erithacus rubecula`). Les URLs que le serveur génère (`photo_url`, `audio_url`…)
utilisent toujours `%20`.

**Nom français `common_name_fr`** (chaîne ou `null`), résolu par le serveur dans cet ordre :
1. `species-data/base/<Nom>.json` → `common_name_fr` ;
2. `species_universe_fr.json` → `commonName` ;
3. cache de noms alimenté par le bridge (champ `common_name` des payloads d'ingestion, issu du
   dictionnaire du nœud `GET /api/v2/species/dictionary/fr`) ;
4. sinon `null` — **le frontend affiche alors `scientific_name`**.

**`photo_url`** (chaîne ou `null`) = `/api/v1/species/{nom encodé}/photo?size=320` si la base de
l'espèce contient une photo (`photo.url_1600` ou `photo.url_original` non nul), sinon `null`. Le
frontend construit la variante HD en remplaçant `size=320` par `size=1600`.

**`has_sheet`** (booléen) = une fiche rédactionnelle valide `species-data/sheets/<Nom>.json` est
chargée (§8.3).

### 1.7 Vues de données : détection valide, vue effective, vue par espèce

Ces trois définitions s'appliquent à **toutes** les routes navigateur ; chaque route précise laquelle
elle utilise.

- **Revue courante** d'une détection = la revue (`reviews`) d'`id` le plus grand pour cette détection,
  ou aucune.
- **Détection valide** = détection dont la revue courante n'est **pas** `false_positive`.
- **Vue par espèce** = détections valides, regroupées par `scientific_name` (canonique, brut de
  redirection). Utilisée par : `/sites/{slug}/species`, `/species`, `/species/{name}`,
  `/species/{name}/presence`, top-5 clips.
- **Vue effective** = détections valides, espèce **effective** =
  `COALESCE(redirected_to_scientific_name, scientific_name)`, **en excluant** les détections dont
  l'espèce effective porte une règle `impossible` sur le site. Utilisée par : `/now` (`recent`),
  événement SSE `detection`, `/calendar`, `/recent-detections`, les 6 routes `/stats/*`.
- `/sites/{slug}/detections` (revue) montre **toutes** les détections, avec leurs indicateurs
  (`review`, `rule`, espèce effective) — aucune exclusion.

Conséquences : une règle `redirect` X→Y fait compter les détections de X pour Y dans la vue
effective (calendrier, stats) mais la fiche de X garde ses propres compteurs et clips. Une règle
`impossible` masque rétroactivement l'espèce des vues effectives (les données restent en base).

### 1.8 Erreurs

Toute réponse d'erreur (4xx, 5xx) a le corps JSON :
```json
{
  "error": "site_not_found",
  "message": "Aucun site avec le slug « rennes ».",
  "details": null
}
```

| Champ | Type | Null ? | Description |
|---|---|---|---|
| `error` | chaîne | non | code machine stable (catalogue ci-dessous), snake_case |
| `message` | chaîne | non | explication lisible, en français, non destinée au parsing |
| `details` | objet, tableau ou `null` | oui | informations structurées (ex. liste des erreurs de validation, `synced_up_to_id`) |

Le serveur DOIT remplacer les formats d'erreur par défaut de FastAPI/Starlette
(`{"detail": …}`) par ce format, y compris pour les 404 de route inconnue, les 405 et les 422 de
validation Pydantic. Pour `validation_error`, `details` est un tableau
`[{"loc": ["body", "rule"], "msg": "…", "type": "…"}]` (repris des erreurs Pydantic).

**Codes HTTP utilisés** :

| Code | Sens dans ce contrat |
|---|---|
| 200 | succès avec corps |
| 201 | ressource créée (enregistrement de nœud, revue, faux négatif, clip stocké) |
| 202 | accepté, effet asynchrone via `node_commands` (reset de seuil dynamique) |
| 204 | succès sans corps (`pending`) |
| 206 | contenu partiel (requête `Range` sur l'audio) |
| 400 | requête bien formée mais incohérente (`invalid_range` : `start > end`) |
| 401 | authentification absente ou invalide (secret de nœud, jeton admin) |
| 403 | authentifié mais interdit (`node_decommissioned`) |
| 404 | ressource inconnue |
| 405 | méthode non autorisée sur une route existante (`method_not_allowed`) |
| 409 | conflit avec l'état serveur (curseur, base du nœud réinitialisée, clip plus voulu, commande déjà finalisée, chaîne de redirection) |
| 413 | corps trop gros (`payload_too_large` : upload > 25 Mo) |
| 416 | plage `Range` non satisfaisable (audio) |
| 422 | validation du corps, des paramètres de requête ou de chemin |
| 500 | erreur interne (`internal_error`) |
| 502 | échec d'un service amont (téléchargement photo Wikimedia) |

**Catalogue des codes `error`** :

| `error` | HTTP | Où |
|---|---|---|
| `validation_error` | 422 | partout (corps, query, path) |
| `batch_too_large` | 422 | sync : plus de 200 détections |
| `clip_name_mismatch` | 422 | upload : `clip_name` différent de celui ingéré |
| `invalid_audio` | 422 | upload : fichier vide ou en-tête non reconnu |
| `invalid_range` | 400 | stats : `start > end` |
| `unauthorized` | 401 | ingestion : en-tête `Authorization` absent, mal formé ou secret faux |
| `invalid_admin_token` | 401 | routes admin |
| `node_decommissioned` | 403 | ingestion : nœud mis hors service |
| `not_found` | 404 | route inconnue |
| `site_not_found` | 404 | `{slug}` inconnu |
| `node_not_found` | 404 | `{node_id}` inconnu |
| `species_not_found` | 404 | espèce inconnue partout (§6.9) |
| `detection_not_found` | 404 | détection inconnue (ou d'un autre site/nœud) |
| `recording_not_found` | 404 | clip évincé, manquant ou pas encore reçu |
| `spectrogram_not_found` | 404 | PNG absent |
| `photo_not_found` | 404 | espèce sans photo |
| `rule_not_found` | 404 | DELETE d'une règle inexistante |
| `command_not_found` | 404 | ack d'une commande inconnue ou d'un autre nœud |
| `threshold_not_found` | 404 | reset d'un seuil dynamique absent du dernier heartbeat |
| `method_not_allowed` | 405 | — |
| `cursor_ahead` | 409 | sync : `since_id` > curseur serveur |
| `node_db_reset` | 409 | sync : la base du nœud est repartie à zéro |
| `clip_not_wanted` | 409 | upload : clip hors top-5 |
| `command_already_final` | 409 | ack contradictoire |
| `redirect_chain` | 409 | règle `redirect` créant une chaîne |
| `payload_too_large` | 413 | upload |
| `range_not_satisfiable` | 416 | audio |
| `photo_upstream_error` | 502 | photo |
| `internal_error` | 500 | — |

### 1.9 Pagination

Routes paginées : `/species`, `/sites/{slug}/detections`, `/sites/{slug}/reviews`,
`/sites/{slug}/false-negatives`, `/sites/{slug}/commands`.

- Paramètres : `limit` (entier ≥ 1, défaut et maximum propres à chaque route) et `offset` (entier
  ≥ 0, défaut 0). `limit` au-delà du maximum → 422.
- Réponse : objet contenant le tableau sous un **nom de ressource au pluriel** plus
  `total` (nombre total d'éléments correspondant aux filtres, avant pagination), `limit` et `offset`
  effectivement appliqués :
```
{ "detections": [ … ], "total": 4627, "limit": 50, "offset": 0 }
```
- Les routes non paginées renvoient aussi un objet avec un tableau nommé (`{"sites": […]}`), sans
  `total`/`limit`/`offset`. Jamais de tableau JSON nu en racine.

### 1.10 URLs de médias dans les réponses

Les URLs générées par le serveur (`photo_url`, `audio_url`, `spectrogram_url`, `photo.url`…) sont des
**chemins absolus sans hôte** commençant par `/api/v1/`. Le frontend les résout contre l'origine de
l'API (en dev, même origine grâce au proxy Vite, §2.3).

### 1.11 Requêtes invalides courantes

- `{slug}` inexistant → 404 `site_not_found` (vérifié **avant** toute autre validation métier).
- Paramètre `date`/`start`/`end` mal formé → 422 ; `start > end` → 400 `invalid_range`.
- `min_confidence`, `threshold_override` hors de leurs bornes → 422.

### 1.12 Santé

`GET /health` (hors `/api/v1`, sans auth) → `200 {"status": "ok", "version": "0.1.0"}`
(`version` = version du serveur, chaîne).

---

## 2. Authentification et CORS

### 2.1 Ingestion (bridge → serveur)

- En-tête **`Authorization: Bearer <bridge_shared_secret>`** sur **toutes** les routes
  `/nodes/{node_id}/…` (sauf `/nodes/register`, §3.1).
- Le secret est propre au nœud. Le serveur stocke `SHA-256(secret)` en hexadécimal minuscule
  (`nodes.bridge_shared_secret_hash`) et compare avec `hmac.compare_digest` au hash du nœud
  **désigné par `{node_id}` dans le chemin** (un secret valide pour un autre nœud est un secret faux).
- Ordre des vérifications et réponses :
  1. `{node_id}` inexistant → **404 `node_not_found`** ;
  2. en-tête absent, schéma différent de `Bearer`, ou secret faux → **401 `unauthorized`** avec
     l'en-tête de réponse `WWW-Authenticate: Bearer` ;
  3. nœud avec `decommissioned_at` non nul → **403 `node_decommissioned`** ;
  4. puis validation du corps (422) et logique métier.
- Toute requête d'ingestion **authentifiée avec succès** (quel que soit le code métier ensuite)
  met à jour `node_status.last_seen_at = maintenant`.

### 2.2 Navigateur

- **S1 : aucune authentification** sur les routes navigateur (§6). Le serveur écoute sur
  `127.0.0.1` par défaut. Une session famille (`/auth/*`) viendra plus tard (§10.2) ; le frontend
  DOIT centraliser ses appels dans `web/src/lib/api/` pour pouvoir ajouter les cookies ensuite.
- Aucun cookie n'est émis en S1.

### 2.3 CORS et proxy de développement

- Serveur : middleware CORS avec `allow_origins` = `BIRDFRAME_CORS_ORIGINS` (défaut
  `http://localhost:5173,http://127.0.0.1:5173`), `allow_methods` = `GET, POST, PUT, DELETE, OPTIONS`,
  `allow_headers` = `Content-Type, Range, Authorization, X-Admin-Token`, `expose_headers` =
  `Content-Range, Accept-Ranges, Content-Length`, `allow_credentials = false`.
- Frontend : base d'API `import.meta.env.VITE_API_BASE ?? "/api/v1"` ; `vite.config.ts` DOIT
  proxifier `/api` vers `http://localhost:8090` en dev (même origine → pas de souci CORS pour SSE et
  `Range`). Le CORS serveur reste configuré pour un accès direct.

---

## 3. Enregistrement d'un nœud et administration

Les routes admin exigent l'en-tête **`X-Admin-Token: <BIRDFRAME_ADMIN_TOKEN>`** (comparaison en temps
constant). En-tête absent, faux, ou `BIRDFRAME_ADMIN_TOKEN` vide/non défini côté serveur →
**401 `invalid_admin_token`** (la route est donc inutilisable tant que le jeton n'est pas configuré).

### 3.1 `POST /nodes/register`

Crée (si besoin) le site, crée le nœud, génère son secret. Normalement appelée une seule fois par
`scripts/register_node.py`.

Corps :
```json
{
  "site_slug": "pornic",
  "site_name": "Pornic",
  "node_name": "Mac Armand — Pornic",
  "timezone": "Europe/Paris",
  "lat": 47.1155,
  "lon": -2.1046
}
```

| Champ | Type | Requis | Contraintes |
|---|---|---|---|
| `site_slug` | chaîne | oui | format §1.5 |
| `site_name` | chaîne | oui | 1-100 caractères |
| `node_name` | chaîne | oui | 1-100 caractères, libellé humain |
| `timezone` | chaîne | oui | nom IANA reconnu par `zoneinfo` (sinon 422) |
| `lat` | flottant ou `null` | oui (peut être `null`) | −90 ≤ lat ≤ 90 |
| `lon` | flottant ou `null` | oui (peut être `null`) | −180 ≤ lon ≤ 180 |

Comportement :
- Si aucun site n'a ce `site_slug` → création du site avec `site_name`, `timezone`, `lat`, `lon`.
- Si le site existe déjà → le nœud y est rattaché ; `site_name`, `timezone`, `lat`, `lon` du corps
  sont **ignorés** (le site n'est pas modifié) et `site_created` vaut `false`.
- Création du nœud, `node_sync_state.last_synced_detection_id = 0`, `node_status` vide.
- Secret = `secrets.token_urlsafe(32)` (43 caractères URL-safe). Seul son SHA-256 est stocké. **Le
  secret en clair n'est renvoyé qu'ici, une seule fois.**
- Le serveur met en file, pour ce nœud, la commande `set_main_name` `{"name": "<site_slug>"}` (§5.3) — **sauf** si le corps contient `"auto_main_name": false` (champ optionnel, défaut `true`), utilisé en S1 pour ne jamais faire réécrire `local-test/config.yaml` par BirdNET-Go (voir `BRIDGE_NODE_READONLY`, §7.1).

Réponse **201** :
```json
{
  "node_id": 1,
  "site_id": 1,
  "site_slug": "pornic",
  "site_created": true,
  "bridge_shared_secret": "Q2h0cX0l3S6mJv9s1q0yJpS6o0q8W7dM3xk1b2c3d4e"
}
```

| Champ | Type | Null ? | Description |
|---|---|---|---|
| `node_id` | entier | non | à écrire dans `BRIDGE_NODE_ID` |
| `site_id` | entier | non | id interne du site |
| `site_slug` | chaîne | non | rappel |
| `site_created` | booléen | non | `false` si le site existait |
| `bridge_shared_secret` | chaîne | non | à écrire dans `BRIDGE_SECRET` (fichier en mode 600) |

Erreurs : 401 `invalid_admin_token`, 422 `validation_error`.

### 3.2 `POST /admin/species-data/reload`

Relit `BIRDFRAME_SPECIES_DATA_DIR` (univers, `base/`, `sheets/`, `aliases.json`) sans redémarrer le
serveur (utile pendant que les agents Haiku produisent les fiches). Corps vide. Réponse **200** :
```json
{
  "universe_count": 368,
  "base_count": 92,
  "sheet_count": 40,
  "alias_count": 1,
  "invalid_files": [
    {"file": "sheets/Parus_major.json", "error": "summary_fr : 64 mots (minimum 80)"}
  ],
  "loaded_at": "2026-09-27T15:02:11Z"
}
```
`invalid_files` : fichiers ignorés (tableau d'objets `{file, error}`, chemins relatifs à
`species-data/`). Le même rapport est journalisé au démarrage.

---

## 4. Ingestion bridge → serveur

### 4.1 Vue d'ensemble des boucles du bridge

Le bridge tourne en process natif à côté de BirdNET-Go et fait tourner **quatre boucles
indépendantes** (une panne de l'une ne bloque pas les autres) :

| Boucle | Cadence | Routes serveur | Routes BirdNET-Go locales |
|---|---|---|---|
| Synchro détections + clips | `BRIDGE_SYNC_INTERVAL_S` (20 s) ; immédiatement à nouveau si le lot était plein | `POST /sync`, `POST /clips/{id}`, `POST /clips/{id}/missing` | aucune (lecture `birdnet.db` en `mode=ro` + fichiers de `BRIDGE_CLIPS_DIR`) |
| Relais « en écoute » | événementiel (SSE local) + renvoi du dernier état toutes les 30 s | `POST /pending` | `GET /api/v2/detections/stream` |
| Heartbeat | `BRIDGE_HEARTBEAT_INTERVAL_S` (60 s) | `POST /heartbeat` | `GET /api/v2/app/config`, `GET /api/v2/dynamic-thresholds` |
| Commandes | `BRIDGE_COMMANDS_INTERVAL_S` (30 s), `BRIDGE_COMMANDS_FAST_INTERVAL_S` (3 s) pendant une session live active et pendant 120 s après la réception d'une commande | `GET /commands`, `POST /commands/{id}/ack` | voir §5 |

Démarrage du bridge : lire la config (§7.1), vérifier que `birdnet.db` s'ouvre en lecture seule, puis
lancer les quatre boucles. La boucle de commandes démarre **en premier** (la commande `set_main_name`
en file depuis l'enregistrement doit pouvoir s'exécuter).

**Réaction du bridge aux erreurs HTTP du serveur (toutes routes d'ingestion)** :

| Réponse | Action du bridge |
|---|---|
| 2xx | succès |
| erreur réseau, timeout (10 s), 5xx | réessai avec backoff exponentiel : base 5 s, ×2, plafond 300 s, jitter ±25 % ; remise à zéro au premier succès |
| 401, 403, 404 `node_not_found` | configuration invalide : journal niveau ERROR, **pas de backoff exponentiel**, nouvel essai toutes les 300 s, boucle sinon en pause |
| 409 | traitement spécifique à chaque route (ci-dessous) |
| 413, 422 | bug de payload : journal ERROR avec le corps de réponse, l'élément fautif est abandonné (pas de réessai en boucle) |

### 4.2 `POST /nodes/{node_id}/sync`

Pousse un lot de détections confirmées + leurs prédictions secondaires.

**Construction du lot par le bridge** (requêtes de `architecture.md` §3.1, `ORDER BY p.confidence
DESC`, jamais `rank`) :
- `since_id` = curseur courant (dernière valeur `synced_up_to_id` reçue, ou fichier d'état, ou 0) ;
- `SELECT … WHERE d.id > :since_id ORDER BY d.id ASC LIMIT :BRIDGE_BATCH_SIZE` (≤ 200) ;
- `node_max_id` = `SELECT COALESCE(MAX(id), 0) FROM detections` ;
- le bridge appelle `/sync` **à chaque cycle, même avec un lot vide** (récupère `want_clips` et
  `commands`, prouve la vie du lien).

Corps :
```json
{
  "since_id": 4511,
  "node_max_id": 4627,
  "detections": [
    {
      "node_local_id": 4512,
      "detected_at_utc": "2026-09-27T13:30:12Z",
      "scientific_name": "Erithacus rubecula",
      "common_name": "Rougegorge familier",
      "confidence": 0.98,
      "source_id": 1,
      "source_display_name": "Sound Card 1",
      "clip_name": "2026/09/erithacus_rubecula_98p_20260927T133012Z.wav",
      "has_clip": true,
      "predictions": [
        {"scientific_name": "Turdus merula", "common_name": "Merle noir", "confidence": 0.0207},
        {"scientific_name": "Human vocal", "common_name": null, "confidence": 0.0118}
      ]
    }
  ]
}
```

| Champ | Type | Requis | Null ? | Description |
|---|---|---|---|---|
| `since_id` | entier ≥ 0 | oui | non | borne exclusive utilisée pour la requête du lot (`id > since_id`) |
| `node_max_id` | entier ≥ 0 | oui | non | `MAX(detections.id)` de `birdnet.db` au moment du lot |
| `detections` | tableau | oui | non | 0 à 200 éléments, triés par `node_local_id` croissant |
| `detections[].node_local_id` | entier ≥ 1 | oui | non | `detections.id` du nœud |
| `detections[].detected_at_utc` | chaîne instant | oui | non | `detections.detected_at` (entier Unix en base BirdNET-Go) converti en UTC `Z` |
| `detections[].scientific_name` | chaîne 1-200 | oui | non | `labels.scientific_name` de `detections.label_id` (nom brut du nœud) |
| `detections[].common_name` | chaîne | oui | oui | nom FR du dictionnaire du nœud, `null` si inconnu |
| `detections[].confidence` | flottant [0,1] | oui | non | `detections.confidence` |
| `detections[].source_id` | entier | oui | oui | `detections.source_id` (id entier de `audio_sources`, informatif) |
| `detections[].source_display_name` | chaîne | oui | oui | `audio_sources.display_name` |
| `detections[].clip_name` | chaîne | oui | oui | `detections.clip_name` tel quel (relatif à `BRIDGE_CLIPS_DIR`), `null` si vide |
| `detections[].has_clip` | booléen | oui | non | `true` ssi `clip_name` non vide **et** (le fichier `<BRIDGE_CLIPS_DIR>/<clip_name>` existe **ou** la détection a moins de 120 s — fichier possiblement en cours d'écriture) |
| `detections[].predictions` | tableau | oui | non | 0 à 20 prédictions **secondaires uniquement** (`detection_predictions`), triées confiance décroissante. La prédiction primaire n'y figure **jamais** (le bridge retire toute ligne dont le nom = celui de la détection) |
| `predictions[].scientific_name` | chaîne 1-200 | oui | non | nom brut du nœud |
| `predictions[].common_name` | chaîne | oui | oui | nom FR du dictionnaire du nœud |
| `predictions[].confidence` | flottant [0,1] | oui | non | — |

Validation : corps non conforme (pas d'objet, `detections` absent, > 200 éléments →
`batch_too_large`) → 422, **rien n'est inséré**. En revanche, un **élément** invalide (ex. confiance
> 1) ne fait pas échouer le lot : il est listé dans `rejected` et le curseur avance quand même par-
dessus (sinon une seule ligne corrompue bloquerait la synchro pour toujours). Le serveur valide donc
les éléments un par un.

**Algorithme serveur** (transaction unique) :
1. Soit `L = node_sync_state.last_synced_detection_id`.
2. Si `node_max_id < L` → **409 `node_db_reset`**, `details: {"synced_up_to_id": L, "node_max_id":
   <reçu>}` ; rien n'est inséré. (La base BirdNET-Go du nœud a été remplacée — ex. bascule de lieu :
   il faut enregistrer un nouveau nœud, §3.1.)
3. Si `since_id > L` → **409 `cursor_ahead`**, `details: {"synced_up_to_id": L}` ; rien n'est inséré.
   (Cas d'un serveur restauré depuis une sauvegarde plus ancienne : le serveur redemande depuis `L`.)
4. Pour chaque élément valide : canonicaliser les noms (§1.6), calculer `redirected_to_scientific_name`
   selon la règle `redirect` du site, `detected_local_date`/`hour`, puis
   `INSERT … ON CONFLICT(node_id, node_local_id) DO NOTHING`. Inséré → `accepted` ; conflit →
   `duplicates` (le contenu existant n'est **jamais** modifié : première écriture gagnante).
   Prédictions insérées seulement pour les détections nouvellement acceptées. Les `common_name`
   reçus alimentent le cache de noms (§1.6, niveau 3).
5. `L' = max(L, max(node_local_id du lot, éléments rejetés compris))` si le lot est non vide, sinon
   `L' = L`. Écrire `L'` et `last_sync_at`.
6. Top-5 clips (§4.3.1) pour chaque détection acceptée avec `has_clip = true`.
7. Diffuser un événement SSE `detection` (§6.4) pour chaque détection acceptée, valide dans la vue
   effective, et dont `detected_at_utc` date de moins de 15 minutes (pas d'inondation pendant un
   rattrapage historique).

Réponse **200** :
```json
{
  "accepted": 1,
  "duplicates": 0,
  "rejected": [],
  "synced_up_to_id": 4512,
  "want_clips": [4512, 4388],
  "commands": [
    {
      "id": 88,
      "kind": "set_species_threshold",
      "payload": {"scientific_name": "Larus argentatus", "aliases": [], "threshold": 0.4},
      "created_at": "2026-09-27T13:29:50Z",
      "expires_at": null
    }
  ]
}
```

| Champ | Type | Null ? | Description |
|---|---|---|---|
| `accepted` | entier | non | détections nouvellement insérées |
| `duplicates` | entier | non | détections déjà connues (rejeu idempotent, **jamais une erreur**) |
| `rejected` | tableau de `{node_local_id: entier, error: chaîne}` | non | éléments invalides ignorés (le curseur passe quand même) |
| `synced_up_to_id` | entier | non | **valeur canonique du curseur**. Le bridge DOIT l'adopter comme nouveau curseur, même si elle diffère de son fichier local, et l'écrire dans `BRIDGE_STATE_FILE` |
| `want_clips` | tableau d'entiers | non | `node_local_id` dont le serveur veut l'audio : **toutes** les entrées top-5 actives de ce nœud encore sans fichier (pas seulement celles du lot), triées rang croissant, 50 au maximum |
| `commands` | tableau de `Command` (§4.7) | non | commandes en attente pour ce nœud, même sémantique de livraison que `GET /commands` (bonus opportuniste) |

**Réaction du bridge** :
- 200 : adopter `synced_up_to_id` ; traiter `want_clips` (§4.3) **séquentiellement, avant le cycle
  suivant** ; transmettre `commands` à l'exécuteur de commandes (§5.1, déduplication par `id`) ; si le
  lot était plein (200), relancer un cycle immédiatement.
- 409 `cursor_ahead` : adopter `details.synced_up_to_id` comme curseur, relancer immédiatement.
- 409 `node_db_reset` : journal CRITICAL, **arrêter la boucle de synchro** (intervention humaine).

### 4.3 `POST /nodes/{node_id}/clips/{node_local_id}`

Upload d'un clip demandé dans `want_clips`.

Requête `multipart/form-data`, deux parties :

| Partie | Type | Requis | Description |
|---|---|---|---|
| `audio` | fichier | oui | octets bruts du fichier `<BRIDGE_CLIPS_DIR>/<clip_name>` ; `filename` = nom de base du fichier ; `Content-Type` de la partie : `audio/wav` (`.wav`), `audio/flac`, `audio/mpeg` (`.mp3`), `audio/mp4` (`.m4a`/`.aac`), `audio/ogg` (`.opus`) |
| `clip_name` | texte | oui | `detections.clip_name` du nœud pour cette détection |

Le bridge obtient `clip_name` par `SELECT clip_name FROM detections WHERE id = :node_local_id`.
S1 : BirdNET-Go exporte en WAV (`realtime.audio.export.type: wav`) ; les autres formats sont acceptés
pour un futur nœud configuré autrement.

Validation serveur : taille ≤ 25 Mo (sinon **413 `payload_too_large`**) ; fichier non vide et
en-tête cohérent avec l'extension (`RIFF…WAVE` pour `.wav`), sinon **422 `invalid_audio`** ;
`clip_name` égal à celui ingéré pour la détection, sinon **422 `clip_name_mismatch`**.

Comportement :
- détection `(node_id, node_local_id)` inconnue → **404 `detection_not_found`** ;
- détection hors du top-5 actif (évincée entre-temps, ou jamais retenue) → **409 `clip_not_wanted`**
  — le bridge considère la demande comme close (pas de réessai) ;
- déjà stocké → **200**, `already_stored: true`, fichier existant conservé (idempotent) ;
- sinon : écrire `<BIRDFRAME_DATA_DIR>/clips/<site_slug>/<Genre_espece>/<kept_clip_id>.<ext>`,
  générer le spectrogramme PNG à côté (`<kept_clip_id>.png`, §6.13), remplir
  `kept_clips.audio_path`, `spectrogram_path`, `fetched_at` → **201**.

Réponse **201** (ou 200) :
```json
{
  "kept_clip_id": 88,
  "detection_id": 1523,
  "rank": 2,
  "already_stored": false,
  "spectrogram_generated": true
}
```
`spectrogram_generated` = `false` si `sox` a échoué (le clip audio reste servi ; journal WARNING).

#### 4.3.1 Top-5 serveur (comportement observable)

- Candidats pour `(site, espèce)` (vue par espèce) : détections **valides** avec `has_clip = true`
  dont le clip n'a pas été signalé manquant.
- Top-5 = les 5 meilleurs candidats par `confidence` décroissante, puis `detected_at_utc`
  décroissant, puis `detection_id` décroissant. Rangs `1..5` recompactés à chaque changement.
- Entrée d'un candidat → ligne `kept_clips` (audio absent) ⇒ apparaît dans `want_clips` du nœud
  d'origine. Sortie (6ᵉ, ou détection passée en `false_positive`) → `evicted_at` posé, **fichiers
  serveur supprimés** (jamais ceux du nœud). Une détection évincée qui redevient top-5 (après un faux
  positif) est redemandée via `want_clips`.

### 4.4 `POST /nodes/{node_id}/clips/{node_local_id}/missing`

Le fichier n'existe plus sur le nœud (purgé par la rétention locale) ou `clip_name` est vide.

Corps :
```json
{ "clip_name": "2026/09/erithacus_rubecula_98p_20260927T133012Z.wav", "reason": "not_found" }
```

| Champ | Type | Requis | Null ? | Valeurs |
|---|---|---|---|---|
| `clip_name` | chaîne | oui | oui | nom demandé (`null` si la détection n'a pas de `clip_name`) |
| `reason` | chaîne | oui | non | `not_found` (fichier absent), `unreadable` (erreur d'E/S), `no_clip_name` |

Comportement : `kept_clips.missing = 1`, `fetched_at = NULL` ; le rang est libéré et le candidat
suivant entre dans le top-5 (il apparaîtra dans un prochain `want_clips`). Idempotent.
Réponse **200** : `{"status": "marked_missing"}`, ou `{"status": "ignored"}` si la détection n'était
pas dans le top-5 actif. 404 `detection_not_found` si la détection est inconnue.

### 4.5 `POST /nodes/{node_id}/pending`

Relais du bloc « en écoute ». **Vérifié dans le code BirdNET-Go** : l'événement SSE `pending` de
`GET /api/v2/detections/stream` porte un **instantané complet** (tableau de toutes les espèces
visibles en cours d'écoute), émis uniquement quand il change
(`internal/analysis/processor/pending_broadcast.go:176-199`, envoi `internal/api/v2/sse/sse.go:361`) ;
chaque élément est un `SSEPendingDetection` (`pending_broadcast.go:35-48`) **sans champ de confiance**.
Les éléments terminés (`approved`/`rejected`) figurent dans **un seul** instantané puis disparaissent
(`processor.go:1800-1810`).

Le bridge envoie donc l'instantané entier, à chaque événement `pending` local, et renvoie le dernier
instantané connu toutes les 30 s. Si l'abonnement SSE local tombe, il envoie un instantané vide
(`items: []`) puis se reconnecte (backoff §4.1).

Corps :
```json
{
  "snapshot_at_unix": 1790519945,
  "items": [
    {
      "scientific_name": "Erithacus rubecula",
      "common_name": "Rougegorge familier",
      "status": "active",
      "hit_count": 3,
      "confidence_hint": null,
      "first_detected_unix": 1790519938,
      "last_updated_unix": 1790519944,
      "source_id": "audio_card_881db84a"
    }
  ]
}
```

| Champ | Type | Requis | Null ? | Source BirdNET-Go |
|---|---|---|---|---|
| `snapshot_at_unix` | entier | oui | non | horloge du bridge à la réception de l'événement |
| `items` | tableau | oui | non | 0 à 50 éléments, dans l'ordre reçu |
| `items[].scientific_name` | chaîne | oui | non | `scientificName` |
| `items[].common_name` | chaîne | oui | oui | `species` (nom commun, locale du nœud) |
| `items[].status` | chaîne | oui | non | `status` ∈ `active`, `approved`, `rejected` |
| `items[].hit_count` | entier ≥ 0 | oui | non | `hitCount` |
| `items[].confidence_hint` | flottant [0,1] | oui | oui | max des `modelContributions[].maxConfidence` si présent, sinon `null` (**presque toujours `null`** avec un seul modèle : BirdNET-Go n'expose pas de confiance dans ce flux) |
| `items[].first_detected_unix` | entier | oui | non | `firstDetected` |
| `items[].last_updated_unix` | entier | oui | non | `lastUpdated` |
| `items[].source_id` | chaîne | oui | oui | `sourceID` (id de source du registre audio, ex. `audio_card_881db84a`) |

Le champ `thumbnail` de BirdNET-Go (URL relative au nœud) n'est **pas** relayé.

Comportement serveur : remplace intégralement l'état « en écoute » de ce nœud (en mémoire suffit),
horodaté à la réception ; recalcule la liste du site et diffuse `pending` (§6.4) si elle a changé.
Réponse **204** sans corps.

**Expiration côté serveur** (appliquée à chaque calcul de la liste d'un site, réévaluée toutes les
5 s ; un événement SSE `pending` est émis si le résultat change) :
- tous les éléments d'un nœud hors ligne (§6.1, `online = false`) sont retirés ;
- un élément `approved` ou `rejected` est retiré 20 s après la réception de son instantané ;
- un élément `active` dont `last_updated_unix < maintenant − 90` est retiré.

### 4.6 `POST /nodes/{node_id}/heartbeat`

Corps :
```json
{
  "sent_at_utc": "2026-09-27T14:40:00Z",
  "bridge_version": "0.1.0",
  "birdnet_go_version": "20260823",
  "birdnet_go_reachable": true,
  "birdnet_go_pid_alive": true,
  "mic_device_name": "HyperX QuadCast 2",
  "mic_healthy": true,
  "disk_free_pct": 62.4,
  "node_db_max_id": 4627,
  "dynamic_thresholds_snapshot": [
    {
      "species_name": "accenteur mouchet",
      "scientific_name": "Prunella modularis",
      "level": 3,
      "current_value": 0.2,
      "base_threshold": 0.6,
      "high_conf_count": 19,
      "trigger_count": 19,
      "is_active": true,
      "expires_at_utc": "2026-09-28T14:26:19Z",
      "last_triggered_utc": "2026-09-27T14:39:38Z",
      "first_created_utc": "2026-09-27T14:39:38Z"
    }
  ]
}
```

| Champ | Type | Requis | Null ? | Description / source |
|---|---|---|---|---|
| `sent_at_utc` | instant | oui | non | horloge du bridge (le serveur peut détecter une dérive) |
| `bridge_version` | chaîne | oui | non | version du paquet `node/` |
| `birdnet_go_version` | chaîne | oui | oui | champ `version` de `GET /api/v2/app/config` (`internal/api/v2/app/app.go:36`), `null` si injoignable |
| `birdnet_go_reachable` | booléen | oui | non | `GET /api/v2/app/config` a répondu 200 en < 5 s |
| `birdnet_go_pid_alive` | booléen | oui | oui | PID lu dans `BRIDGE_BIRDNET_PID_FILE` vivant ; `null` si pas de fichier configuré |
| `mic_device_name` | chaîne | oui | oui | micro effectivement capturé si déterminable (S1 macOS : `local-test/tools/mic-status <PID>`, cf. `CLAUDE.md` — ne jamais se fier à `audio.log`), sinon `null` |
| `mic_healthy` | booléen | oui | oui | `true` = micro attendu capturé ; `false` = anomalie détectée ; `null` = inconnu |
| `disk_free_pct` | flottant [0,100] | oui | oui | espace libre du volume de `BRIDGE_CLIPS_DIR` |
| `node_db_max_id` | entier ≥ 0 | oui | non | `MAX(detections.id)` de `birdnet.db` |
| `dynamic_thresholds_snapshot` | tableau ou `null` | oui | oui | `null` = lecture impossible ; `[]` = aucun seuil. Toutes les pages de `GET /api/v2/dynamic-thresholds?limit=250&offset=…` (`dynamicthresholds.go:51`, réponse `{data,total,limit,offset}` `:175-180`, champs `:61-73`) |
| `…[].species_name` | chaîne | oui | non | `speciesName` (clé du nœud = **nom commun en minuscules**, ex. `accenteur mouchet`) |
| `…[].scientific_name` | chaîne | oui | non | `scientificName` |
| `…[].level` | entier 0-3 | oui | non | `level` |
| `…[].current_value` | flottant | oui | non | `currentValue` |
| `…[].base_threshold` | flottant | oui | non | `baseThreshold` |
| `…[].high_conf_count` | entier | oui | non | `highConfCount` |
| `…[].trigger_count` | entier | oui | non | `triggerCount` |
| `…[].is_active` | booléen | oui | non | `isActive` |
| `…[].expires_at_utc` | instant | oui | oui | `expiresAt` converti en UTC |
| `…[].last_triggered_utc` | instant | oui | oui | `lastTriggered` (instant Go zéro `0001-01-01…` → `null`) |
| `…[].first_created_utc` | instant | oui | oui | `firstCreated` (zéro → `null`) |

Comportement serveur : met à jour `node_status` (tous les champs, `last_heartbeat_at`), remplace
`dynamic_thresholds_snapshot_json` (canonicalisation des noms §1.6) et
`dynamic_thresholds_snapshot_at = maintenant` — sauf si le champ vaut `null`, auquel cas l'instantané
précédent est conservé. Réponse **200** :
```json
{ "server_time_utc": "2026-09-27T14:40:00Z" }
```

### 4.7 `GET /nodes/{node_id}/commands`

Paramètre : `limit` (1-50, défaut 20).

Sémantique de livraison (au moins une fois) :
- sont renvoyées, par `id` croissant : les commandes `pending` non expirées, et les commandes
  `delivered` depuis plus de 120 s sans ack (redélivrance) ;
- à la livraison : `status = 'delivered'`, `delivered_at = maintenant` ;
- une commande dont `expires_at` est dépassé n'est jamais livrée : elle passe en `expired`.

Réponse **200** :
```json
{
  "commands": [
    {
      "id": 89,
      "kind": "start_live",
      "payload": {"session_id": "3f0e6a52-2c1b-4d7e-9a57-0c6f1e8b9d21", "source_id": null},
      "created_at": "2026-09-27T14:41:02Z",
      "expires_at": "2026-09-27T14:42:02Z"
    }
  ]
}
```

Objet **`Command`** (livraison au bridge) :

| Champ | Type | Null ? | Description |
|---|---|---|---|
| `id` | entier | non | `node_commands.id` |
| `kind` | chaîne | non | §5.2 |
| `payload` | objet | non | forme exacte par `kind`, §5.3 |
| `created_at` | instant | non | — |
| `expires_at` | instant | oui | au-delà, ne pas exécuter (le bridge vérifie aussi, avec son horloge) |

### 4.8 `POST /nodes/{node_id}/commands/{cmd_id}/ack`

Corps :
```json
{
  "status": "applied",
  "result": {"stream_token": "…", "playlist_url": "/api/v2/streams/hls/t/…/playlist.m3u8"},
  "error": null
}
```

| Champ | Type | Requis | Null ? | Description |
|---|---|---|---|---|
| `status` | chaîne | oui | non | `applied` ou `failed` |
| `result` | objet | oui | oui | résultat propre au `kind` (§5.3), `null` si rien à dire |
| `error` | chaîne ≤ 2000 | oui | oui | message d'erreur ; **requis non nul si `status = failed`** (sinon 422) |

Règles :
- Le bridge N'ACQUITTE `failed` que pour les **échecs permanents** (réponse 4xx de BirdNET-Go,
  validation, espèce/source introuvable). Pour un échec **transitoire** (BirdNET-Go injoignable,
  timeout, 5xx), il **n'acquitte pas** : le serveur redélivrera après 120 s.
- Transitions : `pending|delivered → applied|failed`. Un ack identique à l'état final déjà enregistré
  → 200 (idempotent). Un ack différent d'un état final (`applied`, `failed`, `expired`) → **409
  `command_already_final`**. Commande inconnue ou d'un autre nœud → **404 `command_not_found`**.
- Effets serveur : `applied_at` (ou `error_message`) renseigné, `result` stocké (`result_json`, §9) ;
  pour `mark_detection_reviewed` appliqué : `reviews.synced_to_node_at = maintenant`.

Réponse **200** : `{"id": 89, "status": "applied"}`.

---

## 5. Commandes serveur → nœud (`node_commands`)

### 5.1 Principes

- Le serveur **ne parle jamais** en mutation à l'API BirdNET-Go d'un nœud. Il écrit une ligne
  `node_commands` ; le bridge la récupère (§4.7, ou `commands` du sync §4.2), l'exécute **localement**
  contre `BRIDGE_NODE_API` (`http://localhost:8080`), puis l'acquitte (§4.8).
- **Toutes les commandes sont idempotentes** par construction (ajout seulement si absent, retrait
  seulement si présent, écriture d'une valeur cible). Une redélivrance est donc sans danger.
- Le bridge exécute les commandes **une par une, par `id` croissant** (l'ordre compte pour les
  changements de règle), et garde en mémoire les `id` exécutés depuis 30 min pour ignorer les
  doublons reçus par les deux canaux (poll et sync).
- Commande expirée (`expires_at` dépassé à la réception, horloge du bridge) : **ne pas exécuter**,
  acquitter `failed` avec `error = "expired"`.

**Cycle CSRF local** (bibliothèque unique `node/bridge/csrf_client.py`) — vérifié dans le code :
1. `GET {BRIDGE_NODE_API}/api/v2/app/config` → corps JSON avec `csrfToken`
   (`internal/api/v2/app/app.go:22,34`) et cookie `csrf` (`internal/api/middleware/csrf.go:22`).
2. Toute requête mutante (`POST`, `PUT`, `PATCH`, `DELETE`) envoie l'en-tête `X-CSRF-Token: <token>`
   (`csrf.go:224`) **et** le cookie `csrf` (même `httpx.Client`, cookies conservés).
3. Sur réponse 403 : rafraîchir le jeton (étape 1) et rejouer **une** fois.
4. Si `BRIDGE_NODE_API_TOKEN` est non vide (S2+), ajouter `Authorization: Bearer <token>` à **toutes**
   les requêtes vers BirdNET-Go. En S1, la sécurité BirdNET-Go est désactivée : les routes protégées
   par `AuthMiddleware` passent sans jeton.
5. Les `POST` sous `/api/v2/streams/` **ne sont pas** exemptés de CSRF (seules les méthodes sûres le
   sont : `csrf.go:143-169`).

### 5.2 Énumération des `kind`

| `kind` | Déclencheur serveur | Expire |
|---|---|---|
| `set_species_threshold` | règle `present` avec seuil ; retrait d'un seuil | non |
| `exclude_species` | règle `impossible` | non |
| `unexclude_species` | sortie d'une règle `impossible` | non |
| `include_species` | règle `present` | non |
| `uninclude_species` | sortie d'une règle `present` | non |
| `reset_dynamic_threshold` | `DELETE /sites/{slug}/dynamic-thresholds/{name}` | non |
| `set_main_name` | `POST /nodes/register` | non |
| `mark_detection_reviewed` | `POST /sites/{slug}/reviews` | non |
| `start_live` | (vague 4) démarrage du live | 60 s |
| `live_heartbeat` | (vague 4) maintien du live | 30 s |
| `stop_live` | (vague 4) arrêt du live | 60 s |

Statuts : `pending` → `delivered` → `applied` | `failed` ; `pending`/`delivered` → `expired`.

**Champ commun `aliases`** : pour les commandes portant sur une espèce, `aliases` (tableau de chaînes,
éventuellement vide) = tous les noms de `aliases.json` qui pointent vers `scientific_name`. Le bridge
applique l'opération **au nom et à chacun de ses alias** (BirdNET-Go peut stocker l'un ou l'autre).

### 5.3 Payloads exacts et exécution locale par le bridge

Rappels de sémantique BirdNET-Go utilisés ci-dessous (vérifiés) :
- `GET /api/v2/settings/:section` renvoie la section brute (`settings.go:82`, réponse `:198`) ;
  `GET /api/v2/settings/species` → `{"include": [...], "exclude": [...], "config": {...} | null}`
  (`conf/config.go:917-921`) ; section `species` = `Realtime.Species` (`settings.go:1065-1066`).
- `PATCH /api/v2/settings/:section` (`settings.go:87`, handler `:474-625`) **fusionne** :
  les objets JSON sont fusionnés clé par clé (`deepMergeMaps`, `settings.go:741-769`), **les
  tableaux sont remplacés en entier** (valeur source recopiée, `:763-765`). Donc : pour modifier
  `include`/`exclude`, envoyer **la liste complète** ; pour `config`, envoyer seulement l'entrée
  visée. Une entrée de `config` **ne peut pas être supprimée** par PATCH (fusion, et `null` sur une
  valeur struct est un no-op). Réponse 200 :
  `{"message", "skippedFields", "restart_required", "restart_reasons"}` (`settings.go:619-624`).
- Clés de `config` normalisées en minuscules (`settings.go:973-1011`) ; recherche par nom commun en
  minuscules **puis** nom scientifique en minuscules **puis** alias canonique
  (`processor/species_config_lookup.go:26-56`). Seuil validé dans [0,1] (`settings.go:1625-1646`).
- **Danger** : une entrée `config` présente avec `threshold: 0` fixe le seuil à 0 (tout passe) —
  `getBaseConfidenceThreshold` renvoie `config.Threshold` dès que l'entrée existe
  (`processor.go:1340-1355`). Ne **jamais** écrire `threshold: 0` pour « retirer » un seuil.
- `PUT /api/v2/settings` (`settings.go:84`) remplace les champs de type map **en entier**
  (`mergeFullSettings`, `settings.go:771-813`) : c'est la seule façon de supprimer une clé de
  `config` ; c'est aussi ce que fait l'UI native (`frontend/src/lib/utils/settingsApi.ts:53-60` :
  GET complet puis PUT complet). Les secrets masqués au GET sont restaurés au PUT.
- `include` et les clés de `config` sont des inclusions forcées pour le filtre de zone
  (`classifier/range_filter.go:303-322`) ; `exclude` est canonicalisé en noms scientifiques
  (`settings.go:554-556`).
- Ne **pas** utiliser `POST /api/v2/detections/ignore` : c'est une bascule, non idempotente
  (`detections/detections.go:1588-1605`).

Comparaisons de noms dans les listes BirdNET-Go : **insensibles à la casse**. Ordre des listes
préservé, ajouts en fin.

#### `set_species_threshold`

```json
{"scientific_name": "Larus argentatus", "aliases": [], "threshold": 0.4}
```

| Champ | Type | Null ? | Contraintes |
|---|---|---|---|
| `scientific_name` | chaîne | non | nom canonique |
| `aliases` | tableau de chaînes | non | voir §5.2 |
| `threshold` | flottant | **oui** | 0.01 ≤ t ≤ 1.0 ; **`null` = retirer le seuil personnalisé** |

Exécution :
- `threshold` non nul : `PATCH /api/v2/settings/species` avec
  `{"config": {"larus argentatus": {"threshold": 0.4}}}` — une clé par nom (nom + alias), en
  **minuscules**. La fusion conserve `interval`/`actions` existants de l'entrée. Si `config` contient
  déjà une clé égale au **nom commun FR** de l'espèce (dictionnaire du nœud, en minuscules, ex.
  `goéland argenté`), cette clé est **aussi** mise à jour : BirdNET-Go la consulte avant la clé
  scientifique (`species_config_lookup.go:31-37`) et elle masquerait sinon la nôtre.
- `threshold` nul : `GET /api/v2/settings` (objet complet), supprimer de
  `realtime.species.config` toutes les clés égales (insensible à la casse) au nom, à un alias ou au
  nom commun FR de l'espèce ; si aucune n'existait → no-op ; sinon `PUT /api/v2/settings` avec
  l'objet complet modifié.
- `result` : `{"changed": true, "keys": ["larus argentatus"], "restart_required": false}`
  (`changed = false` pour un no-op ; `restart_required` repris de la réponse BirdNET-Go, `false` si
  no-op).

#### `exclude_species` / `unexclude_species` / `include_species` / `uninclude_species`

```json
{"scientific_name": "Columba livia", "aliases": []}
```

Exécution (même schéma pour les quatre, sur la liste `exclude` ou `include`) :
1. `GET /api/v2/settings/species` ;
2. calculer la nouvelle liste : `exclude_species`/`include_species` → ajouter chaque nom absent ;
   `unexclude_species`/`uninclude_species` → retirer toute entrée égale (insensible à la casse) au nom
   ou à un alias ;
3. si inchangée → no-op ; sinon `PATCH /api/v2/settings/species` avec **uniquement** la liste
   complète concernée : `{"exclude": [ … ]}` ou `{"include": [ … ]}`.
- `result` : `{"changed": true, "list": "exclude", "restart_required": false}`.
- Vérification possible (non obligatoire) : `GET /api/v2/detections/ignored`
  (`detections/handler.go:159`) liste les espèces exclues.

#### `reset_dynamic_threshold`

```json
{"scientific_name": "Prunella modularis", "aliases": []}
```

Le seuil dynamique est indexé côté BirdNET-Go par le **nom commun en minuscules**
(`processor.go:984-987`, reset `dynamic_threshold.go:352-364`), pas par le nom scientifique.
Exécution :
1. `GET /api/v2/dynamic-thresholds?limit=250&offset=0` (paginer jusqu'à `total`) ;
2. sélectionner les entrées dont `scientificName` égale (insensible à la casse) le nom ou un alias ;
3. pour chacune : `DELETE /api/v2/dynamic-thresholds/{PathEscape(speciesName)}`
   (`dynamicthresholds.go:57`, handler `:394-415`, réponse `{"success": true, …}`).
- Aucune entrée trouvée → `applied` avec `result: {"reset": []}`.
- `result` : `{"reset": ["accenteur mouchet"]}`.

#### `set_main_name`

```json
{"name": "pornic"}
```
`name` : 1-100 caractères (`settings.go:37`, `validateMainSection` `:1505-1520`).
Exécution : `PATCH /api/v2/settings/main` avec `{"name": "pornic"}` (section `main`,
`settings.go:1051-1052` ; champ `main.name`, `conf/config.go:1845-1848`), puis
`GET /api/v2/settings/main` et vérifier `name`. Égalité → `applied`, `result: {"name": "pornic"}` ;
sinon `failed`. Hygiène seulement : le rattachement de site côté serveur ne dépend jamais de
`main.name`. En S1, cette commande modifie `local-test/config.yaml` **via l'API BirdNET-Go** (écriture
faite par le binaire lui-même, conforme à `architecture.md` §7.3).

#### `mark_detection_reviewed`

```json
{"node_local_id": 4627, "verified": "false_positive", "comment": "c'était un pic"}
```

| Champ | Type | Null ? | Valeurs |
|---|---|---|---|
| `node_local_id` | entier | non | id de la détection sur le nœud |
| `verified` | chaîne | non | `correct` ou `false_positive` |
| `comment` | chaîne | oui | note de la revue, ≤ 1000 caractères |

Exécution : `POST /api/v2/detections/{node_local_id}/review` avec
`{"verified": "<verified>"}` plus `"comment": "<comment>"` si non nul (`detections/handler.go:156`,
corps `DetectionRequest` `detections.go:201-207`, handler `:1447-1531`). Réponses BirdNET-Go : 404
(détection supprimée du nœud) et **409** (détection verrouillée, `detections.go:112-130`) → `failed`
(permanent). `result` : `null`. Ne **jamais** écrire directement dans `detection_reviews`.

#### `start_live` (vague 4, format figé dès maintenant)

```json
{"session_id": "3f0e6a52-2c1b-4d7e-9a57-0c6f1e8b9d21", "source_id": null}
```

| Champ | Type | Null ? | Description |
|---|---|---|---|
| `session_id` | chaîne | non | **UUID v4** (BirdNET-Go n'utilise `session_id` comme identité client que s'il parse comme UUID : `audio/audio_hls.go:1069-1077`) |
| `source_id` | chaîne | oui | id de source du registre audio (ex. `audio_card_881db84a`) ; `null` = première source de `GET /api/v2/system/audio/sources` (`audio/audio_devices.go:37`, réponse `{"sources": [{id,name,type,state}]}`, `audio_sources.go:13-23`) |

Exécution : `POST /api/v2/streams/hls/{PathEscape(source_id)}/start` avec
`{"session_id": "<uuid>"}` (`audio_hls.go:248-255,279`, handler `:369-438`, corps
`HLSSessionRequest` `:182-184`) → réponse `HLSStreamStatus` (`:171-179`, construite `:495-541`). Le bridge démarre ensuite
son propre heartbeat : `POST /api/v2/streams/hls/heartbeat` avec
`{"stream_token": "<token>", "session_id": "<uuid>"}` toutes les **20 s** (`:283`, handler `:617-650` ;
nettoyage après 5 min d'inactivité, grâce de 30 s au démarrage : `:45-48`). Session terminée
automatiquement si aucun `live_heartbeat` n'est reçu pendant 60 s (→ même action que `stop_live`).
`result` :
```json
{
  "source_id": "audio_card_881db84a",
  "stream_token": "Zq3…",
  "playlist_url": "/api/v2/streams/hls/t/Zq3…/playlist.m3u8",
  "status": "ready",
  "playlist_ready": true,
  "stream_epoch_utc": "2026-09-27T14:41:05Z"
}
```
(`playlist_url` tel que renvoyé par BirdNET-Go, relatif au nœud ; `stream_epoch_utc` = `stream_epoch`
converti, `null` si absent.)

#### `live_heartbeat`

`{"session_id": "<uuid>"}` — repousse de 60 s l'échéance de la session locale. Session inconnue →
`failed`, `error = "unknown_session"`. `result` : `null`.

#### `stop_live`

`{"session_id": "<uuid>"}` — arrête le heartbeat local puis
`POST /api/v2/streams/hls/{source_id}/stop` avec `{"session_id": "<uuid>"}` (`audio_hls.go:280`,
handler `:584-613`, réponse `{"status": "stopped"}`). Session déjà terminée → `applied` (idempotent).

### 5.4 Règles d'espèce → commandes (algorithme serveur)

État cible du nœud pour une règle : `D(present)` = `{inclus: oui, exclu: non, seuil:
threshold_override}` ; `D(impossible)` = `{inclus: non, exclu: oui, seuil: null}` ;
`D(redirect)` = `D(aucune règle)` = `{inclus: non, exclu: non, seuil: null}` (la redirection est un
remappage d'affichage serveur uniquement, aucun mécanisme natif).

Sur `PUT` ou `DELETE` d'une règle, pour **chaque nœud non décommissionné du site**, avec
`A = D(ancienne)` et `N = D(nouvelle)`, le serveur crée dans cet ordre :
1. `unexclude_species` si `A.exclu` et non `N.exclu` ;
2. `uninclude_species` si `A.inclus` et non `N.inclus` ;
3. `set_species_threshold` (`threshold = N.seuil`) si `A.seuil ≠ N.seuil` ;
4. `include_species` si `N.inclus` et non `A.inclus` ;
5. `exclude_species` si `N.exclu` et non `A.exclu`.

Si `A = N` (ré-enregistrement à l'identique), le serveur ré-émet l'application complète de `N`
(`include_species` + `set_species_threshold` si seuil non nul pour `present` ; `exclude_species` pour
`impossible` ; rien pour `redirect`) — ce qui sert de bouton « réessayer » après un `failed`.
Les commandes créées portent l'origine de la règle (`origin_type = 'species_rule'`, §9).

---

## 6. API navigateur

### 6.1 Objets partagés

#### `NodeStatus`

```json
{
  "node_id": 1,
  "node_name": "Mac Armand — Pornic",
  "site_slug": "pornic",
  "site_name": "Pornic",
  "online": true,
  "last_seen_at": "2026-09-27T14:40:12Z",
  "last_sync_at": "2026-09-27T14:40:05Z",
  "last_heartbeat_at": "2026-09-27T14:40:00Z",
  "last_detection_at": "2026-09-27T14:39:01Z",
  "mic_device_name": "HyperX QuadCast 2",
  "mic_healthy": true,
  "disk_free_pct": 62.4,
  "birdnet_go_reachable": true,
  "birdnet_go_pid_alive": true,
  "birdnet_go_version": "20260823",
  "bridge_version": "0.1.0",
  "synced_up_to_id": 4627,
  "node_db_max_id": 4627,
  "sync_lag": 0,
  "decommissioned_at": null
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `node_id` | entier | non | — |
| `node_name` | chaîne | non | `nodes.name` |
| `site_slug`, `site_name` | chaîne | non | site du nœud |
| `online` | booléen | non | `last_seen_at` non nul **et** `maintenant − last_seen_at < 90 s` |
| `last_seen_at` | instant | oui | dernière requête d'ingestion authentifiée (§2.1) |
| `last_sync_at` | instant | oui | dernier `POST /sync` réussi |
| `last_heartbeat_at` | instant | oui | dernier heartbeat reçu |
| `last_detection_at` | instant | oui | `MAX(detected_at_utc)` des détections ingérées de ce nœud |
| `mic_device_name` | chaîne | oui | dernier heartbeat |
| `mic_healthy` | booléen | oui | dernier heartbeat (`null` = inconnu) |
| `disk_free_pct` | flottant | oui | dernier heartbeat |
| `birdnet_go_reachable` | booléen | oui | dernier heartbeat (`null` si aucun) |
| `birdnet_go_pid_alive` | booléen | oui | dernier heartbeat |
| `birdnet_go_version` | chaîne | oui | dernier heartbeat |
| `bridge_version` | chaîne | oui | dernier heartbeat |
| `synced_up_to_id` | entier | non | `node_sync_state.last_synced_detection_id` |
| `node_db_max_id` | entier | oui | dernier heartbeat |
| `sync_lag` | entier | oui | `node_db_max_id − synced_up_to_id` (≥ 0), `null` si `node_db_max_id` nul |
| `decommissioned_at` | instant | oui | — |

#### `PendingItem` (bloc « en écoute »)

```json
{
  "node_id": 1,
  "scientific_name": "Erithacus rubecula",
  "common_name_fr": "Rougegorge familier",
  "status": "active",
  "hit_count": 3,
  "confidence_hint": null,
  "first_detected_unix": 1790519938,
  "last_updated_unix": 1790519944,
  "source_id": "audio_card_881db84a",
  "photo_url": "/api/v1/species/Erithacus%20rubecula/photo?size=320"
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `node_id` | entier | non | nœud émetteur |
| `scientific_name` | chaîne | non | canonique (§1.6) |
| `common_name_fr` | chaîne | oui | résolution §1.6 (le `common_name` du bridge sert de niveau 3) |
| `status` | chaîne | non | `active`, `approved` (confirmée, va devenir une détection), `rejected` (écartée) |
| `hit_count` | entier | non | nombre d'inférences positives cumulées |
| `confidence_hint` | flottant | oui | voir §4.5 (le plus souvent `null`) |
| `first_detected_unix`, `last_updated_unix` | entier | non | secondes Unix |
| `source_id` | chaîne | oui | source audio du nœud |
| `photo_url` | chaîne | oui | §1.6 |

Ordre des listes : `first_detected_unix` croissant, puis `scientific_name`. Pas de fusion entre
nœuds ni entre sources : deux éléments de même espèce peuvent coexister (le frontend PEUT les
regrouper à l'affichage).

#### `Prediction`

```json
{"scientific_name": "Parus major", "common_name_fr": "Mésange charbonnière", "confidence": 0.72, "is_primary": true}
```
Les listes `predictions` exposées au navigateur contiennent **d'abord la prédiction primaire**
(construite par le serveur à partir de la détection : nom canonique brut — pas le nom redirigé —,
confiance de la détection, `is_primary: true`), puis les secondaires par confiance décroissante
(`is_primary: false`). Les étiquettes non taxonomiques (`Dog`, `Human vocal`) sont incluses telles
quelles.

#### `RecentDetection`

```json
{
  "detection_id": 1523,
  "scientific_name": "Parus major",
  "common_name_fr": "Mésange charbonnière",
  "confidence": 0.72,
  "detected_at_utc": "2026-09-27T14:39:01Z",
  "photo_url": "/api/v1/species/Parus%20major/photo?size=320"
}
```
Vue effective : `scientific_name` est l'espèce **effective** (après redirection).

#### `CommandInfo` (commandes vues par le navigateur)

```json
{
  "command_id": 88,
  "node_id": 1,
  "kind": "set_species_threshold",
  "payload": {"scientific_name": "Larus argentatus", "aliases": [], "threshold": 0.4},
  "status": "applied",
  "created_at": "2026-09-27T13:29:50Z",
  "delivered_at": "2026-09-27T13:30:02Z",
  "applied_at": "2026-09-27T13:30:03Z",
  "expires_at": null,
  "error_message": null,
  "result": {"changed": true, "keys": ["larus argentatus"], "restart_required": false}
}
```
`applied_at` est renseigné pour `applied` **et** `failed` (instant de l'ack). `result` : objet de l'ack
ou `null`.

### 6.2 Sites et nœuds

#### `GET /sites`

Réponse **200** (tri par `name`) :
```json
{
  "sites": [
    {
      "slug": "pornic",
      "name": "Pornic",
      "timezone": "Europe/Paris",
      "lat": 47.1155,
      "lon": -2.1046,
      "created_at": "2026-09-27T12:00:00Z",
      "node_count": 1,
      "online": true,
      "last_detection_at": "2026-09-27T14:39:01Z",
      "total_detections": 4627
    }
  ]
}
```
`node_count` = nœuds non décommissionnés ; `online` = au moins un nœud en ligne ;
`total_detections` = détections valides (toutes espèces, sans exclusion de règle).

#### `GET /nodes`

Paramètre : `include_decommissioned` (booléen, défaut `false`). Réponse **200**, tri par
`site_slug` puis `node_id` : `{"nodes": [NodeStatus, …]}`.

### 6.3 `GET /sites/{slug}/now`

Instantané du bloc « en écoute » (le frontend l'appelle au chargement puis s'abonne au SSE §6.4).

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "server_time_utc": "2026-09-27T14:39:05Z",
  "pending": [
    {
      "node_id": 1,
      "scientific_name": "Erithacus rubecula",
      "common_name_fr": "Rougegorge familier",
      "status": "active",
      "hit_count": 3,
      "confidence_hint": null,
      "first_detected_unix": 1790519938,
      "last_updated_unix": 1790519944,
      "source_id": "audio_card_881db84a",
      "photo_url": "/api/v1/species/Erithacus%20rubecula/photo?size=320"
    }
  ],
  "node_status": {
    "node_id": 1, "node_name": "Mac Armand — Pornic", "site_slug": "pornic", "site_name": "Pornic",
    "online": true, "last_seen_at": "2026-09-27T14:39:04Z", "last_sync_at": "2026-09-27T14:38:50Z",
    "last_heartbeat_at": "2026-09-27T14:38:10Z", "last_detection_at": "2026-09-27T14:39:01Z",
    "mic_device_name": "HyperX QuadCast 2", "mic_healthy": true, "disk_free_pct": 62.4,
    "birdnet_go_reachable": true, "birdnet_go_pid_alive": true, "birdnet_go_version": "20260823",
    "bridge_version": "0.1.0", "synced_up_to_id": 4627, "node_db_max_id": 4627, "sync_lag": 0,
    "decommissioned_at": null
  },
  "recent": [
    {
      "detection_id": 1523,
      "scientific_name": "Parus major",
      "common_name_fr": "Mésange charbonnière",
      "confidence": 0.72,
      "detected_at_utc": "2026-09-27T14:39:01Z",
      "photo_url": "/api/v1/species/Parus%20major/photo?size=320"
    }
  ]
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `site_slug` | chaîne | non | — |
| `server_time_utc` | instant | non | pour calculer « il y a N s » côté navigateur sans dépendre de son horloge |
| `pending` | tableau de `PendingItem` | non | tous les nœuds du site, après expiration (§4.5) |
| `node_status` | `NodeStatus` | oui | nœud **principal** du site = nœud non décommissionné au `last_seen_at` le plus récent (à défaut, le plus petit `node_id`) ; `null` si le site n'a aucun nœud |
| `recent` | tableau de `RecentDetection` | non | les **10** dernières détections de la vue effective, `detected_at_utc` décroissant puis `detection_id` décroissant |

### 6.4 `GET /sites/{slug}/pending/stream` (SSE)

- Réponse `200`, `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache`,
  `X-Accel-Buffering: no`. Site inconnu → 404 JSON **avant** l'ouverture du flux.
- Le serveur envoie d'abord `retry: 3000`, puis **immédiatement** un événement `pending` avec
  l'état courant (le client n'a pas besoin d'appeler `/now` pour le bloc « en écoute »).
- Pas de `id:` ni de reprise `Last-Event-ID` : après reconnexion, le premier `pending` suffit.
- Chaque événement : ligne `event: <nom>`, ligne `data: <JSON sur une seule ligne>`, ligne vide.

**`event: pending`** — émis à la connexion puis à chaque changement de la liste du site (nouvel
instantané d'un bridge, ou expiration §4.5). **Remplace** entièrement la liste côté client.
```
event: pending
data: {"site_slug":"pornic","updated_at_utc":"2026-09-27T14:39:05Z","pending":[{"node_id":1,"scientific_name":"Erithacus rubecula","common_name_fr":"Rougegorge familier","status":"active","hit_count":3,"confidence_hint":null,"first_detected_unix":1790519938,"last_updated_unix":1790519944,"source_id":"audio_card_881db84a","photo_url":"/api/v1/species/Erithacus%20rubecula/photo?size=320"}]}
```
`data` = `{site_slug: chaîne, updated_at_utc: instant, pending: PendingItem[]}` — `pending` a
exactement la forme de `/now.pending`.

**`event: heartbeat`** — toutes les **15 s**, même sans activité (garde la connexion ouverte à
travers les proxies, signale un nœud hors ligne).
```
event: heartbeat
data: {"server_time_utc":"2026-09-27T14:39:20Z","node_online":true}
```
`node_online` = `online` du nœud principal (`false` si aucun nœud).

**`event: detection`** — une détection confirmée fraîchement ingérée (§4.2 étape 7 : vue effective,
moins de 15 min). Forme = `RecentDetection` :
```
event: detection
data: {"detection_id":1524,"scientific_name":"Turdus merula","common_name_fr":"Merle noir","confidence":0.91,"detected_at_utc":"2026-09-27T14:39:30Z","photo_url":"/api/v1/species/Turdus%20merula/photo?size=320"}
```
Le frontend PEUT s'en servir pour rafraîchir le calendrier du jour (debounce conseillé ≥ 5 s).

### 6.5 `GET /sites/{slug}/calendar`

Activité d'une journée locale, **toutes espèces, sans limite** (vue effective).

Paramètre : `date` (date locale `YYYY-MM-DD`, défaut = aujourd'hui dans le fuseau du site). Aucun
paramètre `limit` : s'il est passé, il est ignoré.

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "date": "2026-09-27",
  "timezone": "Europe/Paris",
  "sunrise_utc": "2026-09-27T05:51:00Z",
  "sunset_utc": "2026-09-27T17:43:00Z",
  "total_detections": 312,
  "species": [
    {
      "scientific_name": "Erithacus rubecula",
      "common_name_fr": "Rougegorge familier",
      "total": 58,
      "max_confidence": 0.98,
      "first_utc": "2026-09-27T05:12:44Z",
      "last_utc": "2026-09-27T14:31:09Z",
      "hours": [0,0,0,0,0,0,0,4,9,6,5,3,2,4,6,5,8,6,0,0,0,0,0,0],
      "photo_url": "/api/v1/species/Erithacus%20rubecula/photo?size=320"
    }
  ]
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `date` | date locale | non | journée demandée |
| `timezone` | chaîne | non | fuseau du site |
| `sunrise_utc`, `sunset_utc` | instant | oui | lever/coucher du soleil du jour local aux coordonnées du site (lib `astral`, élévation 0, précision minute, secondes à 00) ; `null` si `lat`/`lon` du site nuls ou jour polaire |
| `total_detections` | entier | non | somme des `total` |
| `species` | tableau | non | **toutes** les espèces effectives ayant ≥ 1 détection ce jour-là ; tri `total` décroissant puis `scientific_name` croissant ; `[]` si aucune |
| `species[].scientific_name` | chaîne | non | espèce effective |
| `species[].total` | entier ≥ 1 | non | nombre de détections du jour |
| `species[].max_confidence` | flottant | non | — |
| `species[].first_utc`, `last_utc` | instant | non | première et dernière détection du jour |
| `species[].hours` | tableau de **24** entiers | non | index = heure locale 0..23 (§1.4) ; somme = `total` |
| `species[].photo_url` | chaîne | oui | §1.6 |

Une date future ou sans données → 200 avec `species: []`.

### 6.6 `GET /sites/{slug}/recent-detections` (transitoire, WP-04)

Route de démarrage, remplacée fonctionnellement par `/now` en WP-06 ; PEUT être supprimée ensuite
(par mise à jour de ce contrat). Paramètre `limit` (1-200, défaut 50). Vue effective, tri
`detected_at_utc` décroissant. Réponse **200** : `{"detections": [RecentDetection, …]}`.

### 6.7 `GET /sites/{slug}/species`

Espèces réellement détectées sur ce site (vue par espèce, détections valides), **toutes** — y compris
celles sous règle `impossible` ou `redirect` (le frontend décide de l'affichage, typiquement grisées
avec un badge).

Paramètre : `sort` ∈ `total` (défaut, décroissant), `last_seen` (décroissant), `common_name`
(croissant, comparaison insensible à la casse et aux accents, repli sur `scientific_name` si nom nul).
Égalités départagées par `scientific_name` croissant.

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "species": [
    {
      "scientific_name": "Erithacus rubecula",
      "common_name_fr": "Rougegorge familier",
      "total": 412,
      "first_seen_utc": "2026-09-26T05:40:02Z",
      "last_seen_utc": "2026-09-27T14:31:09Z",
      "max_confidence": 0.99,
      "days_seen": 2,
      "photo_url": "/api/v1/species/Erithacus%20rubecula/photo?size=320",
      "has_sheet": true,
      "in_france_universe": true,
      "rule": null,
      "redirect_to_scientific_name": null
    }
  ]
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `total` | entier ≥ 1 | non | détections valides sur ce site |
| `first_seen_utc`, `last_seen_utc` | instant | non | — |
| `max_confidence` | flottant | non | — |
| `days_seen` | entier ≥ 1 | non | nombre de dates locales distinctes avec ≥ 1 détection valide |
| `has_sheet` | booléen | non | §1.6 |
| `in_france_universe` | booléen | non | espèce présente dans `species_universe_fr.json` |
| `rule` | chaîne | oui | `present`, `impossible`, `redirect` ou `null` (aucune règle sur ce site) |
| `redirect_to_scientific_name` | chaîne | oui | cible si `rule = redirect`, sinon `null` |

### 6.8 `GET /species`

Univers France (368 espèces de `species_universe_fr.json`) **+** toute espèce ayant au moins une
détection valide sur un site mais absente de l'univers.

Paramètres :

| Paramètre | Type | Défaut | Effet |
|---|---|---|---|
| `site` | slug | — | ajoute `site_total` pour ce site ; restreint `detected_only` à ce site. Slug inconnu → 404 `site_not_found` |
| `q` | chaîne ≤ 100 | — | sous-chaîne recherchée dans `common_name_fr` **ou** `scientific_name`, insensible à la casse **et aux accents** (NFKD, diacritiques retirés, `casefold`) |
| `detected_only` | booléen | `false` | `true` → seulement les espèces avec ≥ 1 détection valide (sur `site` si fourni, sinon sur n'importe quel site) |
| `sort` | `common_name` \| `france_max_score` \| `detections` | `common_name` | `common_name` croissant (insensible casse/accents) ; `france_max_score` décroissant (nuls en dernier) ; `detections` = `site_total` si `site` fourni sinon `total_detections`, décroissant. Égalités : `scientific_name` croissant |
| `limit` | 1-1000 | 500 | pagination §1.9 |
| `offset` | ≥ 0 | 0 | — |

Réponse **200** :
```json
{
  "species": [
    {
      "scientific_name": "Erithacus rubecula",
      "common_name_fr": "Rougegorge familier",
      "order": "Passeriformes",
      "family": "Muscicapidae",
      "in_france_universe": true,
      "france_max_score": 0.9939,
      "detected_sites": ["le-mans", "pornic"],
      "total_detections": 530,
      "site_total": 412,
      "photo_url": "/api/v1/species/Erithacus%20rubecula/photo?size=320",
      "has_sheet": true
    }
  ],
  "total": 371,
  "limit": 500,
  "offset": 0
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `order`, `family` | chaîne | oui | depuis `base.taxonomy` |
| `in_france_universe` | booléen | non | — |
| `france_max_score` | flottant | oui | `france_universe.max_score` ; `null` hors univers |
| `detected_sites` | tableau de slugs | non | sites avec ≥ 1 détection valide, triés par slug |
| `total_detections` | entier ≥ 0 | non | détections valides, tous sites |
| `site_total` | entier ≥ 0 | **oui** | détections valides sur `site` ; `null` si `site` non fourni |
| `photo_url`, `has_sheet` | — | — | §1.6 |

### 6.9 `GET /species/{scientific_name}`

Fiche complète = fusion `base/` + `sheets/` (§8.4) + présence par site. Nom inconnu partout (ni
univers, ni base, ni fiche, ni détection, ni règle) → **404 `species_not_found`**. Un alias est
résolu (la réponse porte le nom canonique).

Réponse **200** :
```json
{
  "scientific_name": "Erithacus rubecula",
  "aliases": [],
  "common_name_fr": "Rougegorge familier",
  "in_france_universe": true,
  "taxonomy": {
    "kingdom": "Animalia", "phylum": "Chordata", "class": "Aves", "order": "Passeriformes",
    "family": "Muscicapidae", "family_common": "Old World Flycatchers", "genus": "Erithacus",
    "species": "Erithacus rubecula"
  },
  "photo": {
    "url": "/api/v1/species/Erithacus%20rubecula/photo?size=320",
    "url_1600": "/api/v1/species/Erithacus%20rubecula/photo?size=1600",
    "width": 3564,
    "height": 2376,
    "license": "CC BY-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
    "author": "Giles Laurent",
    "credit": "Own work, from gileslaurent.com",
    "description_url": "https://commons.wikimedia.org/wiki/File:030_European_robin_in_the_Camargue_Photo_by_Giles_Laurent.jpg"
  },
  "wikipedia": {
    "fr": {
      "title": "Rouge-gorge familier",
      "url": "https://fr.wikipedia.org/wiki/Rouge-gorge_familier",
      "description": "espèce d'oiseaux",
      "extract": "Le Rouge-gorge familier est une espèce de passereaux. …"
    },
    "en": {
      "title": "European robin",
      "url": "https://en.wikipedia.org/wiki/European_robin",
      "description": "Species of bird",
      "extract": "The European robin, known simply as the robin …"
    }
  },
  "has_sheet": true,
  "summary_fr": "Petit passereau au plastron orange vif, le Rougegorge familier est l'un des oiseaux les plus connus des jardins français. Longtemps rangé parmi les grives, il appartient aujourd'hui à la famille des gobemouches de l'Ancien Monde. Son allure ronde, ses grands yeux noirs et sa confiance envers l'homme en font un compagnon habituel du jardinier, qu'il suit pour saisir les vers et les larves mis au jour. Territorial toute l'année, il défend farouchement son domaine contre ses congénères, au point que les combats peuvent être violents. Mâle et femelle chantent, ce qui est rare chez les passereaux, et leur chant mélancolique résonne même en hiver, parfois la nuit près des éclairages publics. En France, les nicheurs sont en partie sédentaires, rejoints à l'automne par des migrateurs venus du nord et de l'est de l'Europe. Il construit son nid près du sol, dans une cavité, un talus ou même un vieil objet abandonné au fond du jardin.",
  "habitat": "Sous-bois, haies, jardins et parcs arborés, du littoral à la montagne.",
  "diet": "Insectes, vers et araignées ; baies et graines en hiver.",
  "activity_pattern": "diurne",
  "migration": {
    "statut": "migrateur partiel",
    "hiverne": "Toute la France ; renforcé en hiver par des oiseaux d'Europe du Nord.",
    "niche": "Partout en France, d'avril à juillet.",
    "passage": "Mouvements marqués en mars et d'octobre à novembre."
  },
  "seasonality_fr": "Présent toute l'année ; chante même en hiver, surtout à l'aube.",
  "song_fr": "Phrases fluides et mélancoliques, cristallines ; cri « tic » sec et répété.",
  "lookalikes": [
    {"scientific_name": "Phoenicurus ochruros", "common_name_fr": "Rougequeue noir", "why_fr": "Cris « tic » proches."}
  ],
  "rarity_note": "Très commun partout en France.",
  "fun_facts": [
    "Les deux sexes chantent, y compris en hiver pour défendre un territoire.",
    "Il suit volontiers le jardinier pour attraper les vers mis au jour."
  ],
  "france_universe": {
    "max_score": 0.9939,
    "cities": {"Le Mans": 0.99, "Pornic": 0.992, "Rennes": 0.993},
    "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
  },
  "sources": ["https://fr.wikipedia.org/wiki/Rouge-gorge_familier"],
  "generated_at": "2026-09-27T16:10:00Z",
  "generator_model": "claude-haiku-4-5",
  "reviewed_by_human": false,
  "presence_by_site": [
    {
      "site_slug": "pornic",
      "site_name": "Pornic",
      "total": 412,
      "first_seen_utc": "2026-09-26T05:40:02Z",
      "last_seen_utc": "2026-09-27T14:31:09Z",
      "days_seen": 2,
      "max_confidence": 0.99,
      "months": [0,0,0,0,0,0,0,0,412,0,0,0],
      "rule": null,
      "redirect_to_scientific_name": null
    }
  ]
}
```

Champs (tous toujours présents ; `null` quand la source manque) :

| Champ | Type | Null ? | Source / définition |
|---|---|---|---|
| `scientific_name` | chaîne | non | canonique |
| `aliases` | tableau de chaînes | non | noms de `aliases.json` pointant vers cette espèce |
| `common_name_fr` | chaîne | oui | §1.6 |
| `in_france_universe` | booléen | non | — |
| `taxonomy` | objet | oui | `base.taxonomy` tel quel : `kingdom, phylum, class, order, family, family_common` (**en anglais**, fourni par le nœud), `genus, species` — chaînes, chacune pouvant être `null` |
| `photo` | objet | oui | `null` si la base n'a pas de photo. `url`/`url_1600` = routes proxy §6.10 (jamais l'URL Wikimedia directe) ; `width`, `height` (entiers, image originale), `license`, `license_url`, `author`, `credit`, `description_url` (chaînes, `null` si inconnues) repris de `base.photo` |
| `wikipedia` | objet | non | `{fr: WikiRef \| null, en: WikiRef \| null}` ; `WikiRef = {title, url, description, extract}` (chaînes, `description`/`extract` nullables) ; une langue vaut `null` si `base.wikipedia.<lang>.title` est nul |
| `has_sheet` | booléen | non | §1.6 |
| `summary_fr`, `habitat`, `diet`, `seasonality_fr`, `song_fr`, `rarity_note` | chaîne | oui | fiche rédactionnelle ; `null` si `has_sheet = false` (le frontend affiche alors `wikipedia.fr.extract`) |
| `activity_pattern` | chaîne | oui | `diurne` \| `nocturne` \| `crépusculaire` \| `mixte` |
| `migration` | objet | oui | `{statut, hiverne, niche, passage}` ; `statut` ∈ `sédentaire` \| `migrateur partiel` \| `migrateur` \| `hivernant` \| `estivant` \| `de passage` ; les trois textes nullables |
| `lookalikes` | tableau | non | `[{scientific_name, common_name_fr, why_fr}]` ; `[]` sans fiche. `common_name_fr` est **re-résolu par le serveur** (§1.6), pas recopié de la fiche |
| `fun_facts` | tableau de chaînes | non | `[]` sans fiche |
| `france_universe` | objet | oui | `{max_score: flottant, cities: {ville: flottant}, months: entier[]}` (base, sinon univers brut arrondi, sinon `null`) ; `months` = mois 1-12 où l'espèce est plausible selon le modèle de zone BirdNET (repris tel quel) |
| `sources` | tableau d'URLs | non | fiche ; `[]` sans fiche |
| `generated_at` | instant | oui | fiche |
| `generator_model` | chaîne | oui | fiche |
| `reviewed_by_human` | booléen | non | fiche (`false` par défaut ou sans fiche) — le frontend affiche le badge « généré par IA, à vérifier » quand `has_sheet && !reviewed_by_human` |
| `presence_by_site` | tableau | non | un élément par site ayant ≥ 1 détection valide **ou** une règle pour cette espèce ; tri `total` décroissant puis `site_slug` |
| `presence_by_site[].total` | entier ≥ 0 | non | détections valides (vue par espèce) |
| `presence_by_site[].first_seen_utc`, `last_seen_utc`, `max_confidence` | — | oui | `null` si `total = 0` |
| `presence_by_site[].days_seen` | entier ≥ 0 | non | — |
| `presence_by_site[].months` | 12 entiers | non | index 0 = janvier ; mois local, toutes années confondues |
| `presence_by_site[].rule`, `redirect_to_scientific_name` | chaîne | oui | règle du site |

### 6.10 `GET /species/{scientific_name}/photo`

Paramètre : `size` ∈ `320` (défaut) \| `1600` ; autre valeur → 422.

Comportement retenu : **proxy + cache disque serveur** (pas de redirection 302 : pas de hotlink vers
Wikimedia depuis le navigateur, fonctionne hors ligne une fois en cache).
1. Espèce sans photo dans sa base → **404 `photo_not_found`** (espèce inconnue → aussi
   `photo_not_found`).
2. Cache : `<BIRDFRAME_DATA_DIR>/photos/<Genre_espece>/<size>.jpg`. Présent → servi.
3. Absent : télécharger **une seule** source, `base.photo.url_1600` (à défaut `url_original`), avec
   un `User-Agent` identifiant le projet (comme `species-data/build_base.py`), timeout 20 s ; produire
   avec Pillow les deux tailles : largeur **320 px** et largeur **min(1600, largeur source)**, hauteur
   proportionnelle, JPEG qualité 85, EXIF retiré, profil sRGB ; écrire les deux fichiers
   atomiquement (fichier temporaire + renommage).
4. Échec du téléchargement → **502 `photo_upstream_error`** ; échec mémorisé 10 min (pas de nouvel
   appel amont pendant ce délai, même réponse 502).

Réponse **200** : corps JPEG, `Content-Type: image/jpeg`,
`Cache-Control: public, max-age=604800`. Le crédit photo (`author`, `license`) DOIT être affiché par
le frontend partout où la photo 1600 est affichée (fiche espèce).

### 6.11 `GET /species/{scientific_name}/sites/{slug}/top-clips`

Les ≤ 5 meilleurs enregistrements de l'espèce (nom **brut canonique**, vue par espèce) sur le site.

Paramètre : `include_missing` (booléen, défaut `false`).

- Site inconnu → 404 `site_not_found`. Espèce sans clip (ou inconnue) → 200 `{"clips": []}` (pas de
  404 espèce sur cette route).
- Par défaut : les entrées top-5 actives (`evicted_at IS NULL AND missing = 0`), triées par `rank`.
  Une entrée dont l'audio n'est pas encore reçu est incluse avec `audio_available: false` et
  `audio_url: null`.
- `include_missing=true` : ajoute **après** les 5 au plus 5 entrées signalées manquantes (les plus
  récentes), avec `rank: null` et `missing: true` (diagnostic).

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "scientific_name": "Parus major",
  "clips": [
    {
      "kept_clip_id": 88,
      "detection_id": 1523,
      "detected_at_utc": "2026-09-27T14:39:01Z",
      "confidence": 0.72,
      "rank": 1,
      "audio_available": true,
      "audio_url": "/api/v1/recordings/88/audio",
      "spectrogram_url": "/api/v1/recordings/88/spectrogram",
      "duration_s": 15.0,
      "review": null,
      "missing": false,
      "predictions": [
        {"scientific_name": "Parus major", "common_name_fr": "Mésange charbonnière", "confidence": 0.72, "is_primary": true},
        {"scientific_name": "Columba palumbus", "common_name_fr": "Pigeon ramier", "confidence": 0.0242, "is_primary": false},
        {"scientific_name": "Cyanistes caeruleus", "common_name_fr": "Mésange bleue", "confidence": 0.0217, "is_primary": false}
      ]
    }
  ]
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `kept_clip_id` | entier | non | — |
| `detection_id` | entier | non | détection serveur |
| `detected_at_utc` | instant | non | — |
| `confidence` | flottant | non | confiance de la détection |
| `rank` | entier 1-5 | oui | `null` seulement pour une entrée `missing` |
| `audio_available` | booléen | non | fichier audio présent sur le serveur |
| `audio_url` | chaîne | oui | `/api/v1/recordings/{kept_clip_id}/audio` si `audio_available`, sinon `null` |
| `spectrogram_url` | chaîne | oui | `/api/v1/recordings/{kept_clip_id}/spectrogram` si le PNG existe, sinon `null` |
| `duration_s` | flottant | oui | durée de l'audio (lue à la réception), `null` si inconnue |
| `review` | chaîne | oui | revue courante : `correct` ou `null` (un `false_positive` sort du top-5) |
| `missing` | booléen | non | `true` seulement avec `include_missing=true` |
| `predictions` | tableau de `Prediction` | non | primaire en tête (§6.1), puis secondaires (jusqu'à 9) |

### 6.12 `GET /species/{scientific_name}/presence`

Présence dans le temps (vue par espèce). Espèce inconnue partout → 404 `species_not_found`.

| Paramètre | Type | Défaut | Effet |
|---|---|---|---|
| `site` | slug | — | restreint au site ; absent = tous les sites (chaque détection est placée dans le fuseau **de son site**) ; inconnu → 404 |
| `include_by_day` | booléen | `false` | ajoute `by_day` |

Réponse **200** :
```json
{
  "scientific_name": "Erithacus rubecula",
  "site_slug": "pornic",
  "total": 412,
  "first_seen_utc": "2026-09-26T05:40:02Z",
  "last_seen_utc": "2026-09-27T14:31:09Z",
  "months": [0,0,0,0,0,0,0,0,412,0,0,0],
  "hours": [0,0,0,0,0,3,20,48,55,40,30,22,18,20,25,30,41,35,20,5,0,0,0,0],
  "by_day": [
    {"date": "2025-09-28", "count": 0},
    {"date": "2026-09-27", "count": 210}
  ]
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `site_slug` | chaîne | oui | `null` si tous sites |
| `total` | entier ≥ 0 | non | — |
| `first_seen_utc`, `last_seen_utc` | instant | oui | `null` si `total = 0` |
| `months` | 12 entiers | non | toute la période disponible, mois local (index 0 = janvier) |
| `hours` | 24 entiers | non | toute la période, heure locale |
| `by_day` | tableau ou `null` | oui | `null` si `include_by_day=false` ; sinon **exactement 365** éléments `{date, count}`, du plus ancien au plus récent, se terminant **aujourd'hui** (fuseau du site ; sans `site`, fuseau `Europe/Paris`), jours à 0 inclus |

### 6.13 Enregistrements : `GET /recordings/{kept_clip_id}/audio` et `/spectrogram`

**Audio** :
- 200 corps complet, `Content-Type` selon l'extension (`audio/wav` en S1 ; `audio/flac`,
  `audio/mpeg`, `audio/mp4`, `audio/ogg`), `Accept-Ranges: bytes`,
  `Cache-Control: public, max-age=31536000, immutable` (le contenu d'un `kept_clip_id` ne change
  jamais).
- **Support `Range`** (`bytes=a-b`, `bytes=a-`, `bytes=-n`, une seule plage) → **206** avec
  `Content-Range: bytes a-b/total` ; plage invalide → **416 `range_not_satisfiable`** avec
  `Content-Range: bytes */total`.
- Clip évincé, manquant ou pas encore reçu, ou id inconnu → **404 `recording_not_found`**.

**Spectrogramme** : `Content-Type: image/png`, même `Cache-Control` ; absent → **404
`spectrogram_not_found`**. Généré côté serveur à la réception (§4.3) par :
```
sox <audio> -n remix 1 rate 24k spectrogram -r -x 1000 -y 257 -z 90 -o <kept_clip_id>.png
```
Contrat d'image pour le frontend (curseur de lecture superposé) : PNG **sans axes ni légende**
(`-r`), 1000 × 257 px, l'axe horizontal couvre **exactement** toute la durée du clip (x = 0 au début,
x = largeur à la fin), l'axe vertical va de 0 Hz (bas) à 12 kHz (haut). Position du curseur :
`x = currentTime / duration × largeur_affichée`.

### Statistiques — règles communes (§6.14 à §6.19)

- Calculées **en SQL sur la table `detections` du serveur**, jamais par proxy vers le nœud
  (décision amendée `architecture.md` §9bis) : elles restent disponibles quand le nœud est hors ligne.
- **Vue effective** (§1.7) pour les six routes.
- Paramètres `start`/`end` (dates locales inclusives) : défaut `end` = aujourd'hui, `start` =
  `end − 29 jours` (30 jours). Un seul des deux fourni : l'autre prend sa valeur par défaut calculée
  à partir de lui (`start` seul → `end = start + 29 j` ; `end` seul → `start = end − 29 j`).
  `start > end` → 400 `invalid_range`.
- Toutes les réponses rappellent `site_slug` et `timezone`.

### 6.14 `GET /sites/{slug}/stats/kpis`

Pas de paramètre. Réponse **200** :
```json
{
  "site_slug": "pornic",
  "timezone": "Europe/Paris",
  "date": "2026-09-27",
  "lifetime_species": 58,
  "lifetime_detections": 4627,
  "today_detections": 312,
  "today_species": 27,
  "best_day": {"date": "2026-09-26", "count": 1740},
  "streak_days": 2,
  "first_detection_utc": "2026-09-25T21:11:14Z",
  "last_detection_utc": "2026-09-27T14:39:01Z"
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `date` | date locale | non | aujourd'hui (fuseau du site) |
| `lifetime_species` | entier | non | espèces effectives distinctes, toute la période |
| `lifetime_detections` | entier | non | — |
| `today_detections`, `today_species` | entier | non | journée locale courante |
| `best_day` | objet `{date, count}` | oui | journée locale au plus grand nombre de détections ; égalité → la plus récente ; `null` si aucune détection |
| `streak_days` | entier ≥ 0 | non | nombre de jours locaux **consécutifs** avec ≥ 1 détection, se terminant aujourd'hui si aujourd'hui a ≥ 1 détection, sinon se terminant hier ; 0 si ni aujourd'hui ni hier |
| `first_detection_utc`, `last_detection_utc` | instant | oui | `null` si aucune détection |

### 6.15 `GET /sites/{slug}/stats/daily?start=&end=`

Réponse **200** — **un élément par jour** de `start` à `end`, jours vides inclus (zéros), ordre
chronologique :
```json
{
  "site_slug": "pornic",
  "timezone": "Europe/Paris",
  "start": "2026-09-25",
  "end": "2026-09-27",
  "days": [
    {"date": "2026-09-25", "total": 12, "species_count": 5},
    {"date": "2026-09-26", "total": 1740, "species_count": 44},
    {"date": "2026-09-27", "total": 312, "species_count": 27}
  ]
}
```
`total` = détections du jour ; `species_count` = espèces effectives distinctes du jour.

### 6.16 `GET /sites/{slug}/stats/hourly?start=&end=`

Répartition par heure locale sur la période. Réponse **200** — **exactement 24** éléments,
`hour` = 0..23 dans l'ordre :
```json
{
  "site_slug": "pornic",
  "timezone": "Europe/Paris",
  "start": "2026-08-29",
  "end": "2026-09-27",
  "hours": [
    {
      "hour": 7,
      "total": 402,
      "species": [
        {"scientific_name": "Erithacus rubecula", "common_name_fr": "Rougegorge familier", "count": 88}
      ]
    }
  ]
}
```
`species` = les **10** espèces effectives les plus détectées à cette heure sur la période (`count`
décroissant, puis `scientific_name`), moins de 10 si moins d'espèces, `[]` si `total = 0`.

### 6.17 `GET /sites/{slug}/stats/species?start=&end=&limit=`

Classement des espèces sur la période. `limit` : 1-500, défaut 20.

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "timezone": "Europe/Paris",
  "start": "2026-08-29",
  "end": "2026-09-27",
  "total_species": 58,
  "species": [
    {
      "rank": 1,
      "scientific_name": "Erithacus rubecula",
      "common_name_fr": "Rougegorge familier",
      "total": 412,
      "days_seen": 2,
      "max_confidence": 0.99,
      "avg_confidence": 0.8123,
      "first_utc": "2026-09-26T05:40:02Z",
      "last_utc": "2026-09-27T14:31:09Z",
      "photo_url": "/api/v1/species/Erithacus%20rubecula/photo?size=320"
    }
  ]
}
```
Tri `total` décroissant, puis `scientific_name` croissant ; `rank` = position 1..n dans ce tri
(pas de rang ex æquo). `total_species` = nombre d'espèces effectives sur la période (avant `limit`).

### 6.18 `GET /sites/{slug}/stats/heatmap?year=&species=`

Matrice espèce × semaine (semaine au sens §1.4, **pas ISO**).

| Paramètre | Type | Défaut | Effet |
|---|---|---|---|
| `year` | entier 2000-2100 | année locale courante | année civile locale |
| `species` | nom scientifique, **répétable** (`?species=Erithacus%20rubecula&species=Turdus%20merula`) | — | si fourni : exactement ces espèces (1 à 40, dans l'ordre donné, y compris à zéro ; alias résolus ; > 40 → 422) ; sinon les **40** espèces effectives les plus détectées de l'année |

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "timezone": "Europe/Paris",
  "year": 2026,
  "week_count": 53,
  "species": [
    {
      "scientific_name": "Erithacus rubecula",
      "common_name_fr": "Rougegorge familier",
      "total": 412,
      "weeks": [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,412,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    }
  ]
}
```
`weeks` = **53** entiers, index 0 = semaine 1. Sans `species` : tri `total` décroissant puis
`scientific_name`.

### 6.19 `GET /sites/{slug}/stats/confidence?start=&end=&species=`

Histogramme de confiance en **10 classes**. `species` optionnel (un seul nom) : restreint à cette
espèce effective.

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "timezone": "Europe/Paris",
  "start": "2026-08-29",
  "end": "2026-09-27",
  "species": null,
  "total": 4627,
  "buckets": [
    {"min": 0.0, "max": 0.1, "count": 0},
    {"min": 0.1, "max": 0.2, "count": 0},
    {"min": 0.2, "max": 0.3, "count": 31},
    {"min": 0.3, "max": 0.4, "count": 820},
    {"min": 0.4, "max": 0.5, "count": 700},
    {"min": 0.5, "max": 0.6, "count": 610},
    {"min": 0.6, "max": 0.7, "count": 590},
    {"min": 0.7, "max": 0.8, "count": 600},
    {"min": 0.8, "max": 0.9, "count": 640},
    {"min": 0.9, "max": 1.0, "count": 636}
  ]
}
```
Classe `i` (0..9) = `[i/10, (i+1)/10)`, la dernière incluant 1.0 (`i = min(floor(conf × 10), 9)`).
Toujours 10 classes. `species` = nom canonique demandé ou `null`.

### 6.20 `GET /sites/{slug}/species-rules`

Réponse **200** (tri `updated_at` décroissant) :
```json
{
  "site_slug": "pornic",
  "rules": [
    {
      "scientific_name": "Columba livia",
      "common_name_fr": "Pigeon biset",
      "rule": "impossible",
      "threshold_override": null,
      "redirect_to_scientific_name": null,
      "redirect_to_common_name_fr": null,
      "reason": "Pas de pigeons bisets ici, confusion avec le ramier",
      "updated_at": "2026-09-27T15:00:00Z",
      "sync_status": "applied",
      "commands": [
        {
          "command_id": 90, "node_id": 1, "kind": "exclude_species",
          "payload": {"scientific_name": "Columba livia", "aliases": []},
          "status": "applied", "created_at": "2026-09-27T15:00:00Z",
          "delivered_at": "2026-09-27T15:00:02Z", "applied_at": "2026-09-27T15:00:03Z",
          "expires_at": null, "error_message": null,
          "result": {"changed": true, "list": "exclude", "restart_required": false}
        }
      ]
    }
  ]
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `rule` | chaîne | non | `present`, `impossible`, `redirect` |
| `threshold_override` | flottant | oui | seulement pour `present` |
| `redirect_to_scientific_name`, `redirect_to_common_name_fr` | chaîne | oui | seulement pour `redirect` |
| `reason` | chaîne | oui | texte libre d'Armand |
| `updated_at` | instant | non | dernier PUT |
| `commands` | tableau de `CommandInfo` | non | commandes créées par le **dernier** PUT de cette règle (tous nœuds), `id` croissant ; `[]` si aucune |
| `sync_status` | chaîne | non | agrégat de `commands` : `none` (aucune commande), `failed` (au moins une `failed` ou `expired`), `pending` (au moins une `pending`/`delivered`), sinon `applied` |

Le frontend rafraîchit cette liste toutes les 5 s tant qu'une règle est en `pending`.

### 6.21 `PUT /sites/{slug}/species-rules/{scientific_name}`

Crée ou remplace la règle (alias résolu vers le nom canonique).

Corps :
```json
{ "rule": "present", "threshold_override": 0.35, "redirect_to_scientific_name": null, "reason": "Nicheur dans le jardin" }
```

| Champ | Type | Requis | Contraintes |
|---|---|---|---|
| `rule` | chaîne | oui | `present` \| `impossible` \| `redirect` |
| `threshold_override` | flottant | optionnel | `present` seulement : 0.01 ≤ t ≤ 1.0 ou `null` ; non nul avec une autre règle → 422 |
| `redirect_to_scientific_name` | chaîne | optionnel | **requis non nul** si `redirect`, interdit sinon (422) ; ≠ nom de la règle (422) ; alias résolu |
| `reason` | chaîne ≤ 500 | optionnel | — |

Conflits : la cible d'une redirection porte elle-même une règle `redirect`, ou l'espèce est déjà la
cible d'une redirection sur ce site et on veut la rediriger → **409 `redirect_chain`**.

Effets (synchrones, dans la requête) :
1. écriture de `species_site_rules` (`updated_at = maintenant`) ;
2. recalcul de `detections.redirected_to_scientific_name` pour ce site et cette espèce
   (`= cible` si `redirect`, sinon `NULL`) ;
3. création des commandes selon §5.4.

Réponse **200** : `{"rule": <objet règle identique à un élément de GET §6.20>}` (avec `commands`
fraîchement créées en `pending`).

### 6.22 `DELETE /sites/{slug}/species-rules/{scientific_name}`

Supprime la règle ; remet `redirected_to_scientific_name` à `NULL` pour l'espèce ; crée les commandes
de retour à l'état « aucune règle » (§5.4). Règle absente → **404 `rule_not_found`**.
Réponse **200** : `{"deleted": true, "commands": [CommandInfo, …]}`.

### 6.23 `GET /sites/{slug}/dynamic-thresholds`

Miroir lecture seule du **dernier heartbeat** de chaque nœud du site (aucun appel au nœud).

Réponse **200** :
```json
{
  "site_slug": "pornic",
  "snapshot_at": "2026-09-27T14:40:00Z",
  "thresholds": [
    {
      "node_id": 1,
      "scientific_name": "Prunella modularis",
      "common_name_fr": "Accenteur mouchet",
      "node_species_name": "accenteur mouchet",
      "level": 3,
      "current_value": 0.2,
      "base_threshold": 0.6,
      "high_conf_count": 19,
      "trigger_count": 19,
      "is_active": true,
      "expires_at": "2026-09-28T14:26:19Z",
      "last_triggered_at": "2026-09-27T14:39:38Z",
      "first_created_at": "2026-09-27T14:39:38Z",
      "reset_pending": false
    }
  ]
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `snapshot_at` | instant | oui | instantané le plus récent parmi les nœuds ; `null` si aucun heartbeat avec instantané |
| `thresholds[].node_species_name` | chaîne | non | clé BirdNET-Go (`species_name` du heartbeat) |
| `level` | entier 0-3 | non | — |
| `current_value`, `base_threshold` | flottant | non | — |
| `expires_at`, `last_triggered_at`, `first_created_at` | instant | oui | — |
| `reset_pending` | booléen | non | une commande `reset_dynamic_threshold` `pending`/`delivered` existe pour ce nœud et cette espèce |

Tri : `level` décroissant, puis `scientific_name`.

### 6.24 `DELETE /sites/{slug}/dynamic-thresholds/{scientific_name}`

Crée une commande `reset_dynamic_threshold` pour **chaque nœud du site dont le dernier instantané
contient l'espèce**. Aucun → **404 `threshold_not_found`**. Réponse **202** :
```json
{ "commands": [ { "command_id": 91, "node_id": 1, "kind": "reset_dynamic_threshold", "payload": {"scientific_name": "Prunella modularis", "aliases": []}, "status": "pending", "created_at": "2026-09-27T15:05:00Z", "delivered_at": null, "applied_at": null, "expires_at": null, "error_message": null, "result": null } ] }
```
L'instantané affiché ne change qu'au heartbeat suivant (≤ 60 s après l'application).

### 6.25 `POST /sites/{slug}/reviews`

Corps :
```json
{ "detection_id": 1523, "kind": "false_positive", "note": "C'était un pic épeiche" }
```

| Champ | Type | Requis | Contraintes |
|---|---|---|---|
| `detection_id` | entier | oui | détection **serveur** de ce site (sinon 404 `detection_not_found`) |
| `kind` | chaîne | oui | `correct` \| `false_positive` |
| `note` | chaîne ≤ 1000 | optionnel | — |

Effets : insertion dans `reviews` (plusieurs revues par détection autorisées ; la plus récente fait
foi, §1.7) ; commande `mark_detection_reviewed` `{node_local_id, verified: kind, comment: note}` pour
le nœud d'origine ; si `false_positive` et la détection est dans le top-5 → éviction + promotion du
candidat suivant (§4.3.1) ; si `correct` après un `false_positive` → la détection redevient candidate.

Réponse **201** :
```json
{
  "review": {
    "review_id": 17,
    "detection_id": 1523,
    "kind": "false_positive",
    "note": "C'était un pic épeiche",
    "created_at": "2026-09-27T15:10:00Z",
    "created_by": null,
    "synced_to_node_at": null,
    "command_status": "pending",
    "detection": {
      "scientific_name": "Parus major",
      "common_name_fr": "Mésange charbonnière",
      "confidence": 0.72,
      "detected_at_utc": "2026-09-27T14:39:01Z"
    }
  },
  "command_id": 92
}
```
`created_by` : `null` en S1 (pas d'utilisateurs). `command_status` = statut de la commande
`mark_detection_reviewed` associée (`null` si aucune). `detection.scientific_name` = nom brut
canonique (pas le nom redirigé).

### 6.26 `GET /sites/{slug}/reviews`

Paramètres : `limit` (1-500, défaut 50), `offset`, `kind` (optionnel, `correct` \|
`false_positive`). Tri `created_at` décroissant puis `review_id` décroissant.
Réponse **200** : `{"reviews": [<objet review de §6.25>, …], "total": 12, "limit": 50, "offset": 0}`.

### 6.27 `POST /sites/{slug}/false-negatives`

Signalement d'une espèce entendue par Armand mais non détectée (enregistrement serveur uniquement,
**aucune** commande nœud).

Corps :
```json
{ "scientific_name": "Strix aluco", "approx_time_utc": "2026-09-26T21:30:00Z", "notes": "Hulotte entendue vers 23 h 30" }
```

| Champ | Type | Requis | Contraintes |
|---|---|---|---|
| `scientific_name` | chaîne 1-200 | oui | alias résolu ; une espèce hors univers est acceptée |
| `approx_time_utc` | instant | optionnel | — |
| `notes` | chaîne ≤ 1000 | optionnel | — |

Réponse **201** :
```json
{
  "false_negative": {
    "id": 3,
    "scientific_name": "Strix aluco",
    "common_name_fr": "Chouette hulotte",
    "known_species": true,
    "approx_time_utc": "2026-09-26T21:30:00Z",
    "notes": "Hulotte entendue vers 23 h 30",
    "reported_at": "2026-09-27T15:12:00Z",
    "reported_by": null
  }
}
```
`known_species` = espèce présente dans l'univers ou déjà détectée quelque part.

### 6.28 `GET /sites/{slug}/false-negatives`

Paramètres : `limit` (1-500, défaut 50), `offset`. Tri `reported_at` décroissant.
Réponse **200** : `{"false_negatives": [<objet de §6.27>, …], "total": 3, "limit": 50, "offset": 0}`.

### 6.29 `GET /sites/{slug}/commands`

Audit des commandes des nœuds du site. Paramètres : `status` (optionnel : `pending` \| `delivered` \|
`applied` \| `failed` \| `expired`), `kind` (optionnel, §5.2), `limit` (1-500, défaut 50), `offset`.
Tri `command_id` décroissant.
Réponse **200** : `{"commands": [CommandInfo, …], "total": 40, "limit": 50, "offset": 0}`.

### 6.30 `GET /sites/{slug}/detections`

Liste brute pour la revue (**aucune exclusion**, §1.7).

| Paramètre | Type | Défaut | Effet |
|---|---|---|---|
| `date` | date locale | — | restreint à la journée locale |
| `species` | nom scientifique | — | détections dont `scientific_name` **ou** `redirected_to_scientific_name` vaut ce nom (alias résolu) |
| `min_confidence` | flottant [0,1] | — | `confidence ≥ min_confidence` |
| `review` | `correct` \| `false_positive` \| `none` | — | filtre sur la revue courante (`none` = jamais revue) |
| `limit` | 1-500 | 50 | — |
| `offset` | ≥ 0 | 0 | — |

Tri `detected_at_utc` décroissant, puis `detection_id` décroissant.

Réponse **200** :
```json
{
  "detections": [
    {
      "detection_id": 1523,
      "node_id": 1,
      "node_local_id": 4627,
      "detected_at_utc": "2026-09-27T14:39:01Z",
      "local_date": "2026-09-27",
      "scientific_name": "Parus major",
      "common_name_fr": "Mésange charbonnière",
      "effective_scientific_name": "Parus major",
      "effective_common_name_fr": "Mésange charbonnière",
      "confidence": 0.72,
      "source_display_name": "Sound Card 1",
      "has_clip": true,
      "kept_clip_id": 88,
      "audio_url": "/api/v1/recordings/88/audio",
      "spectrogram_url": "/api/v1/recordings/88/spectrogram",
      "review": null,
      "review_note": null,
      "rule": null,
      "predictions": [
        {"scientific_name": "Parus major", "common_name_fr": "Mésange charbonnière", "confidence": 0.72, "is_primary": true},
        {"scientific_name": "Columba palumbus", "common_name_fr": "Pigeon ramier", "confidence": 0.0242, "is_primary": false}
      ]
    }
  ],
  "total": 4627,
  "limit": 50,
  "offset": 0
}
```

| Champ | Type | Null ? | Définition |
|---|---|---|---|
| `node_local_id` | entier | non | permet d'ouvrir la détection dans l'UI native du nœud |
| `local_date` | date locale | non | — |
| `scientific_name`, `common_name_fr` | — | — | nom brut canonique |
| `effective_scientific_name`, `effective_common_name_fr` | — | — | après redirection (= brut sans règle `redirect`) |
| `has_clip` | booléen | non | tel que déclaré par le bridge |
| `kept_clip_id` | entier | oui | si la détection est dans le top-5 actif |
| `audio_url`, `spectrogram_url` | chaîne | oui | seulement si `kept_clip_id` non nul et fichier présent |
| `review` | chaîne | oui | revue courante `correct` \| `false_positive` \| `null` |
| `review_note` | chaîne | oui | note de la revue courante |
| `rule` | chaîne | oui | règle du site sur `scientific_name` brut |
| `predictions` | tableau de `Prediction` | non | primaire en tête |

---

## 7. Configuration

### 7.1 Bridge : `node/config/<slug>.env`

Écrit par `scripts/register_node.py` (permissions **600**), lu par `node/bridge/config.py`. Format
`CLÉ=valeur`, une par ligne, pas de guillemets, `#` = commentaire. **Chemins absolus obligatoires.**
Lancement : `python -m bridge --config node/config/pornic.env`.

| Variable | Requis | Défaut | Description |
|---|---|---|---|
| `BRIDGE_SERVER_URL` | oui | — | URL du serveur **sans** `/api/v1` ni `/` final (le bridge ajoute `/api/v1`). S1 : `http://localhost:8090` |
| `BRIDGE_NODE_ID` | oui | — | entier renvoyé par `/nodes/register` |
| `BRIDGE_SECRET` | oui | — | `bridge_shared_secret` en clair |
| `BRIDGE_SITE_SLUG` | oui | — | slug du site (journaux ; valeur attendue de `main.name`) |
| `BRIDGE_DB_PATH` | oui | — | `birdnet.db` du nœud, ouvert **uniquement** en `file:…?mode=ro` (`uri=True`) |
| `BRIDGE_CLIPS_DIR` | oui | — | dossier racine des clips (= `realtime.audio.export.path` de BirdNET-Go résolu) ; `clip_name` y est relatif |
| `BRIDGE_NODE_API` | non | `http://localhost:8080` | API BirdNET-Go locale, sans `/` final |
| `BRIDGE_NODE_API_TOKEN` | non | vide | jeton Bearer natif BirdNET-Go (S2+, §5.1) ; vide = pas d'en-tête |
| `BRIDGE_SYNC_INTERVAL_S` | non | `20` | cadence de `/sync` |
| `BRIDGE_COMMANDS_INTERVAL_S` | non | `30` | cadence lente de `/commands` |
| `BRIDGE_COMMANDS_FAST_INTERVAL_S` | non | `3` | cadence rapide (session live active, ou 120 s après une commande reçue) |
| `BRIDGE_HEARTBEAT_INTERVAL_S` | non | `60` | cadence de `/heartbeat` |
| `BRIDGE_BATCH_SIZE` | non | `200` | taille de lot, **1 à 200** (au-delà : refus de démarrer) |
| `BRIDGE_STATE_FILE` | oui | — | fichier d'état JSON (ex. `/…/bird-frame/node/state/pornic.json`), créé si absent |
| `BRIDGE_BIRDNET_PID_FILE` | non | vide | fichier PID de BirdNET-Go (S1 : `/…/local-test/birdnet-go.pid`) ; vide → `birdnet_go_pid_alive = null` |
| `BRIDGE_LOG_LEVEL` | non | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `BRIDGE_NODE_READONLY` | non | `0` | `1` = **mode nœud en lecture seule** (obligatoire en S1 sur le Mac d'Armand, où le nœud est l'installation de développement `local-test/`) : le bridge n'exécute **aucune** mutation contre `BRIDGE_NODE_API` — il ne lance pas la boucle de commandes (un WARNING au démarrage et un rappel toutes les heures : « N commandes en attente côté serveur, nœud en lecture seule »), et `POST /nodes/register` est appelé avec `"auto_main_name": false` par `scripts/register_node.py` quand ce mode est demandé (`--node-readonly`), pour que `set_main_name` ne soit pas mis en file. Sync, clips, pending et heartbeat fonctionnent normalement (lectures seules). |

Exemple S1 :
```
BRIDGE_SERVER_URL=http://localhost:8090
BRIDGE_NODE_ID=1
BRIDGE_SECRET=Q2h0cX0l3S6mJv9s1q0yJpS6o0q8W7dM3xk1b2c3d4e
BRIDGE_SITE_SLUG=pornic
BRIDGE_DB_PATH=/Users/armand_mounsi/Documents/repositories/bird-frame/local-test/data/birdnet.db
BRIDGE_CLIPS_DIR=/Users/armand_mounsi/Documents/repositories/bird-frame/local-test/data/clips
BRIDGE_NODE_API=http://localhost:8080
BRIDGE_SYNC_INTERVAL_S=20
BRIDGE_COMMANDS_INTERVAL_S=30
BRIDGE_STATE_FILE=/Users/armand_mounsi/Documents/repositories/bird-frame/node/state/pornic.json
BRIDGE_BIRDNET_PID_FILE=/Users/armand_mounsi/Documents/repositories/bird-frame/local-test/birdnet-go.pid
```

Contenu de `BRIDGE_STATE_FILE` (optimisation seulement ; **le curseur serveur fait foi**) :
```json
{ "cursor": 4627, "updated_at": "2026-09-27T14:40:05Z" }
```
Écriture atomique (fichier temporaire + renommage) après chaque `synced_up_to_id` adopté.

### 7.2 Serveur : `server/.env`

Lu par `server/app/config.py` (pydantic-settings). Chemins relatifs résolus **par rapport au dossier
`server/`**. Lancement : `cd server && uvicorn app.main:app --host $BIRDFRAME_HOST --port $BIRDFRAME_PORT`.

| Variable | Requis | Défaut | Description |
|---|---|---|---|
| `BIRDFRAME_DB_PATH` | non | `data/bird-frame.db` | base SQLite du serveur |
| `BIRDFRAME_DATA_DIR` | non | `data` | contient `clips/<site_slug>/<Genre_espece>/<kept_clip_id>.<ext>` + `.png`, et `photos/<Genre_espece>/{320,1600}.jpg` |
| `BIRDFRAME_ADMIN_TOKEN` | oui pour `/nodes/register` | vide | ≥ 32 caractères ; vide = routes admin refusées (401) |
| `BIRDFRAME_HOST` | non | `127.0.0.1` | interface d'écoute |
| `BIRDFRAME_PORT` | non | `8090` | port |
| `BIRDFRAME_CORS_ORIGINS` | non | `http://localhost:5173,http://127.0.0.1:5173` | liste séparée par des virgules |
| `BIRDFRAME_SPECIES_DATA_DIR` | non | `../species-data` | lit `species_universe_fr.json`, `base/*.json`, `sheets/*.json`, `aliases.json` au démarrage (et via §3.2) ; `cache/` n'est **pas** lu |
| `BIRDFRAME_SOX_PATH` | non | `sox` | exécutable sox pour les spectrogrammes |
| `BIRDFRAME_MAX_UPLOAD_MB` | non | `25` | taille max d'un clip |
| `BIRDFRAME_LOG_LEVEL` | non | `info` | niveau de journal |

Exemple S1 :
```
BIRDFRAME_DB_PATH=data/bird-frame.db
BIRDFRAME_DATA_DIR=data
BIRDFRAME_ADMIN_TOKEN=change-me-please-at-least-32-characters-long
BIRDFRAME_PORT=8090
BIRDFRAME_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
BIRDFRAME_SPECIES_DATA_DIR=../species-data
```

### 7.3 Alias taxonomiques : `species-data/aliases.json`

Fichier créé et maintenu à la main (par l'équipe serveur au départ). Objet plat
`{"nom reçu": "nom canonique bird-frame"}` ; le nom canonique DOIT exister dans l'univers ou dans
`base/` ; pas de chaîne (une valeur n'est jamais elle-même une clé). Contenu initial (constaté dans la
base de Pornic) :
```json
{
  "Coloeus monedula": "Corvus monedula"
}
```
Le serveur journalise (WARNING, une fois par nom) toute espèce ingérée absente de l'univers et de
`base/` : c'est le signal pour compléter ce fichier. Un fichier absent = aucun alias.

---

## 8. Fichiers `species-data/`

### 8.1 Arborescence et nommage

```
species-data/
├── species_universe_fr.json      # 368 entrées {scientificName, commonName, label, maxScore, cities, months}
├── aliases.json                  # §7.3
├── base/<Genre_espece>.json      # pré-remplissage déterministe (build_base.py), §8.2
├── sheets/<Genre_espece>.json    # fiche rédactionnelle (agents Haiku), §8.3
└── cache/<Genre_espece>.{fr,en}.txt  # texte intégral Wikipédia pour les agents — jamais lu par le serveur
```
`<Genre_espece>` = `scientific_name` avec les espaces remplacés par `_` (ex. `Erithacus_rubecula`).
Le `scientific_name` contenu dans le fichier DOIT correspondre au nom de fichier ; sinon le fichier
est ignoré (et signalé dans `invalid_files`, §3.2).

### 8.2 Base pré-remplie `base/<Genre_espece>.json` (forme réelle)

Produite par `species-data/build_base.py` (lecture de `base/Erithacus_rubecula.json`). Le serveur la
lit **en mode tolérant** : toute clé absente est traitée comme `null`.

```json
{
 "scientific_name": "Erithacus rubecula",
 "common_name_fr": "Rougegorge familier",
 "birdnet_label": "Erithacus rubecula_Rougegorge familier",
 "taxonomy": {
  "kingdom": "Animalia", "phylum": "Chordata", "class": "Aves", "order": "Passeriformes",
  "family": "Muscicapidae", "family_common": "Old World Flycatchers", "genus": "Erithacus",
  "species": "Erithacus rubecula"
 },
 "wikipedia": {
  "fr": {"title": "Rouge-gorge familier", "url": "https://fr.wikipedia.org/wiki/Rouge-gorge_familier",
         "description": "espèce d'oiseaux", "extract": "Le Rouge-gorge familier est …", "fulltext_chars": 17068},
  "en": {"title": "European robin", "url": "https://en.wikipedia.org/wiki/European_robin",
         "description": "Species of bird", "extract": "The European robin …", "fulltext_chars": 18314}
 },
 "photo": {
  "source": "wikipedia",
  "url_original": "https://upload.wikimedia.org/wikipedia/commons/a/a3/030_European_robin_in_the_Camargue_Photo_by_Giles_Laurent.jpg",
  "width": 3564, "height": 2376,
  "file": "030_European_robin_in_the_Camargue_Photo_by_Giles_Laurent.jpg",
  "url_1600": "https://thumb.wikimedia.org/…/1920px-030_European_robin_in_the_Camargue_Photo_by_Giles_Laurent.jpg?…",
  "license": "CC BY-SA 4.0",
  "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
  "author": "Giles Laurent",
  "credit": "Own work, from gileslaurent.com",
  "description_url": "https://commons.wikimedia.org/wiki/File:030_European_robin_in_the_Camargue_Photo_by_Giles_Laurent.jpg"
 },
 "france_universe": {
  "max_score": 0.9939,
  "cities": {"Le Mans": 0.99, "Pornic": 0.992, "Rennes": 0.993, "…": 0.0},
  "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
 },
 "built_at": "2026-09-27T14:35:13Z"
}
```

| Champ | Type | Null ? | Remarques |
|---|---|---|---|
| `scientific_name` | chaîne | non | = nom du fichier |
| `common_name_fr` | chaîne | oui | nom BirdNET FR (univers) |
| `birdnet_label` | chaîne | oui | `"<scientifique>_<commun>"` |
| `taxonomy` | objet | **oui** (`null` si le nœud n'a pas répondu : drapeau `sans-taxonomie` du script) | 8 chaînes ; `family_common` est en **anglais** |
| `wikipedia.fr`, `wikipedia.en` | objet | non | chaque sous-champ `title`, `url`, `description`, `extract` peut être `null` (drapeau `sans-wiki-fr`) ; `fulltext_chars` entier ≥ 0 |
| `photo` | objet | **oui** (`null` : drapeau `sans-photo`) | `source`, `url_original`, `width`, `height` toujours présents si `photo` non nul ; `file`, `url_1600`, `license`, `license_url`, `author`, `credit`, `description_url` **absents** si la requête Commons a échoué. Attention : `url_1600` pointe en pratique vers une vignette 1920 px (pas exactement 1600) |
| `france_universe` | objet | non | `max_score` (4 décimales), `cities` (18 villes, 3 décimales), `months` (entiers 1-12) |
| `built_at` | instant | non | — |

La base n'est **jamais** modifiée par les agents ni par le serveur.

### 8.3 Fiche rédactionnelle `sheets/<Genre_espece>.json` (écrite par les agents Haiku)

Un agent par espèce lit `base/<Genre_espece>.json` et `cache/<Genre_espece>.{fr,en}.txt` (plus une
recherche web ciblée si nécessaire) et écrit **uniquement** ce fichier.

**Exemple complet** :
```json
{
  "schema_version": 1,
  "scientific_name": "Erithacus rubecula",
  "summary_fr": "Petit passereau au plastron orange vif, le Rougegorge familier est l'un des oiseaux les plus connus des jardins français. Longtemps rangé parmi les grives, il appartient aujourd'hui à la famille des gobemouches de l'Ancien Monde. Son allure ronde, ses grands yeux noirs et sa confiance envers l'homme en font un compagnon habituel du jardinier, qu'il suit pour saisir les vers et les larves mis au jour. Territorial toute l'année, il défend farouchement son domaine contre ses congénères, au point que les combats peuvent être violents. Mâle et femelle chantent, ce qui est rare chez les passereaux, et leur chant mélancolique résonne même en hiver, parfois la nuit près des éclairages publics. En France, les nicheurs sont en partie sédentaires, rejoints à l'automne par des migrateurs venus du nord et de l'est de l'Europe. Il construit son nid près du sol, dans une cavité, un talus ou même un vieil objet abandonné au fond du jardin.",
  "habitat": "Sous-bois, haies, jardins et parcs arborés, du littoral à la montagne.",
  "diet": "Insectes, vers de terre et araignées ; baies et petites graines en hiver.",
  "activity_pattern": "diurne",
  "migration": {
    "statut": "migrateur partiel",
    "hiverne": "Dans toute la France, où les nicheurs locaux sont rejoints par des oiseaux d'Europe du Nord et de l'Est.",
    "niche": "Partout en France, d'avril à juillet, souvent deux nichées.",
    "passage": "Passages marqués en mars puis d'octobre à novembre."
  },
  "seasonality_fr": "Visible et audible toute l'année ; c'est l'un des rares oiseaux à chanter en plein hiver.",
  "song_fr": "Chant fluide et mélancolique fait de phrases cristallines variées ; cri d'alarme « tic » sec et répété.",
  "lookalikes": [
    {"scientific_name": "Phoenicurus ochruros", "common_name_fr": "Rougequeue noir", "why_fr": "Cris « tic » secs très proches."},
    {"scientific_name": "Prunella modularis", "common_name_fr": "Accenteur mouchet", "why_fr": "Chant grinçant de même tessiture."}
  ],
  "rarity_note": "Très commun partout en France, toute l'année.",
  "fun_facts": [
    "Mâle et femelle chantent, y compris en hiver pour défendre chacun leur territoire.",
    "Il suit volontiers le jardinier pour attraper les vers mis au jour par la bêche."
  ],
  "sources": [
    "https://fr.wikipedia.org/wiki/Rouge-gorge_familier",
    "https://en.wikipedia.org/wiki/European_robin"
  ],
  "generated_at": "2026-09-27T16:10:00Z",
  "generator_model": "claude-haiku-4-5"
}
```

**Champ par champ** :

| Champ | Type | Requis | Contraintes |
|---|---|---|---|
| `schema_version` | entier | oui | exactement `1` |
| `scientific_name` | chaîne | oui | identique à `base.scientific_name` et au nom de fichier |
| `summary_fr` | chaîne | oui | **120 à 200 mots** (mots = segments séparés par des espaces), ton « trivia » accessible, un seul paragraphe |
| `habitat` | chaîne | oui | 1 à 2 phrases, ≤ 400 caractères |
| `diet` | chaîne | oui | 1 à 2 phrases, ≤ 400 caractères |
| `activity_pattern` | chaîne | oui | `diurne` \| `nocturne` \| `crépusculaire` \| `mixte` (orthographe exacte, accent compris) |
| `migration` | objet | oui | 4 clés, toutes présentes |
| `migration.statut` | chaîne | oui | `sédentaire` \| `migrateur partiel` \| `migrateur` \| `hivernant` \| `estivant` \| `de passage` — statut **en France** |
| `migration.hiverne` | chaîne ou `null` | oui | où/quand l'espèce passe l'hiver (en France ou hors de France), ≤ 300 caractères |
| `migration.niche` | chaîne ou `null` | oui | où/quand elle se reproduit (« Ne niche pas en France » est une réponse valide), ≤ 300 caractères |
| `migration.passage` | chaîne ou `null` | oui | périodes de passage migratoire en France ; `null` si sédentaire strict, ≤ 300 caractères |
| `seasonality_fr` | chaîne | oui | quand on le voit/entend en France, 1 à 2 phrases, ≤ 400 caractères |
| `song_fr` | chaîne | oui | comment reconnaître chant/cris, 1 à 2 phrases, ≤ 400 caractères |
| `lookalikes` | tableau | oui | 0 à 5 objets `{scientific_name, common_name_fr, why_fr}` : espèces avec lesquelles **BirdNET** peut le confondre (ressemblance acoustique), de préférence présentes dans l'univers ; `common_name_fr` chaîne ou `null` ; `why_fr` ≤ 200 caractères |
| `rarity_note` | chaîne | oui | 1 phrase, ≤ 300 caractères, cohérente avec `france_universe` |
| `fun_facts` | tableau de chaînes | oui | **2 ou 3** puces, chacune ≤ 250 caractères, une phrase |
| `sources` | tableau d'URLs | oui | 1 à 10 URLs `https://` distinctes ; DOIT contenir `base.wikipedia.fr.url` si non nulle (sinon `base.wikipedia.en.url`) |
| `generated_at` | instant | oui | UTC `YYYY-MM-DDTHH:MM:SSZ` |
| `generator_model` | chaîne | oui | identifiant exact du modèle (ex. `claude-haiku-4-5`) |
| `reviewed_by_human` | booléen | **non** | **jamais écrit par un agent** ; ajouté à la main par Armand (`true`) après relecture ; absent ≡ `false` |

**Règles de rédaction pour les agents** :
- Français, texte brut (ni Markdown, ni HTML, ni retour à la ligne dans les chaînes), UTF-8 NFC,
  fichier JSON écrit avec `ensure_ascii=False`, aucune clé en plus (`additionalProperties: false`).
- `france_universe` de la base est un **fait établi** (modèle de zone BirdNET : plausibilité par ville
  et par mois), jamais une supposition à contredire. Ne pas écrire « très rare en France » si
  `max_score ≥ 0.5`.
- Reformuler : ne pas recopier de longs passages de Wikipédia (licence CC BY-SA).
- Ne rien inventer : en cas de doute sur un champ nullable, `null` ; sur un champ texte requis, rester
  général plutôt que spéculatif.

**JSON Schema** (draft 2020-12) — à placer tel quel dans `server/app/species_sheets/sheet.schema.json`
et dans le prompt des agents :
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "bird-frame/species-sheet-v1",
  "title": "Fiche rédactionnelle bird-frame v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "scientific_name", "summary_fr", "habitat", "diet", "activity_pattern",
               "migration", "seasonality_fr", "song_fr", "lookalikes", "rarity_note", "fun_facts",
               "sources", "generated_at", "generator_model"],
  "properties": {
    "schema_version": {"const": 1},
    "scientific_name": {"type": "string", "minLength": 3, "maxLength": 200},
    "summary_fr": {"type": "string", "minLength": 500, "maxLength": 1800},
    "habitat": {"type": "string", "minLength": 10, "maxLength": 400},
    "diet": {"type": "string", "minLength": 5, "maxLength": 400},
    "activity_pattern": {"enum": ["diurne", "nocturne", "crépusculaire", "mixte"]},
    "migration": {
      "type": "object",
      "additionalProperties": false,
      "required": ["statut", "hiverne", "niche", "passage"],
      "properties": {
        "statut": {"enum": ["sédentaire", "migrateur partiel", "migrateur", "hivernant", "estivant", "de passage"]},
        "hiverne": {"type": ["string", "null"], "maxLength": 300},
        "niche": {"type": ["string", "null"], "maxLength": 300},
        "passage": {"type": ["string", "null"], "maxLength": 300}
      }
    },
    "seasonality_fr": {"type": "string", "minLength": 10, "maxLength": 400},
    "song_fr": {"type": "string", "minLength": 10, "maxLength": 400},
    "lookalikes": {
      "type": "array",
      "maxItems": 5,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["scientific_name", "common_name_fr", "why_fr"],
        "properties": {
          "scientific_name": {"type": "string", "minLength": 3, "maxLength": 200},
          "common_name_fr": {"type": ["string", "null"], "maxLength": 100},
          "why_fr": {"type": "string", "minLength": 5, "maxLength": 200}
        }
      }
    },
    "rarity_note": {"type": "string", "minLength": 5, "maxLength": 300},
    "fun_facts": {
      "type": "array", "minItems": 2, "maxItems": 3,
      "items": {"type": "string", "minLength": 10, "maxLength": 250}
    },
    "sources": {
      "type": "array", "minItems": 1, "maxItems": 10, "uniqueItems": true,
      "items": {"type": "string", "pattern": "^https://\\S+$"}
    },
    "generated_at": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"},
    "generator_model": {"type": "string", "minLength": 3, "maxLength": 100},
    "reviewed_by_human": {"type": "boolean"}
  }
}
```

**Validation au chargement par le serveur** : (1) JSON Schema ci-dessus ; (2) `scientific_name` =
nom de fichier ; (3) `summary_fr` entre **80 et 260 mots** sinon rejet (entre 80-119 ou 201-260 :
accepté avec WARNING — la cible des agents reste 120-200) ; (4) la base de l'espèce existe (sinon
WARNING, fiche acceptée) ; (5) alerte WARNING (pas de rejet) si `rarity_note` contient « rare »,
« exceptionnel » ou « accidentel » alors que `france_universe.max_score ≥ 0.5`. Fiche rejetée →
`has_sheet = false` et entrée dans `invalid_files`.

### 8.4 Fusion base + fiche pour `GET /species/{name}`

| Champ de réponse (§6.9) | Source |
|---|---|
| `common_name_fr` | §1.6 (base → univers → cache bridge) |
| `in_france_universe` | présence dans `species_universe_fr.json` |
| `taxonomy` | `base.taxonomy` |
| `photo.url`, `photo.url_1600` | générés (route proxy §6.10) si `base.photo` a `url_1600` ou `url_original` |
| `photo.width`, `height`, `license`, `license_url`, `author`, `credit`, `description_url` | `base.photo.*` |
| `wikipedia.fr/en.{title,url,description,extract}` | `base.wikipedia.*` (`fulltext_chars` non exposé) |
| `summary_fr`, `habitat`, `diet`, `activity_pattern`, `migration`, `seasonality_fr`, `song_fr`, `lookalikes`, `rarity_note`, `fun_facts`, `sources`, `generated_at`, `generator_model` | fiche (`null` / `[]` sans fiche) |
| `reviewed_by_human` | fiche (`false` par défaut) |
| `france_universe` | `base.france_universe`, sinon entrée de l'univers (`maxScore`→`max_score` arrondi à 4, `cities` arrondies à 3, `months`), sinon `null` |
| `presence_by_site` | calcul SQL (§6.9) |

---

## 9. Écarts de schéma SQL

Changements que ce contrat impose au DDL de `architecture.md` §4 (migration Alembic à l'équipe
serveur ; le reste du DDL est inchangé) :

1. **`detections`** : `+ raw_scientific_name TEXT NOT NULL` (nom reçu avant alias) ;
   `+ detected_local_date TEXT NOT NULL` ; `+ detected_local_hour INTEGER NOT NULL` ; index
   `(site_id, detected_local_date)` et `(node_id, detected_at_utc)`. `scientific_name` stocke le nom
   **canonique**.
2. **`kept_clips`** : `+ duration_s REAL` ; `+ missing_reason TEXT`.
3. **`node_commands`** : `kind` CHECK étendu aux 11 valeurs de §5.2 ; `status` CHECK `+ 'expired'` ;
   `+ expires_at TEXT` ; `+ result_json TEXT` ; `+ origin_type TEXT` (`species_rule`, `review`,
   `dynamic_threshold`, `register`, `live`, `manual`) ; `+ origin_id INTEGER` (id de la règle, de la
   revue…).
4. **`node_status`** : `+ last_heartbeat_at TEXT` ; `+ birdnet_go_reachable INTEGER` ;
   `+ node_db_max_id INTEGER` ; `+ dynamic_thresholds_snapshot_at TEXT`.
5. **Nouvelle table `species_names`** : `scientific_name TEXT PRIMARY KEY, common_name_fr TEXT,
   source TEXT NOT NULL DEFAULT 'bridge', updated_at TEXT NOT NULL` (cache de noms, niveau 3 §1.6).
6. **`false_negative_reports`** : `approx_time` renommé `approx_time_utc`.
7. **`species_sheets`** : cache libre des fichiers `species-data/` (la source de vérité reste les
   fichiers) ; l'équipe serveur PEUT stocker `base_json`/`sheet_json` bruts plutôt que les colonnes
   éclatées du §4 — seul le format de réponse §6.9 compte.
8. État « en écoute » : en mémoire (non persisté) ; perdu au redémarrage du serveur, reconstruit au
   prochain instantané du bridge (≤ 30 s).

---

## 10. Écarts voulus et hors périmètre

### 10.1 Écarts par rapport à `architecture.md` (ce fichier fait foi)

1. **`POST /pending`** : instantané complet (tableau `items`), pas un événement unitaire — c'est ce
   qu'émet réellement BirdNET-Go (§4.5). `confidence_hint` est le plus souvent `null`.
2. **Prédictions du sync** : secondaires uniquement ; `architecture.md` §3.1 demandait d'inclure la
   primaire, son exemple §5.2 ne l'incluait pas. Tranché : secondaires seules, la primaire est
   reconstruite par le serveur à la lecture (pas de doublon en base).
3. **Sync** : ajout de `since_id`, `node_max_id`, `rejected`, des 409 `cursor_ahead`/`node_db_reset`,
   et `want_clips` couvrant toutes les demandes en attente du nœud.
4. **Commandes** : ajout de `unexclude_species`, `uninclude_species`, `set_main_name`,
   `mark_detection_reviewed` (prévu par WP-13) ; `threshold: null` pour retirer un seuil (via
   `PUT /api/v2/settings`, le PATCH ne pouvant pas supprimer une clé) ; champ `aliases`.
5. **Règle `present`** = `include_species` (contourne le filtre de zone) + seuil optionnel.
6. **Stats** : 6 routes calculées en SQL côté serveur (`kpis`, `daily`, `hourly`, `species`,
   `heatmap`, `confidence`) ; `ridgeline`, `phenology`, `insights` ne font pas partie de ce contrat.
7. **Alias taxonomiques** (`aliases.json`) et cache de noms alimenté par le bridge.
8. **Photos** : proxy + cache disque serveur, pas de 302.
9. **Faux négatifs** rattachés au site : `/sites/{slug}/false-negatives` (au lieu de
   `/false-negatives`).
10. **`session_id` live** = UUID v4 obligatoire (l'exemple `abcd1234` de l'architecture serait ignoré
    par BirdNET-Go).
11. **Navigateur sans authentification en S1** (le login famille §10.4 est reporté).
12. **Seuils dynamiques** : le navigateur désigne l'espèce par son nom scientifique ; le bridge
    retrouve la clé BirdNET-Go (nom commun en minuscules).

### 10.2 Hors périmètre de ce contrat (vagues 4-5, à spécifier plus tard)

- `POST /sites/{slug}/live/start`, `…/live/heartbeat`, `GET /sites/{slug}/live/hls/*`,
  `GET /sites/{slug}/live/audio-level` (WP-19) — seuls les **payloads de commandes** live sont figés
  ici (§5.3).
- `POST /auth/login`, `POST /auth/logout` (session famille).
- `POST /species/{name}/sheet/regenerate` (appel API Claude).
- `GET /sites/{slug}/dynamic-thresholds/{species}/events` (historique ; exigerait un appel au nœud).
- Rotation de secret, décommission d'un nœud, modification d'un site (admin).
- Shadow BirdNET-Go (WP-21).

---

## 11. Annexe : types TypeScript de référence

À reprendre tel quel dans `web/src/lib/api/types.ts` (le serveur DOIT produire exactement ces formes ;
l'équipe serveur peut s'en servir pour relire ses schémas Pydantic).

```ts
// ---- Primitives -------------------------------------------------------------
export type UtcInstant = string;   // "2026-09-27T14:39:01Z"
export type LocalDate = string;    // "2026-09-27" (fuseau du site)
export type SpeciesRuleKind = 'present' | 'impossible' | 'redirect';
export type ReviewKind = 'correct' | 'false_positive';
export type PendingStatus = 'active' | 'approved' | 'rejected';
export type CommandStatus = 'pending' | 'delivered' | 'applied' | 'failed' | 'expired';
export type CommandKind =
  | 'set_species_threshold' | 'exclude_species' | 'unexclude_species'
  | 'include_species' | 'uninclude_species' | 'reset_dynamic_threshold'
  | 'set_main_name' | 'mark_detection_reviewed'
  | 'start_live' | 'live_heartbeat' | 'stop_live';
export type ActivityPattern = 'diurne' | 'nocturne' | 'crépusculaire' | 'mixte';
export type MigrationStatut =
  | 'sédentaire' | 'migrateur partiel' | 'migrateur' | 'hivernant' | 'estivant' | 'de passage';

export interface ApiError { error: string; message: string; details: unknown | null; }
export interface Page { total: number; limit: number; offset: number; }

// ---- Objets partagés --------------------------------------------------------
export interface NodeStatus {
  node_id: number; node_name: string; site_slug: string; site_name: string;
  online: boolean;
  last_seen_at: UtcInstant | null; last_sync_at: UtcInstant | null;
  last_heartbeat_at: UtcInstant | null; last_detection_at: UtcInstant | null;
  mic_device_name: string | null; mic_healthy: boolean | null; disk_free_pct: number | null;
  birdnet_go_reachable: boolean | null; birdnet_go_pid_alive: boolean | null;
  birdnet_go_version: string | null; bridge_version: string | null;
  synced_up_to_id: number; node_db_max_id: number | null; sync_lag: number | null;
  decommissioned_at: UtcInstant | null;
}
export interface PendingItem {
  node_id: number; scientific_name: string; common_name_fr: string | null;
  status: PendingStatus; hit_count: number; confidence_hint: number | null;
  first_detected_unix: number; last_updated_unix: number;
  source_id: string | null; photo_url: string | null;
}
export interface Prediction {
  scientific_name: string; common_name_fr: string | null; confidence: number; is_primary: boolean;
}
export interface RecentDetection {
  detection_id: number; scientific_name: string; common_name_fr: string | null;
  confidence: number; detected_at_utc: UtcInstant; photo_url: string | null;
}
export interface CommandInfo {
  command_id: number; node_id: number; kind: CommandKind;
  payload: Record<string, unknown>; status: CommandStatus;
  created_at: UtcInstant; delivered_at: UtcInstant | null; applied_at: UtcInstant | null;
  expires_at: UtcInstant | null; error_message: string | null;
  result: Record<string, unknown> | null;
}

// ---- Sites / nœuds ----------------------------------------------------------
export interface Site {
  slug: string; name: string; timezone: string; lat: number | null; lon: number | null;
  created_at: UtcInstant; node_count: number; online: boolean;
  last_detection_at: UtcInstant | null; total_detections: number;
}
export interface SitesResponse { sites: Site[]; }
export interface NodesResponse { nodes: NodeStatus[]; }

// ---- Dashboard --------------------------------------------------------------
export interface NowResponse {
  site_slug: string; server_time_utc: UtcInstant;
  pending: PendingItem[]; node_status: NodeStatus | null; recent: RecentDetection[];
}
export interface SsePendingEvent { site_slug: string; updated_at_utc: UtcInstant; pending: PendingItem[]; }
export interface SseHeartbeatEvent { server_time_utc: UtcInstant; node_online: boolean; }
export type SseDetectionEvent = RecentDetection;

export interface CalendarSpecies {
  scientific_name: string; common_name_fr: string | null; total: number; max_confidence: number;
  first_utc: UtcInstant; last_utc: UtcInstant; hours: number[]; /* 24 */ photo_url: string | null;
}
export interface CalendarResponse {
  site_slug: string; date: LocalDate; timezone: string;
  sunrise_utc: UtcInstant | null; sunset_utc: UtcInstant | null;
  total_detections: number; species: CalendarSpecies[];
}
export interface RecentDetectionsResponse { detections: RecentDetection[]; }

// ---- Espèces ----------------------------------------------------------------
export interface SiteSpecies {
  scientific_name: string; common_name_fr: string | null; total: number;
  first_seen_utc: UtcInstant; last_seen_utc: UtcInstant; max_confidence: number; days_seen: number;
  photo_url: string | null; has_sheet: boolean; in_france_universe: boolean;
  rule: SpeciesRuleKind | null; redirect_to_scientific_name: string | null;
}
export interface SiteSpeciesResponse { site_slug: string; species: SiteSpecies[]; }

export interface UniverseSpecies {
  scientific_name: string; common_name_fr: string | null; order: string | null; family: string | null;
  in_france_universe: boolean; france_max_score: number | null; detected_sites: string[];
  total_detections: number; site_total: number | null; photo_url: string | null; has_sheet: boolean;
}
export interface SpeciesListResponse extends Page { species: UniverseSpecies[]; }

export interface WikiRef { title: string; url: string | null; description: string | null; extract: string | null; }
export interface Taxonomy {
  kingdom: string | null; phylum: string | null; class: string | null; order: string | null;
  family: string | null; family_common: string | null; genus: string | null; species: string | null;
}
export interface SpeciesPhoto {
  url: string; url_1600: string; width: number | null; height: number | null;
  license: string | null; license_url: string | null; author: string | null;
  credit: string | null; description_url: string | null;
}
export interface Lookalike { scientific_name: string; common_name_fr: string | null; why_fr: string; }
export interface FranceUniverse { max_score: number; cities: Record<string, number>; months: number[]; }
export interface PresenceBySite {
  site_slug: string; site_name: string; total: number;
  first_seen_utc: UtcInstant | null; last_seen_utc: UtcInstant | null;
  days_seen: number; max_confidence: number | null; months: number[]; /* 12 */
  rule: SpeciesRuleKind | null; redirect_to_scientific_name: string | null;
}
export interface SpeciesDetail {
  scientific_name: string; aliases: string[]; common_name_fr: string | null;
  in_france_universe: boolean; taxonomy: Taxonomy | null; photo: SpeciesPhoto | null;
  wikipedia: { fr: WikiRef | null; en: WikiRef | null };
  has_sheet: boolean;
  summary_fr: string | null; habitat: string | null; diet: string | null;
  activity_pattern: ActivityPattern | null;
  migration: { statut: MigrationStatut; hiverne: string | null; niche: string | null; passage: string | null } | null;
  seasonality_fr: string | null; song_fr: string | null; lookalikes: Lookalike[];
  rarity_note: string | null; fun_facts: string[];
  france_universe: FranceUniverse | null; sources: string[];
  generated_at: UtcInstant | null; generator_model: string | null; reviewed_by_human: boolean;
  presence_by_site: PresenceBySite[];
}
export interface TopClip {
  kept_clip_id: number; detection_id: number; detected_at_utc: UtcInstant; confidence: number;
  rank: number | null; audio_available: boolean; audio_url: string | null;
  spectrogram_url: string | null; duration_s: number | null; review: 'correct' | null;
  missing: boolean; predictions: Prediction[];
}
export interface TopClipsResponse { site_slug: string; scientific_name: string; clips: TopClip[]; }
export interface PresenceResponse {
  scientific_name: string; site_slug: string | null; total: number;
  first_seen_utc: UtcInstant | null; last_seen_utc: UtcInstant | null;
  months: number[]; /* 12 */ hours: number[]; /* 24 */
  by_day: { date: LocalDate; count: number }[] | null; /* 365 */
}

// ---- Stats ------------------------------------------------------------------
interface StatsBase { site_slug: string; timezone: string; }
interface StatsRange extends StatsBase { start: LocalDate; end: LocalDate; }
export interface KpisResponse extends StatsBase {
  date: LocalDate; lifetime_species: number; lifetime_detections: number;
  today_detections: number; today_species: number;
  best_day: { date: LocalDate; count: number } | null; streak_days: number;
  first_detection_utc: UtcInstant | null; last_detection_utc: UtcInstant | null;
}
export interface DailyResponse extends StatsRange { days: { date: LocalDate; total: number; species_count: number }[]; }
export interface HourlyResponse extends StatsRange {
  hours: { hour: number; total: number;
           species: { scientific_name: string; common_name_fr: string | null; count: number }[] }[]; /* 24 */
}
export interface SpeciesRankingResponse extends StatsRange {
  total_species: number;
  species: { rank: number; scientific_name: string; common_name_fr: string | null; total: number;
             days_seen: number; max_confidence: number; avg_confidence: number;
             first_utc: UtcInstant; last_utc: UtcInstant; photo_url: string | null }[];
}
export interface HeatmapResponse extends StatsBase {
  year: number; week_count: 53;
  species: { scientific_name: string; common_name_fr: string | null; total: number; weeks: number[] /* 53 */ }[];
}
export interface ConfidenceResponse extends StatsRange {
  species: string | null; total: number; buckets: { min: number; max: number; count: number }[]; /* 10 */
}

// ---- Système ----------------------------------------------------------------
export interface SpeciesRule {
  scientific_name: string; common_name_fr: string | null; rule: SpeciesRuleKind;
  threshold_override: number | null; redirect_to_scientific_name: string | null;
  redirect_to_common_name_fr: string | null; reason: string | null; updated_at: UtcInstant;
  sync_status: 'none' | 'pending' | 'applied' | 'failed'; commands: CommandInfo[];
}
export interface SpeciesRulesResponse { site_slug: string; rules: SpeciesRule[]; }
export interface PutSpeciesRuleBody {
  rule: SpeciesRuleKind; threshold_override?: number | null;
  redirect_to_scientific_name?: string | null; reason?: string | null;
}
export interface PutSpeciesRuleResponse { rule: SpeciesRule; }
export interface DeleteSpeciesRuleResponse { deleted: true; commands: CommandInfo[]; }

export interface DynamicThreshold {
  node_id: number; scientific_name: string; common_name_fr: string | null; node_species_name: string;
  level: number; current_value: number; base_threshold: number; high_conf_count: number;
  trigger_count: number; is_active: boolean; expires_at: UtcInstant | null;
  last_triggered_at: UtcInstant | null; first_created_at: UtcInstant | null; reset_pending: boolean;
}
export interface DynamicThresholdsResponse { site_slug: string; snapshot_at: UtcInstant | null; thresholds: DynamicThreshold[]; }
export interface ResetDynamicThresholdResponse { commands: CommandInfo[]; }

export interface Review {
  review_id: number; detection_id: number; kind: ReviewKind; note: string | null;
  created_at: UtcInstant; created_by: string | null; synced_to_node_at: UtcInstant | null;
  command_status: CommandStatus | null;
  detection: { scientific_name: string; common_name_fr: string | null; confidence: number; detected_at_utc: UtcInstant };
}
export interface PostReviewBody { detection_id: number; kind: ReviewKind; note?: string | null; }
export interface PostReviewResponse { review: Review; command_id: number | null; }
export interface ReviewsResponse extends Page { reviews: Review[]; }

export interface FalseNegative {
  id: number; scientific_name: string; common_name_fr: string | null; known_species: boolean;
  approx_time_utc: UtcInstant | null; notes: string | null;
  reported_at: UtcInstant; reported_by: string | null;
}
export interface PostFalseNegativeBody { scientific_name: string; approx_time_utc?: UtcInstant | null; notes?: string | null; }
export interface PostFalseNegativeResponse { false_negative: FalseNegative; }
export interface FalseNegativesResponse extends Page { false_negatives: FalseNegative[]; }

export interface CommandsResponse extends Page { commands: CommandInfo[]; }

export interface ReviewDetection {
  detection_id: number; node_id: number; node_local_id: number;
  detected_at_utc: UtcInstant; local_date: LocalDate;
  scientific_name: string; common_name_fr: string | null;
  effective_scientific_name: string; effective_common_name_fr: string | null;
  confidence: number; source_display_name: string | null; has_clip: boolean;
  kept_clip_id: number | null; audio_url: string | null; spectrogram_url: string | null;
  review: ReviewKind | null; review_note: string | null; rule: SpeciesRuleKind | null;
  predictions: Prediction[];
}
export interface DetectionsResponse extends Page { detections: ReviewDetection[]; }
```
