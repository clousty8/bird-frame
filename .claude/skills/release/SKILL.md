---
name: release
description: |
  Coupe une release de bird-frame : bump de version → CHANGELOG.md → push `dev` → PR `dev`→`main`
  → CI → fusion automatique (pas de pause de review) → tag + release GitHub → suivi du
  déploiement Railway → suivi de la mise à jour des nœuds. Utilise ce skill quand :
  - L'utilisateur tape `/release` ou `/release <patch|minor|major|X.Y.Z>`
  - L'utilisateur dit « fais une release », « publie une version », « sors une release », « on release »
  Le skill est automatique de bout en bout, **sans pause de review** : Armand est seul sur ce
  dépôt, déclencher `/release` vaut autorisation de tout enchaîner jusqu'à la publication.
---

# Release — Publier une version de bird-frame

Ce skill enchaîne tout le processus de release, **sans pause humaine** : bump → CHANGELOG →
push `dev` → PR → CI verte → fusion → tag/release GitHub → suivi Railway → suivi des nœuds →
rapport final. S'arrête et rapporte seulement en cas d'échec réel (CI rouge, conflit inattendu).

**Pré-requis de gouvernance** (rappel) : dépôt privé `clousty8/bird-frame`, branches `dev`
(travail) et `main` (production). GitHub ne protège pas `main` (fonction payante sur un dépôt
privé) : **c'est ce skill qui garantit qu'on ne fusionne jamais avec le check CI `test` rouge**
(`.github/workflows/ci.yml`) — ne jamais pousser directement sur `main` ; Railway construit et déploie automatiquement l'image Docker à
chaque push sur `main`. Une release embarque **tout l'état courant de `dev`** dans `main` — pas
de confirmation de périmètre à demander.

## Étape 1 — Partir d'un `dev` propre et à jour

```bash
git checkout dev
git status            # doit être clean
git fetch origin
git merge --ff-only origin/dev
```

Si l'arbre n'est pas clean, arrête-toi : on ne release pas par-dessus du travail non committé.

## Étape 2 — Déterminer le niveau de bump

- Si l'utilisateur a fourni l'argument (`/release minor`, `patch`, `major`, ou une version
  `X.Y.Z`), utilise-le.
- Sinon, **déduis-le** des commits de `dev` depuis le dernier tag et **annonce ton choix** :

  ```bash
  LAST=$(git describe --tags --abbrev=0 --match 'v*' 2>/dev/null || echo "")
  git log ${LAST:+$LAST..}HEAD --no-merges --pretty=format:'%s'
  ```

  En `0.y.z` (cas actuel) : nouveautés (`feat:`) → `minor` ; fix uniquement (`fix:`) → `patch`.
  `major` seulement pour un changement réellement cassant (schéma SQLite sans migration,
  rupture du contrat `docs/api-contract.md` entre bridge et serveur, format de config du nœud
  qui change) — rare, à ne déduire que si les commits le disent explicitement.

## Étape 3 — Bumper la version

```bash
python3 scripts/bump.py <patch|minor|major|X.Y.Z>
```

Ce script synchronise **tous** les emplacements de version d'un coup (`VERSION`,
`server/pyproject.toml`, `node/pyproject.toml`, `web/package.json`, etc. — voir le script pour
la liste exacte). **N'édite jamais ces fichiers à la main.** Récupère la version bumpée avec
`python3 scripts/bump.py --print` si besoin de la reconfirmer.

## Étape 4 — Mettre à jour `CHANGELOG.md`

`CHANGELOG.md` (racine) alimente aussi la description de la release GitHub (étape 10). Il faut
une section pour la **nouvelle** version. Reste simple — quelques puces suffisent.

1. Reprends la liste de commits obtenue à l'étape 2.
2. Résume-les en **3 à 6 puces courtes, orientées utilisateur** (ce que ça change POUR ARMAND,
   pas le détail technique). Garde les `feat:` / `fix:` parlants ; **ignore** `chore:`, `docs:`,
   `test:`, `refactor:`, `chore(release):` et les merges. Français clair.
3. Ajoute la section **tout en haut** du corps de `CHANGELOG.md` (juste après le bloc d'en-tête,
   avant la section précédente), au format **exact** :

   ```md
   ## vX.Y.Z

   - Première nouveauté
   - Deuxième nouveauté
   ```

   `X.Y.Z` = la version bumpée à l'étape 3. Le `v` du titre est **obligatoire** (l'étape 10 lit
   cette section telle quelle pour `gh release create --notes`). Si une section `## vX.Y.Z` de
   cette version existe déjà (préparée pendant le dev), garde-la ou affine-la — n'en crée pas
   une deuxième.

