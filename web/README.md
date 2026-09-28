# bird-frame — web/

Frontend Vite + Svelte 5 (runes) + TypeScript strict + Tailwind v4. Squelette du lot
WP-04 étendu : ce que les quatre équipes de pages (tableau de bord, espèces, statistiques,
système) partagent pour travailler **en parallèle sans toucher aux mêmes fichiers**.

Contrat d'API suivi : `docs/api-contract.md`. Toute divergence entre ce README et le
contrat est tranchée par le contrat (règle de préséance §10.1).

## Commandes

```bash
npm install
npm run dev     # http://localhost:5173, proxy /api → http://localhost:8090
npm run build   # dist/
npm run test    # vitest run
npm run check   # svelte-check (TypeScript strict + Svelte)
```

## Règle « une équipe = ses fichiers »

Chaque équipe de page possède **un seul fichier** sous `src/routes/` et ne modifie que
celui-là pour livrer son lot :

| Équipe | Fichier(s) | Route(s) |
|---|---|---|
| Tableau de bord | `src/routes/DashboardPage.svelte` | `/`, `/dashboard` |
| Espèces | `src/routes/SpeciesPage.svelte`, `src/routes/SpeciesDetailPage.svelte` | `/species`, `/species/:name` |
| Statistiques | `src/routes/StatsPage.svelte` | `/stats` |
| Système | `src/routes/SystemPage.svelte` (+ ses propres composants sous `src/lib/components/system/` si besoin) | `/system`, `/system/nodes`, `/system/rules`, `/system/review`, `/system/false-negatives`, `/system/thresholds` |

