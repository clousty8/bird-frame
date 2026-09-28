# Synthèse — par où commencer (21/09/2026)

Lire ce fichier en premier. Détail dans `01-panorama-projets.md`, `02-materiel.md`,
`03-pieges-et-retours.md`. Les fichiers `02b` à `02e` sont des brouillons partiels dont
**les prix sont faux** — ils ne servent que pour les aspects techniques.

## 1. Le choix de base : Fugleramme, pas Inky Bird Frame

| | Fugleramme | Inky Bird Frame |
|---|---|---|
| Étoiles GitHub (vérifié) | **3216** | 189 |
| Machines | 1 | 2 (cadre + contrôleur) |
| Détection | Audio locale, chez toi | Aucune — agrège des observations tierces |
| Dépendance réseau | Optionnelle | Obligatoire + abonnement ChatGPT payant |
| Stabilité déclarée | releases régulières | pas encore en v1.0 (issue #264 « soak test ») |

Les deux sont nés en juillet 2026 et sont activement développés. Mais Fugleramme est plus simple,
plus autonome, et bâti sur **BirdNET-Go** — le moteur le plus actif de tout l'écosystème.

**Pour la France, un argument de plus** : Inky Bird Frame s'appuie sur eBird, alors que la
plateforme de référence française est **Faune-France** (LPO, ~90 000 contributeurs, 150 M de données)
— qui n'a pas d'API publique. On interrogerait donc une source peu dense localement.

## 2. L'écosystème audio — ne pas se tromper de dépôt

| Dépôt | Statut | À faire |
|---|---|---|
| `mcguirepr89/BirdNET-Pi` | 🔴 **archivé** (17/08/2025) | Ne pas utiliser. C'est pourtant le plus documenté sur le web — piège des vieux tutos. |
| `Nachtzuster/BirdNET-Pi` | 🟠 fork semi-actif (dernier commit 02/2026) | Alternative acceptable |
| `tphakala/birdnet-go` | 🟢 **commits quotidiens, 2158 ★** | **C'est celui-là.** Utilisé par Fugleramme. |

## 3. Le plan en trois étapes

### Étape 0 — Valider sans rien acheter (0 à 44 €)
BirdNET-Go publie des images Docker `amd64`/`arm64` et a sa propre interface web.
**Le faire tourner sur le Mac avant tout achat.** Avec le micro intégré pour un premier test,
ou un Boya BY-LM40 (43,90 €) qui resservira tel quel ensuite — aucun argent perdu.

Ça valide que la détection marche chez toi. Ça ne valide ni le 24/7 en extérieur, ni l'écran.

### Étape 1 — Régler AVANT de construire
- Seuil de confiance à **0.5-0.7** (défaut 0.1 = inutilisable).
- Constituer la liste d'exclusion locale dès le premier mois d'écoute.
- Attention : BirdNET-Go a un **seuil dynamique** qui abaisse automatiquement le seuil d'une
  espèce déjà détectée — on croit à un bug (issue #239).

### Étape 2 — Le matériel, une fois convaincu
Voir les BOM chiffrées dans `02-materiel.md`. Ordres de grandeur : **~500 € minimum, ~710 € confortable**.

## 4. Les deux vrais obstacles

### A. L'écran est introuvable
L'Inky Impression 13,3" est **en rupture partout en UE** au 21/09/2026 (Berrybase 299,90 € indisponible,
The Pi Hut £229,50 en rupture, absent de Kubii et MC Hobby, précommande chez Pimoroni).

Trois sorties :
1. **Attendre le réassort** du Pimoroni 13,3".
2. **Pimoroni 7,3"** — natif dans Inky Bird Frame, layout à refaire pour Fugleramme.
3. **Waveshare 13,3" Spectra 6** (259,90 €, en stock chez Berrybase) — ⚠️ **panneau identique mais
   librairie incompatible**. Les deux projets utilisent la lib `inky` de Pimoroni, qui auto-détecte
   le panneau via une **EEPROM propre aux cartes Pimoroni**. Un Waveshare impose de réécrire toute
   la couche d'affichage. Ce n'est pas « juste un écran e-ink ».

### B. Les prix Raspberry Pi ont explosé en 2026
Crise mondiale DRAM/NAND : trois hausses officielles en 2026, **+83 % sur le Pi 5 4 Go, +119 % sur le 8 Go**.
Chez Kubii au 21/09/2026 : Pi 5 4 Go à **130,50 € (rupture)**, Pi 4 4 Go à **117 € (précommande)** —
soit quasiment le même prix. Le Zero 2 W est à 19,50 € catalogue mais **en pénurie européenne** ;
méfiance envers les revendeurs tiers qui le vendent 100 €+.

**Corollaire** : tout budget trouvé dans un article d'avant 2026 est obsolète.

## 5. Les pièges à connaître avant de commencer

| # | Piège | Parade |
|---|---|---|
| 1 | Défaut BirdNET = avalanche de faux positifs | Seuil 0.5-0.7 dès l'install |
| 2 | Faux positifs **récurrents et prévisibles** : klaxon → Cygne trompette à 95 %, feu d'artifice → Bihoreau gris, aboiement → Grand corbeau | Liste d'exclusion locale |
| 3 | BirdNET n'est **pas déterministe** : même fichier analysé 5×, le Pigeon ramier sort 1 fois sur 5 | Ne pas surinterpréter une détection isolée |
| 4 | Le modèle contient des **insectes** (grillon dans les étiquettes v2.4) | Normal, pas un bug |
| 5 | **BirdNET-Go ne supporte plus le Pi Zero 2 W ni le Pi 3** (wiki officiel) | Pi 4 2 Go minimum, 4 Go conseillé |
| 6 | Le Pi 5 exige une alim **USB-C PD 27 W (5 V/5 A)** ; sous-alimenté il throttle **et corrompt la carte SD** | Alim officielle, 12,90 € |
| 7 | Écriture continue → **carte SD morte** (issues #1131, #859, #716) | Carte High Endurance / Surveillance / Dashcam, V30+, <80 % de remplissage ; ou NVMe via M.2 HAT+ (14,10 €) |
| 8 | Bookworm puis Trixie cassent `RPi.GPIO` | `gpiozero`/`lgpio` uniquement |
| 9 | Le 13,3" met **20-35 s** à se rafraîchir, pas 12 s — bug de polarité BUSY, `show()` rend la main ~19 s trop tôt (pimoroni/inky#266) | 1 rafraîchissement/minute max (recommandation Pimoroni) |
| 10 | La dalle est « extrêmement fragile » (dixit Pimoroni) | Gants, ne jamais appuyer |
| 11 | Le **micro USB disparaît après reboot**, sans erreur dans les logs | Identifier par ID USB stable, jamais par index `hw:N` ; superviser l'absence de signal |
| 12 | **L'étanchéité du micro n'a aucune solution commerciale** — « surprisingly hard to find ». C'est *la* raison principale d'abandon | Abriter sous un avant-toit ; l'emballer dans du plastique étouffe le son qu'on veut capter |
| 13 | BirdWeather peu fiable : stats à zéro, 403, gel complet à l'activation (#114) | Le traiter comme bonus, jamais comme brique centrale |
| 14 | Le RÖDALM ne laisse que **3 cm de profondeur** | Pas de place pour empiler un HAT PoE/NVMe — déporter le Pi via nappe GPIO |
| 15 | Nappe GPIO branchée à l'envers = Pi et/ou HAT grillés | Repérer la broche 1 |
| 16 | Coral USB TPU : dépôt Google **archivé (avril 2026)** | Ne pas en faire une brique d'un projet neuf |

## 6. Limites connues de Fugleramme lui-même (issues ouvertes)
- **#138** — les oiseaux blancs se fondent dans le fond e-ink, non résolu
- **#33 / #44** — catalogue d'illustrations centré Amérique du Nord, chantier européen en cours
- **#61** — Pi Zero 2 W non validé par le mainteneur
- Le README annonce une couverture « Scandinavie, îles britanniques, Europe centrale » → trous
  probables sur les espèces méditerranéennes.

## 7. Angle mort : le juridique
Aucune doctrine CNIL spécifique trouvée sur un micro extérieur captant en continu. L'**article 226-1
du code pénal** (captation de paroles privées sans consentement — 1 an, 45 000 €) est le cadre
plausible, mais c'est une extrapolation non confirmée par une source fraîche. À creuser avant une
installation extérieure permanente : ne pas orienter le micro vers une propriété voisine, garder le
filtre voix humaine activé, vérifier qu'aucune voix identifiable ne part sur BirdWeather.

## 8. Ce qu'il ne faut PAS faire maintenant
- **La détection par caméra** : WhosAtMyFeeder à l'arrêt depuis mai 2024, alternatives récentes
  (Hailo, BioCLIP) à 2-3 ★. Rien d'équivalent à BirdNET-Go. Excellent complément plus tard, pas un point de départ.
- **Répliquer l'architecture à deux machines** d'Inky Bird Frame : complexité + coût récurrent d'IA.
- **Acheter un Waveshare** en croyant que c'est interchangeable (voir §4.A).