Si tu n'es pas sûr ou qu'il n'y a rien de notable, une seule puce générique suffit. Ne bloque
jamais la release pour le changelog.

## Étape 5 — Commiter et pousser `dev`

```bash
git add VERSION server/pyproject.toml node/pyproject.toml web/package.json CHANGELOG.md
# + tout autre fichier touché par bump.py (regarde `git status` pour ne rien oublier)
git commit -m "chore(release): vX.Y.Z"
git push origin dev
```

**Pousse directement — NE demande PAS d'autorisation.** Le fait que l'utilisateur ait déclenché
`/release` **vaut autorisation explicite** de pousser sur `dev`.

## Étape 6 — Ouvrir la PR `dev` → `main`

```bash
gh pr create --base main --head dev \
  --title "Release vX.Y.Z" \
  --body "Release vX.Y.Z. Voir CHANGELOG.md pour le détail."
```

Récupère le numéro/URL de la PR pour la suite.

## Étape 7 — Attendre la CI verte

Le check requis est `test` (job agrégateur de `.github/workflows/ci.yml`, qui dépend de
`server`, `node`, `web`, `versions` et `docker`). **Surveille-le en ré-interrogeant
périodiquement** :

```bash
gh pr checks <pr-number>
```

N'utilise **pas** un `gh pr checks --watch` bloquant : la CI peut dépasser le timeout des
commandes. Ré-interroge (par ex. toutes les 20-30 s) jusqu'à ce que `test` soit `pass`.

**Si la CI échoue → arrête-toi et rapporte l'échec (ne merge pas).** Donne le nom du/des job(s)
en échec et un lien vers les logs (`gh run view <run-id> --log-failed` ou l'URL de la PR).

## Étape 8 — Fusionner dans `main` (pas de pause)

Dès que `test` est vert :

```bash
gh pr merge <pr-number> --merge
```

⚠️ **TOUJOURS `--merge` (merge commit à deux parents). JAMAIS `--squash` ni `--rebase`, et
JAMAIS le bouton « Squash »/« Rebase » de l'UI GitHub.** `dev` est une branche **permanente**
re-mergée dans `main` à chaque release : un squash/rebase crée sur `main` un commit orphelin
sans lien avec l'historique de `dev` → la base de merge reste figée à la release précédente →
**la release SUIVANTE se retrouve avec des conflits sur tout le changeset** (le même diff vu
« des deux côtés »). Un vrai merge commit fait avancer la base de merge et évite définitivement
ce piège.

Pas de pause de review ici : Armand travaille seul sur ce dépôt, `/release` vaut approbation.

## Étape 9 — Re-synchroniser `main` → `dev` (anti-divergence)

Le merge commit de l'étape 8 vit sur `main` mais pas encore sur `dev` → on le ramène tout de
suite pour que les deux branches restent alignées :

```bash
git checkout dev
git fetch origin
git merge --ff-only origin/dev      # dev local à jour
git merge origin/main               # ramène le merge commit de release ; doit être propre
git push origin dev
```

Ce merge doit être **propre** (aucun conflit) puisque `main` ne contient que ce que `dev` a
produit. S'il y a le moindre conflit, c'est le symptôme du piège squash décrit à l'étape 8 :
**arrête-toi et analyse** (probable squash/rebase antérieur à réconcilier via
`git merge -s ours origin/main`) plutôt que de résoudre à l'aveugle.

## Étape 10 — Tag et release GitHub

Extrais la section fraîchement ajoutée à `CHANGELOG.md` (étape 4) pour en faire les notes de
release :

```bash
NOTES=$(awk '/^## vX\.Y\.Z$/{flag=1; next} /^## v/{flag=0} flag' CHANGELOG.md)
gh release create vX.Y.Z --target main --title vX.Y.Z --notes "$NOTES"
```

(remplace `X.Y.Z` par la version réelle dans les deux commandes). `gh release create` crée le
tag `vX.Y.Z` sur `main` automatiquement s'il n'existe pas encore — pas besoin de `git tag` à la
main.

## Étape 11 — Suivre le déploiement Railway

Railway reconstruit l'image Docker et redéploie automatiquement à chaque push sur `main`
(déclenché par le merge de l'étape 8) — rien à lancer ici, seulement **vérifier que ça a
abouti**.

1. Lis `BIRDFRAME_PUBLIC_URL` dans `deploy/production.env` (racine du dépôt).
   - **Si vide** : le lead n'a pas encore renseigné l'URL Railway. Note-le dans le rapport
     final ("déploiement non vérifiable automatiquement — deploy/production.env vide") et passe
     à l'étape 12 sans bloquer.
2. Si l'URL est renseignée, ré-interroge (jamais de longue attente bloquante en un seul
   `sleep` — poll toutes les 20-30 s, ~10 min max) :

   ```bash
   curl -fsS "<BIRDFRAME_PUBLIC_URL>/health"
   ```

   `GET /health` est **sans authentification** (contrat `docs/api-contract.md` §1.12), donc pas
   de jeton à passer ici. Réponse attendue : `{"status":"ok","version":"X.Y.Z"}`. Continue tant
   que `version` ≠ `X.Y.Z` (build/déploiement Railway en cours), jusqu'à ~10 minutes.
3. **En cas d'échec ou de timeout** : si les outils MCP Railway (`mcp__railway__list-deployments`,
   `mcp__railway__get-logs`) sont disponibles, utilise-les pour inspecter le dernier déploiement
   du service et comprendre l'échec avant de rapporter. Sinon, rapporte simplement l'échec avec
   la dernière réponse observée de `/health`.