**Tout le reste de `web/` (`src/App.svelte`, `src/lib/router.ts`, `src/lib/api/*`,
`src/lib/stores/*`, `src/lib/components/ui/*`, `src/styles/*`) est un bien commun.** Une
équipe qui a besoin d'y changer quelque chose (un nouveau composant générique, un champ
manquant dans `types.ts`, une route API oubliée dans `client.ts`) le fait, mais prévient
les autres équipes (le contrat `docs/api-contract.md` reste la source de vérité pour les
types/routes ; toute extension doit d'abord y être ajoutée). Ne jamais dupliquer le client
API ou le routeur dans une page.

## Carte des dossiers

```
web/
├── index.html
├── src/
│   ├── main.ts                     # point d'entrée (monte App.svelte)
│   ├── App.svelte                  # coquille : en-tête, navigation, SiteSelector, ThemeToggle
│   ├── vite-env.d.ts
│   ├── styles/
│   │   ├── tailwind.css            # copié/adapté de BirdNET-Go, voir NOTICE.md
│   │   └── schemes.css             # copié de BirdNET-Go, voir NOTICE.md
│   ├── lib/
│   │   ├── router.ts               # routeur maison (History API), pur TypeScript, testable sans DOM
│   │   ├── Link.svelte             # <Link to="..."> — navigation SPA
│   │   ├── api/
│   │   │   ├── types.ts            # types de réponses, repris tel quel du contrat §11
│   │   │   └── client.ts           # une fonction par route navigateur + helper SSE
│   │   ├── stores/
│   │   │   ├── auth.svelte.ts      # session (GET /auth/me, modale, 401 → connexion → rejeu)
│   │   │   ├── site.svelte.ts      # site courant (liste + sélection persistée)
│   │   │   └── theme.svelte.ts     # thème clair/sombre/système
│   │   ├── format.ts               # formatage partagé : formatNumber, pluralize/formatCount
│   │   │                           # (« 1 détection », « 2 438 détections »), formatLocalDate
│   │   ├── utils/
│   │   │   └── cn.ts               # utilitaire de classes CSS conditionnelles
│   │   └── components/
│   │       ├── ui/                 # génériques : CollapsibleSection, Card, Badge, Button,
│   │       │                       # LoadingSpinner, EmptyState, ErrorAlert (copiés/adaptés,
│   │       │                       # voir NOTICE.md)
│   │       ├── SiteSelector.svelte
│   │       ├── ThemeToggle.svelte
│   │       ├── SpeciesPhoto.svelte # <img> avec repli silhouette + retry léger
│   │       ├── AuthButton.svelte   # « Se connecter » / « Se déconnecter » (en-tête)
│   │       ├── LoginModal.svelte   # modale mot de passe (montée une fois par App.svelte)
│   │       └── AuthRequiredNotice.svelte # « Connexion requise » + lien vers la modale
│   └── routes/                     # UNE PAGE PAR ÉQUIPE — voir tableau ci-dessus
│       ├── DashboardPage.svelte
│       ├── SpeciesPage.svelte
│       ├── SpeciesDetailPage.svelte
│       ├── StatsPage.svelte
│       └── SystemPage.svelte
├── tests/                          # vitest (routeur, store de site, client API, coquille, NOTICE.md)
├── NOTICE.md                       # attribution des fichiers copiés de BirdNET-Go
└── package.json
```

## Langue et thème

- Compteurs affichés : toujours `formatCount(n, 'détection')` (ou `pluralize`) de
  `src/lib/format.ts` — jamais `{n} détections` en dur ni `(s)`.
- Couleurs d'état en **texte** (vert/ambre/rouge/bleu sur fond clair ou sombre) :
  `var(--color-success-text)` etc., pas `var(--color-success)` (contraste insuffisant).
- Accordéon : classes `.collapsible*` (jamais `collapse`, qui est l'utilitaire Tailwind
  `visibility: collapse`).

- Interface entièrement en **français**, chaînes en dur (pas de système i18n pour
  l'instant — décision du lead, cf. `CLAUDE.md`).
- Thème clair/sombre : préférence système par défaut, bouton dans l'en-tête pour la forcer
  (système → clair → sombre), persisté en `localStorage` (`bird-frame:theme`).

## Store de site

`src/lib/stores/site.svelte.ts` charge `GET /api/v1/sites` une fois (`siteStore.load()`,
appelé par `SiteSelector` au montage) et persiste le slug choisi dans `localStorage`
(`bird-frame:selected-site`). Toute page qui a besoin du site courant lit
`siteStore.selectedSlug` (ou `siteStore.selectedSite` pour l'objet complet) — ne pas
relire `GET /sites` depuis une page.

## Session (mot de passe pour modifier et écouter)

Contrat §2.2 : lecture libre, session requise pour toute modification et pour écouter les
enregistrements. `src/lib/stores/auth.svelte.ts` charge `GET /auth/me` au démarrage
(`authStore.load()`, App.svelte) ; `authStore.unlocked` vaut `true` si l'authentification est
désactivée (serveur de dev sans mot de passe) ou si une session est ouverte — tant que
`/auth/me` n'a pas répondu, tout reste verrouillé.

- Contrôle qui modifie, déconnecté : désactivé (un `<fieldset disabled>` suffit pour un
  formulaire) + `<AuthRequiredNotice action="…" />` au-dessus (mention « Connexion requise » et
  lien qui ouvre la modale).
- Écoute : sans `unlocked`, ne jamais rendre d'`<audio>` (il préchargerait l'URL protégée) ;
  `RecordingItem.svelte` affiche un cadenas « Connecte-toi pour écouter ».
- Toute réponse 401 `auth_required` d'un appel du client ouvre la modale ; après connexion la
  requête est rejouée une fois, sinon l'erreur remonte normalement à la page.
- Tests : `src/test/setup.ts` met le store en « authentification désactivée » avant chaque test
  (comme le serveur de dev) ; un test d'auth fixe l'état voulu avec `authStore._resetForTests(…)`.

## Client API

`src/lib/api/client.ts` centralise **tous** les appels HTTP vers le serveur (contrat §6).
Toute erreur (réseau, HTTP non-2xx, JSON invalide) lève une `ApiRequestError` — jamais
avalée en silence ; les pages doivent l'attraper et afficher `ErrorAlert`. Le flux SSE
« en écoute » (`GET /sites/{slug}/pending/stream`) a son propre helper,
`subscribeToPending()`, qui retourne une fonction de désabonnement.

## Ajouter un fichier copié de BirdNET-Go

1. Copier le fichier depuis `birdnet-go-ui/frontend/`.
2. Ajouter l'en-tête de licence en tête de fichier (voir n'importe quel fichier de
   `src/lib/components/ui/` pour le format exact selon le type de fichier — commentaire
   `<!-- -->` en Svelte, `//` en TypeScript, `/* */` en CSS).
3. Ajouter une ligne dans `NOTICE.md`.
4. `npm run test -- notice.test.ts` doit rester vert.
