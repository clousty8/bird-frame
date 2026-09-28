# Étape 0 — BirdNET-Go sur le micro du Mac

Détection d'oiseaux en temps réel avec le micro intégré du MacBook, résultats dans le navigateur.
Aucun achat, aucun Raspberry Pi, aucune installation système.

## Démarrer / arrêter

```bash
./start.sh     # démarre, affiche le micro utilisé et l'URL
./stop.sh      # arrête
./check-mic.sh # vérifie que le micro capte bien (silence, saturation, stéréo/mono)
./deploy-ui.sh # recompile et met en ligne l'interface modifiée (voir plus bas)
```

Puis ouvrir **http://localhost:8080**

Le serveur tourne en tâche de fond : il survit à la fermeture du terminal.
`./stop.sh` est le seul moyen propre de l'arrêter.

## ⚠️ À CORRIGER EN PREMIER : ta localisation

> **Réglage actuel : Pornic** (depuis le 26/09/2026) — `latitude: 47.1155`, `longitude: -2.1046`
> (mairie, geo.api.gouv.fr / INSEE 44131), 198 espèces retenues. La section ci-dessous décrit le
> réglage d'origine sur Le Mans, conservé dans la sauvegarde du lieu 1. À Pornic la longitude est
> **négative** (à l'ouest de Greenwich).

BirdNET filtre les espèces selon ta position et la semaine de l'année. Pour Le Mans en
semaine 38, il passe de 6522 espèces possibles à **189**. Une position fausse = des espèces
réelles écartées, ou des espèces impossibles acceptées.

**Fichier `config.yaml`, lignes 213 et 214** — réglé sur **Le Mans** (centre communal officiel,
source geo.api.gouv.fr / INSEE 72181) :

```yaml
    longitude: 0.1957
    latitude: 47.9819
```

189 espèces retenues pour Le Mans en semaine 38 (contre 184 pour Paris : les espèces côtières
comme le Fulmar boréal ou la Mouette tridactyle entrent, l'Atlantique étant plus proche).

Pour affiner à ton adresse exacte : clic droit sur Google Maps → le premier chiffre est la
latitude, le second la longitude. **La longitude du Mans est positive** (+0.19, à l'est de
Greenwich, mais de peu) — un signe négatif te placerait dans l'Atlantique. Puis
`./stop.sh && ./start.sh`.

## Ce qui a été réglé, et pourquoi

| Réglage | Ligne | Valeur | Raison |
|---|---|---|---|
| `threshold` | 211 | `0.6` | Seuil de confiance. En dessous de 0.5 → avalanche de faux positifs. Au‑dessus de 0.7 → tu rates des oiseaux réels. |
| `locale` | 217 | `fr` | Noms d'espèces en français dans l'interface. |
| `gain` | 257 | `0` depuis le passage au HyperX QuadCast 2 (`15` avec le micro intégré) | **Réglage le plus sensible.** Avec le QuadCast, régler plutôt le gain sur la molette du micro. Voir ci‑dessous. |
| `device` | 256 | `"HyperX QuadCast 2"` (avant : `sysdefault`) | Nom exact du micro, tel que macOS l'affiche. Ne jamais mettre un index numérique : ils se décalent dès qu'un casque Bluetooth se connecte. |
| `privacyfilter` | 398 | `true` | Supprime les détections quand une voix humaine est présente. |
| `fallbackpolicy` | 336 | `all` | Si la banque de photos avicommons n'a pas l'espèce (ex. Goéland argenté), prendre la photo sur Wikipédia/Wikimedia. |

### Régler le gain

`gain: 15` (ligne 257) a été validé en test. À ajuster selon ce que tu observes :

- **Rien n'est jamais détecté** alors que tu entends des oiseaux → monte à `20` ou `25`.
- **Beaucoup de détections farfelues**, ou détections de « Engine », « Siren » → descends à `5` ou `0`.

Après chaque modification : `./stop.sh && ./start.sh`.

Pour de vrais oiseaux dehors, **ouvre la fenêtre** et pose le Mac près d'elle. Une vitre fermée
coupe l'essentiel des aigus, qui sont précisément la bande des chants (2–8 kHz).

## Vérifier que la chaîne est vivante

Trois signes, dans l'ordre :

1. `./start.sh` affiche `Micro utilisé : MacBook Air Microphone` (ou ton micro externe).
2. Dans l'interface, **Live Spectrogram** bouge quand tu fais du bruit. Si le spectrogramme est
   plat et noir, le Mac ne capte rien : vérifie Réglages Système → Confidentialité et sécurité →
   Microphone.
3. Détections dans la base :
   ```bash
   curl -s "http://localhost:8080/api/v2/detections?limit=10" | python3 -m json.tool
   ```

Aucune détection ne veut **pas** dire que c'est cassé : si aucun oiseau ne chante, il n'y a rien
à détecter. Utilise le spectrogramme pour distinguer « rien à entendre » de « chaîne cassée ».

## À savoir avant de t'inquiéter

- **Seuil dynamique** : BirdNET-Go abaisse automatiquement le seuil d'une espèce déjà détectée.
  Tu verras donc des détections **sous** 0.6. Ce n'est pas un bug (issue #239 du projet).
- **Non déterministe** : le même son analysé plusieurs fois ne donne pas toujours le même
  résultat. Ne surinterprète jamais une détection isolée.
- **Faux positifs prévisibles** : klaxon → Cygne trompette, aboiement → Grand corbeau,
  feu d'artifice → Bihoreau gris. Un filtre anti‑aboiement est déjà actif.
- Le modèle contient aussi des **insectes** et des bruits non biologiques (« Engine », « Siren »).

## Surveillance du micro

Si le micro de `config.yaml` disparaît un instant (débranché, coupure USB), **macOS bascule la
capture de BirdNET-Go sur le micro du Mac sans prévenir**, et ne revient jamais en arrière quand le
micro réapparaît. BirdNET-Go ne s'en rend pas compte : son journal continue d'afficher le QuadCast.
C'est arrivé le 26/09 à 16h43 : 349 détections jusqu'à minuit faites avec le micro du Mac.

`mic-watchdog.sh` (lancé par `./start.sh`, arrêté par `./stop.sh`) demande chaque minute à macOS
quel micro BirdNET-Go utilise vraiment (`tools/mic-status <PID>`). Si ce n'est pas le bon alors que
le bon est branché, il relance BirdNET-Go. Journal : `data/mic-watchdog.log`.
`./start.sh` et `./check-mic.sh` affichent aussi le micro réellement utilisé.

## Audio : seulement les 10 meilleures détections par espèce

`clip-retention.py` tourne en boucle (toutes les 10 min) dès `./start.sh`, et s'arrête avec
`./stop.sh`. Pour chaque espèce, il ne garde le clip audio et les spectrogrammes que des 10
détections de plus forte confiance. **Toutes les détections restent en base** (compteurs et
graphiques justes) ; les autres n'ont simplement plus d'audio à écouter. Il supprime aussi les
clips orphelins (sans détection en base). Les détections **verrouillées** dans l'interface gardent
toujours leur audio. Rien n'est touché avant 30 min, pour ne pas gêner un clip en cours d'écriture.

```bash
./clip-retention.py --dry-run   # voir ce qui serait supprimé
tail data/clip-retention.log    # journal des passages
```

## Interface modifiée (fork)

Le code de l'interface vient du fork **github.com/clousty8/birdnet-go**, branche `bird-frame`,
cloné dans `../birdnet-go-ui`. Changements : grande photo de l'oiseau partout, spectrogramme
affiché seulement quand on écoute l'enregistrement.

Seule l'interface web (Svelte) est modifiée, pas le binaire : BirdNET-Go sert `data/frontend/dist`
s'il existe, à la place de l'interface embarquée. `./deploy-ui.sh` la recompile et la copie là.

- La branche doit partir du **même tag que le binaire** (`20260823` aujourd'hui), sinon
  `deploy-ui.sh` refuse. Pour mettre à jour BirdNET-Go : nouveau binaire, puis
  `git rebase --onto <nouveau-tag> 20260823 bird-frame` dans `../birdnet-go-ui`.
- Revenir à l'interface officielle : supprimer `data/frontend/`, puis `./stop.sh && ./start.sh`.

## Structure

```
local-test/
├── start.sh / stop.sh     scripts de démarrage et d'arrêt
├── check-mic.sh           diagnostic du micro (10 s d'enregistrement)
├── clip-retention.py      ne garde l'audio que du top 10 par espèce (lancé par start.sh)
├── mic-watchdog.sh        relance BirdNET-Go si macOS l'a basculé sur un autre micro (lancé par start.sh)
├── tools/mic-status.swift quel micro un processus utilise vraiment (compilé en tools/mic-status)
├── deploy-ui.sh           compile ../birdnet-go-ui et le sert à la place de l'interface d'origine
├── sauvegardes/           bases des lieux précédents (une par lieu)
├── config.yaml            TOUS les réglages (localisation ligne 213-214)
├── bin/                   binaire officiel darwin-arm64 + ses 2 bibliothèques
├── data/                  base de données, clips audio, logs, frontend/ (interface modifiée)
└── preuves/               captures d'écran des tests de validation
```

Pour tout désinstaller : `./stop.sh` puis supprimer ce dossier. Rien n'a été installé ailleurs
sur la machine.

## Note technique

Le binaire officiel de BirdNET-Go pour macOS est livré sans `LC_RPATH`, donc il ne trouve pas ses
propres bibliothèques. Le contournement documenté par le projet (`DYLD_LIBRARY_PATH`) ne survit
pas à `nohup`, que macOS neutralise par SIP. Un `rpath` relatif a donc été ajouté au binaire :

```bash
install_name_tool -add_rpath @executable_path bin/birdnet-go
codesign -f -s - bin/birdnet-go
```

À refaire si tu remplaces le binaire par une version plus récente.