## Étape 12 — Suivre la mise à jour des nœuds

Chaque nœud (une installation gérée, ex. un Raspberry Pi sur site) se vérifie lui-même toutes
les 10 minutes et se met à jour seul — rien à déclencher, seulement **vérifier que chacun a
bien pris la nouvelle version**.

Si `BIRDFRAME_PUBLIC_URL` est vide (étape 11), cette étape n'est pas vérifiable non plus : le
signaler dans le rapport et t'arrêter là pour cette partie.

Sinon, ré-interroge (poll, jamais bloquant, ~15 min max) :

```bash
curl -fsS "<BIRDFRAME_PUBLIC_URL>/api/v1/nodes" | jq '.nodes[] | {node_name, site_slug, online, bridge_version}'
```

Pour chaque nœud **en ligne** (`online: true`), attends que `bridge_version == "X.Y.Z"`. Un
nœud **hors ligne** (`online: false`) est **signalé dans le rapport, mais pas bloquant** — il se
mettra à jour à sa prochaine reconnexion, pas la peine d'attendre après lui.

⚠️ Si `GET /api/v1/nodes` répond `401`/`403` : l'authentification famille (session, cf.
`docs/api-contract.md` §2.2/§10.2) a peut-être été activée en production depuis l'écriture de ce
skill. Ne devine pas un en-tête ou un jeton : arrête-toi sur ce point précis, rapporte l'erreur
telle quelle, et indique qu'il faut adapter cette étape (voir la doc d'auth du serveur ou
`server/app/auth.py`) une fois qu'on sait comment s'authentifier en tant qu'appelant machine.

## Étape 13 — Rapport final

Termine par un tableau récapitulatif :

| Élément | Résultat |
|---|---|
| Version | vX.Y.Z |
| PR | `dev` → `main`, #<numéro>, lien |
| Release GitHub | lien vers `gh release view vX.Y.Z --web` |
| Railway | version servie par `/health`, ou "non vérifié (URL non configurée)" |
| Nœud `<slug>` (×N) | en ligne/hors ligne, `bridge_version` observée |

Signale clairement tout point resté en échec ou non vérifié plutôt que de laisser croire que
tout est passé.

## Ce que ce skill ne fait PAS

- Demander une confirmation de périmètre (volontairement automatique)
- Demander l'autorisation de pousser sur `dev` (déclencher `/release` = autorisation explicite —
  étape 5)
- Faire une pause de review avant de merger (Armand est seul ; contrairement à un skill à
  plusieurs contributeurs, il n'y a pas de gate humain intermédiaire)
- Éditer les versions à la main (toujours via `scripts/bump.py`)
- Pousser directement sur `main` (interdit — tout passe par la PR)
- Créer ou configurer le service Railway lui-même (suppose qu'il existe déjà et redéploie tout
  seul sur push `main` — voir le skill `railway` pour la partie infrastructure)
- Forcer la mise à jour d'un nœud hors ligne ou bloquer dessus (mise à jour autonome, à sa
  prochaine reconnexion)
