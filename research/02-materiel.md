# Matériel — cadre e-ink oiseaux (France, 2026)

> Recherche effectuée le 21/09/2026 par recherche web directe (WebSearch/WebFetch), sans sous-délégation. Tout prix marqué **[ESTIMATION]** n'a pas été vu tel quel sur une page produit — à vérifier avant achat. Tout prix sans cette mention a été relevé sur une page consultée pendant cette recherche (date de consultation indiquée). Le contexte 2026 (pénurie mémoire, hausses de prix Raspberry Pi, tensions d'approvisionnement sur les écrans Inky) rend ces informations volatiles : à revérifier avant tout achat réel.

## 1. Écran e-ink

### Point clé de compatibilité logicielle

Les deux projets de référence pilotent l'écran via la librairie Python **`inky` de Pimoroni**
(confirmé dans le code des deux repos : Fugleramme référence explicitement le PIM774 13,3"
Spectra 6, Inky Bird Frame dit texto « needs Pimoroni's Inky package » et supporte PIM774 et
PIM773). Cette librairie **auto-détecte le panneau via une puce EEPROM présente sur les cartes
Pimoroni** — c'est ce qui permet au code de fonctionner sans configuration. Les écrans
**Waveshare n'ont pas cette EEPROM Pimoroni** et nécessitent leur propre librairie Python
(`Waveshare EPD`), différente en API : brancher un Waveshare à la place d'un Inky Impression
**ne marchera pas tel quel**, il faut réécrire la couche d'affichage (`display_manager.py` côté
Inky Bird Frame, module équivalent côté Fugleramme). Les alternatives Waveshare ci-dessous sont
donc moins chères mais représentent un vrai chantier logiciel, pas un simple achat de rechange.

### Pimoroni Inky Impression 13,3" (PIM774) — écran de référence des deux projets

- **Génération actuelle = « 2025 Edition »**, panneau **E Ink Spectra 6** (6 couleurs :
  rouge, vert, bleu, jaune, noir, blanc), 1600×1200, rafraîchissement ~12 s annoncé (jusqu'à
  19 s en rafraîchissement complet selon la fiche Waveshare du même type de dalle).
  Remplace l'ancienne génération ACeP 7 couleurs (~30 s de rafraîchissement).
- **Prix vus** :
  - The Pi Hut (UK) : **£229,50 TTC**, **en rupture** (page « sold out ») — vue le 21/09/2026.
  - Berrybase (DE) : **299,90 €**, **indisponible** (« notify me ») — vue le 21/09/2026.
  - Boutique Pimoroni directe (UK) : affichée en **pré-commande**, prix non capturé par la
    recherche automatisée — à vérifier manuellement sur shop.pimoroni.com.
- **Disponibilité générale fin 2026 : tendue.** Plusieurs boutiques (Pi Hut, Berrybase,
  Pimoroni lui-même) affichent rupture ou pré-commande sur ce modèle au moment de la recherche.
  Ce n'est pas une fin de vie annoncée (le produit existe toujours au catalogue, contrairement
  au 5,7" ci-dessous), mais l'approvisionnement est manifestement irrégulier.
- **Achat depuis la France** : aucun revendeur français (Kubii, MC Hobby) ne semble stocker le
  13,3" au moment de la recherche (non trouvé dans leurs catalogues). Les options restent donc
  Pimoroni UK / The Pi Hut UK (post-Brexit → TVA française + frais de dédouanement/traitement à
  l'arrivée, en plus du prix affiché HT/TTC UK) ou Berrybase (Allemagne, UE — pas de douane,
  TVA déjà incluse dans les 299,90 €).

### Pimoroni Inky Impression 7,3" (PIM773) — alternative moins chère, supportée par Inky Bird Frame

- **2025 Edition**, même panneau Spectra 6, 800×480, 6 couleurs, ~12 s de rafraîchissement.
- **Prix vu** : The Pi Hut (UK) **£79,50 TTC**, stock très faible (« 6 units remaining ») —
  vu le 21/09/2026.
- Explicitement mentionné dans le README d'Inky Bird Frame comme alternative « smaller build »,
  qui « fits the complete canonical plate without cropping or stretching ». Compatible logiciel
  garanti (même librairie `inky`, même EEPROM Pimoroni).
- Pas d'équivalent confirmé côté Fugleramme (le repo ne mentionne que le 13,3" dans les extraits
  consultés) — probablement adaptable mais non testé par l'auteur du projet à ma connaissance.

### Pimoroni Inky Impression 5,7" — discontinué

- Ancien panneau ACeP 7 couleurs (noir, blanc, rouge, vert, bleu, jaune, orange), 600×448,
  ~30 s de rafraîchissement.
- **Retiré du catalogue Pimoroni** : la fiche produit officielle affiche « We no longer stock
  this product » — vue le 21/09/2026. The Pi Hut affiche la fiche « [Discontinued] » avec un
  dernier prix connu de £63,50.
- Encore trouvable en stock résiduel chez certains revendeurs hors UE (Core Electronics
  Australie, Vilros US) mais pas identifié chez un revendeur européen fiable — à éviter comme
  base d'achat pour un projet en France en 2026.

### Waveshare 13,3" Spectra 6 (E6) — alternative Waveshare la plus proche du PIM774

- Même génération de dalle E Ink Spectra 6, 1600×1200, 6 couleurs, rafraîchissement complet
  annoncé à 19 s (12 s en rafraîchissement partiel) selon la fiche produit Waveshare.
- **Prix vus** :
  - **Berrybase (DE) : 259,90 € TTC, EN STOCK (17 unités, livraison 1-3 jours)** — vu le
    21/09/2026. C'est aujourd'hui l'option la plus simple pour obtenir *un* écran 13,3" 6
    couleurs livrable depuis l'UE sans attente.
  - Waveshare (Chine, boutique officielle) : 249,99–259,99 USD selon variante (avec/sans carte
    pilote) — vu le 21/09/2026. Import hors UE : TVA + douane à ajouter.
- **Rappel** : ne fonctionne PAS avec le code des deux projets sans réécriture de la couche
  d'affichage (voir point de compatibilité plus haut).

### Waveshare 7,3" ACeP 7 couleurs — alternative bon marché, ancienne techno

- Panneau ACeP (7 couleurs dont orange), 800×480, plus lent à rafraîchir que le Spectra 6
  (l'ACeP est réputé pour des rafraîchissements de l'ordre de 30 s, comme l'ancien Inky 5,7").
- **Prix vu** : Opencircuit.shop (Pays-Bas, UE) **~94 € [prix vu via résultat de recherche,
  page produit non re-vérifiée directement — à confirmer avant achat]**.
- Même limitation logicielle que le 13,3" Waveshare : pas de driver `inky` Pimoroni, réécriture
  nécessaire.

### Synthèse compatibilité par écran

| Écran | Marche avec le code des 2 projets sans modif ? |
|---|---|
| Inky Impression 13,3" (PIM774, toute génération) | Oui — référence de Fugleramme et supporté par Inky Bird Frame |
| Inky Impression 7,3" (PIM773) | Oui — supporté explicitement par Inky Bird Frame |
| Inky Impression 5,7" (discontinué) | Oui en théorie (même librairie `inky`) mais produit quasi introuvable neuf en UE |
| Waveshare 13,3" Spectra 6 (E6) | Non sans réécrire la couche d'affichage |
| Waveshare 7,3" ACeP | Non sans réécrire la couche d'affichage |

## 2. Raspberry Pi et accessoires

### Contexte 2026 : pénurie et flambée des prix

Recherche importante à connaître avant de budgéter : **les prix Raspberry Pi ont fortement
augmenté en 2026** suite à la crise mondiale des prix de la mémoire DRAM/NAND. Selon un article
de Comptoir du Hardware et une brève de Hardware & Co (vues le 21/09/2026), la Raspberry Pi
Foundation a relevé ses tarifs officiels trois fois en 2026 (déc. 2025, fév. 2026, avril 2026) :
le Pi 5 4GB est passé à environ 110 USD officiel (+83% vs 2025), le Pi 5 8GB à ~175 USD
(+119%). Le Pi Zero 2 W est en outre **en pénurie généralisée en Europe** au moment de la
recherche (Pimoroni UK vide, revendeurs allemands « incoming » sans date, cf. raspberry.tips,
vu le 21/09/2026) — se méfier des vendeurs tiers qui surfacturent largement un Zero 2 W à plus
de 100 € sur Amazon quand le prix catalogue est ~19,50 €.

Conséquence concrète, vue directement sur **Kubii (revendeur agréé France)** le 21/09/2026 :
- Raspberry Pi 5 **4GB : 130,50 €**, en rupture de stock.
- Raspberry Pi 5 8GB/16GB : prix non affiché, indiqués « en cours de réapprovisionnement,
  livraison estimée mi-février 2026 » — **cette date semble antérieure à aujourd'hui et donc
  suspecte/obsolète sur la page** ; à vérifier en direct avant tout achat, ne pas s'y fier.
- Raspberry Pi 4 Model B **4GB : 117,00 €**, en précommande (quasiment au prix d'un Pi 5 !).
- Raspberry Pi Zero 2 W : **19,50 €** catalogue mais **en rupture de stock**.

**Implication pratique** : au moment de cette recherche, se procurer *n'importe quel* Raspberry
Pi neuf et en stock immédiat en France est incertain. Il faut vérifier la disponibilité réelle
au moment de l'achat plutôt que de se fier à un prix affiché.

### Quel Pi pour quel usage

- **BirdNET-Go (voie Fugleramme, détection audio locale) ne supporte plus le Pi Zero 2 W ni le
  Pi 3** selon le wiki matériel officiel du projet (`tphakala/birdnet-go` wiki « hardware »,
  vu le 21/09/2026) : "Raspberry Pi 3 and Pi Zero are no longer supported."
  - **Pi 4** : 2 Go RAM minimum, 4 Go recommandé. Le wiki confirme explicitement que le
    classificateur par défaut (BirdNET v2.4) « runs well on Raspberry Pi 4B with 2GB and
    above » → **oui, un Pi 4 suffit pour du BirdNET temps réel « standard »**. Les limites
    apparaissent avec des fonctionnalités avancées (Deep Detection, plusieurs flux RTSP
    simultanés, modèles multiples type Google Perch) où le Pi 4 devient plus juste.
  - **Pi 5** : 2 Go suffisant pour un usage standard, 4 Go recommandé si plusieurs modèles
    tournent en parallèle (BirdNET v2.4 + Perch + BattyBirdNET par ex.). Web UI plus réactive
    qu'un Pi 4.
- **Inky Bird Frame (voie agrégation iNaturalist/eBird, pas d'inférence locale)** : le **Pi Zero
  2 W convient**, comme dans le projet de référence — c'est un client léger qui interroge des
  API et pousse une image sur l'écran, pas un poste de calcul.

### Refroidisseur actif obligatoire pour BirdNET-Go sur Pi 5 ?

Pas de mandat absolu documenté, mais fortement recommandé en pratique :
- Le Pi 5 commence à throttler vers 80-82°C (seuil « soft »), throttling dur à 85°C
  (raspberrypi.com, forums officiels, vus le 21/09/2026).
- Pour toute charge CPU soutenue au-delà de quelques minutes, le refroidissement passif ne
  suffit pas à rester sous le seuil de throttling — c'est documenté indépendamment de BirdNET,
  c'est une caractéristique générale du Pi 5.
- Une discussion communautaire BirdNET-Go confirme que des fonctionnalités comme Google Perch
  peuvent tripler la charge CPU par rapport au modèle par défaut et faire « ramper » le
  ventilateur en continu — signe que la charge n'est pas négligeable en usage prolongé (24/7,
  ce qui est justement le mode de fonctionnement visé par un cadre oiseaux).
- **Conclusion pragmatique** : le ventilateur actif officiel ne coûte que **6,00 € chez Kubii**
  (en stock, vu le 21/09/2026) — au vu du prix dérisoire face au reste du budget, l'installer
  par défaut est une précaution peu coûteuse plutôt qu'un vrai point de blocage budgétaire,
  même si ce n'est pas à 100% "obligatoire" dans tous les climats/usages.

### Accessoires souvent oubliés — prix vus chez Kubii (revendeur France) le 21/09/2026

| Accessoire | Prix | Stock au moment de la recherche | Remarque |
|---|---|---|---|
| Alimentation officielle 27W USB-C PD (Pi 5) | **12,90 €** | En stock (1583 unités) | **Piège classique** : le Pi 5 exige une alim USB-C **Power Delivery** capable de fournir 5V/5A (27W). Un chargeur téléphone USB-C classique (souvent 5V/3A ou moins, ou PD mais mal négocié) peut sous-alimenter le Pi 5 → instabilités, throttling, redémarrages sous charge (typiquement au moment où le ventilateur/écran tirent du courant). Le Pi 4 et le Zero 2 W n'ont pas cette exigence (micro-USB / USB-C simple 5V/3A suffit). |
| Ventilateur/dissipateur actif officiel (Pi 5) | **6,00 €** | En stock (2570 unités) | Voir section refroidissement ci-dessus. |
| M.2 HAT+ officiel (NVMe, Pi 5) | **14,10 €** | En stock (340 unités) | Permet de faire booter/stocker sur un SSD NVMe plutôt qu'une carte SD — pertinent seulement si on veut éviter l'usure d'écriture continue de la carte SD (BirdNET-Go écrit en continu logs + clips audio). Non nécessaire pour un MVP. |
| Carte microSD haute endurance 64 Go (ex. SanDisk High Endurance) | **~21-25 €** [ESTIMATION basse fourchette vue sur des comparateurs de prix FR, non vérifiée sur une page produit unique] | — | **Point de vigilance documenté par la communauté BirdNET-Go elle-même** (wiki hardware) : une carte microSD grand public s'use vite avec les écritures continues et peut tomber en panne. Le wiki recommande explicitement des cartes classées « High Endurance », « Surveillance Grade » ou « Dashcam Rated » (SanDisk High Endurance, Samsung PRO Endurance, Western Digital Purple SC), V30 minimum, 64 Go ou plus, et de rester sous 80% de remplissage. C'est un problème connu et documenté, pas une inquiétude théorique. |
| Câble d'extension GPIO 40 broches (pour déporter l'écran du Pi) | Non trouvé avec prix précis chez un revendeur FR pendant cette recherche ; existe chez Pimoroni UK et Adafruit/Pi Hut, typiquement de l'ordre de **quelques euros à ~10 €** [ESTIMATION, non vérifiée sur une page produit] | — | Utile si on veut loger le Pi hors du cadre (dans un boîtier séparé derrière/au-dessus) plutôt que collé au dos de l'écran. Attention au sens de branchement (risque de griller le HAT/Pi si inversé, avertissement documenté par les fabricants). |
| Boîtier | Boîtier officiel Pi 5 ventilé : prix non capturé précisément lors de cette recherche (page consultée mais prix non extrait) ; boîtier aluminium Pi 5 également listé chez Kubii | — | Optionnel si le Pi est caché derrière l'écran dans le cadre (cas d'usage principal ici) — dans ce cas la coque du cadre fait office de boîtier et on peut s'en passer pour le MVP. |

### Synthèse Pi

| Voie du projet | Pi minimum viable | Pi confortable | Refroidissement |
|---|---|---|---|
| Fugleramme (BirdNET-Go, audio local) | Pi 4, 2 Go (4 Go conseillé) | Pi 5, 4 Go | Dissipateur passif tolérable en usage léger ; actif (6 €) recommandé pour un fonctionnement 24/7 fiable, surtout sur Pi 5 |
| Inky Bird Frame (agrégation API, pas d'inférence) | Pi Zero 2 W | Pi Zero 2 W (suffisant) ou un Pi 4/5 existant comme « serveur » si on veut aussi faire tourner BirdNET-Go dessus | Pas de besoin particulier, faible charge |

## 3. Micro (capture audio)

Cette section concerne uniquement la voie Fugleramme (BirdNET-Go) — Inky Bird Frame n'a pas
besoin de micro, il agrège des observations déjà publiées.

### Ce que dit la communauté BirdNET (wiki officiel BirdNET-Go + discussions BirdNET-Pi)

- Le wiki matériel officiel de BirdNET-Go (`tphakala/birdnet-go`, vu le 21/09/2026) recommande
  en entrée de gamme le **Boya BY-LM40** (micro-cravate USB) mais prévient qu'il **« n'est pas
  très sensible, le son capté est assez bas en volume »** — utilisable pour tester mais pas
  optimal. En haut de gamme il cite le **Clippy Ultra XLR** (capsule Primo EM272, très faible
  bruit de fond ~14 dBA, haute sensibilité), qui nécessite une interface XLR avec alimentation
  fantôme.
- Une discussion communautaire longue et bien documentée sur BirdNET-Pi
  (`mcguirepr89/BirdNET-Pi` discussion #39, vue le 21/09/2026) donne une hiérarchie de prix :
  - Entrée de gamme à éviter : micro-cravate chinois générique (~3 USD) — trop bruyant.
  - **Bon rapport qualité/prix largement cité : la capsule électret PrimoEM272 (ou équivalent
    PUI Audio AOM-5024L-HD-R) montée soi-même, ~15 USD la capsule**, ou déjà montée en « Mini
    Pluggy EM272 Omni » (~40 USD).
  - Milieu de gamme : Edutige EIM-001 (~90 €), T-Bone EM 9600 (~75 €).
  - Haut de gamme : RODE VideoMic NTG (~240 €), Sennheiser MKH8020 (jugé « too expensive » par
    la discussion elle-même).
  - Cartes son USB associées : adaptateur audio USB mono UGREEN (~10-20 USD) pour un micro
    jack simple, ou interface XLR type **Focusrite Scarlett Solo 3e gen (~130 €)** si on va
    vers un Clippy/EM272 en version XLR avec alimentation fantôme.
- Règle importante répétée dans plusieurs sources : **utiliser un micro mono**, pas stéréo — un
  micro stéréo peut introduire des erreurs de phase qui dégradent la détection.

### Solution Clippy / PrimoEM272 — la référence qualité/prix de la communauté

- Le nom « Clippy » désigne des micros-cravate électret construits autour de la capsule
  **Primo EM272** (fabriquée au Japon), reconnue pour son très faible bruit propre et sa
  sensibilité — vendus notamment par micbooster.com (UK) et, pour un revendeur francophone,
  **Le Club Biotope** (France, boutique naturaliste) qui propose le **Clippy EM272 XLR à 85,00 €
  TTC (mono)** — vu le 21/09/2026. Chez micbooster.com (UK), la fourchette va de £33,20 à
  £84,40 selon configuration (mono/stéréo, capsule) — vu le 21/09/2026, mais commande UK →
  friction douane/TVA post-Brexit à anticiper (voir pièges d'achat).
- Aucune de ces fiches produits consultées ne documente explicitement une **étanchéité**
  garantie du micro lui-même — la protection contre l'humidité est presque toujours assurée par
  le **logement/boîtier**, pas par le micro (voir ci-dessous), sauf mention contraire à vérifier
  au cas par cas avant achat.

### Sortir le micro dehors sans le noyer

Plusieurs sources convergent (BirdForum, GitHub issue #1001 sur BirdNET-Pi, guide Kindalame.com,
vus le 21/09/2026) :
- Solution DIY récurrente : boîtier électrique étanche **IP67** (type boîtier de jonction ABS,
  ex. « QILIPSU IP67 Project Box ») dans lequel on loge le micro, avec passages de câble
  étanchéifiés au silicone (presse-étoupes / bulkhead connectors).
- Le micro lui-même a besoin d'une **bonnette anti-vent** (mousse acoustique, ou solution DIY
  comme un morceau de mousse/chaussette, voire un pot de fleur retourné comme écran acoustique
  cité dans une des sources) pour réduire le bruit de vent sans trop filtrer le son utile.
- Le point de défaillance le plus souvent cité n'est pas la pluie directe mais la
  **condensation** sur la capsule — nécessite une ventilation minimale du boîtier plutôt qu'une
  étanchéité totale hermétique.
- Alternative « facile » mentionnée dans plusieurs guides communautaires : loger le micro sous
  un avant-toit / débord de toiture plutôt qu'en plein air, ce qui réduit drastiquement le
  besoin de boîtier étanche dédié.

### Faut-il une carte son USB ?

- Un micro USB « tout-en-un » (Boya BY-LM40, Samson Go Mic, etc.) n'a pas besoin de carte son
  séparée : il s'agit déjà d'un périphérique audio USB.
- Un micro électret classique (Clippy/EM272 en version jack 3,5 mm) a besoin d'un adaptateur
  audio USB (type UGREEN, quelques euros à ~20 €) pour être vu comme périphérique audio par le
  Pi.
- Un micro Clippy/EM272 en **version XLR** a besoin d'une vraie interface audio avec
  alimentation fantôme (12-48V), type Focusrite Scarlett Solo, plus chère (~130 €) mais offrant
  un gain/bruit nettement meilleur.

### Prix vus pour un micro USB simple (Boya BY-LM40)

- Galaxus.fr : **43,90 €** — vu le 21/09/2026 (prix le plus bas trouvé parmi les revendeurs FR
  cités par la recherche : Fnac ~62,39 €, Darty ~51,67 € en promo).

### Synthèse micro

| Option | Prix | Qualité attendue | Remarque |
|---|---|---|---|
| Boya BY-LM40 (USB direct) | ~44 € | Correcte pour tester, sensibilité limitée selon le wiki BirdNET-Go | Le plus simple à brancher, aucune carte son à ajouter |
| Capsule PrimoEM272 seule + montage DIY | ~15 USD la capsule [prix vu sur une discussion communautaire, pas une page boutique — à confirmer] | Très bon rapport qualité/bruit selon la communauté | Demande un peu de bricolage (soudure, câble blindé) |
| Clippy EM272 XLR monté (Le Club Biotope, FR) | 85,00 € | Référence qualité/bruit de la communauté | Nécessite une interface XLR à alimentation fantôme en plus |
| Interface Focusrite Scarlett Solo (si Clippy XLR) | ~130 € | — | Coût additionnel à ajouter au Clippy XLR |

## 4. Caméra (optionnel)

**Important à savoir avant tout achat sur ce poste : ni Fugleramme ni Inky Bird Frame n'utilisent
de caméra.** Confirmé en lisant les deux dépôts : Fugleramme est purement audio (BirdNET-Go +
micro), Inky Bird Frame est purement agrégation d'observations déjà publiées (iNaturalist/eBird)
via API. Une voie caméra/vision serait donc **un ajout expérimental de votre cru**, sans code de
référence à réutiliser — à budgéter comme une extension future plutôt que comme un besoin du MVP.

### Module caméra Raspberry Pi v3

- **Prix vu chez Kubii (FR) : 30,00 €**, en stock (396 unités) — vu le 21/09/2026. Capteur Sony
  IMX708, autofocus, 12 MP, existe en version standard (75°) et grand-angle (120°), ainsi qu'en
  version infrarouge (NoIR) pour la vision nocturne — pertinent si on veut aussi capter des
  passages d'oiseaux à l'aube/crépuscule sans éclairage additionnel.
- Se branche en CSI (nappe caméra dédiée), pas en GPIO — n'entre pas en conflit avec l'écran
  e-ink qui occupe le connecteur GPIO 40 broches.

### Caméras USB

Non creusé en détail dans cette recherche (hors périmètre du MVP identifié) — une webcam USB
générique fonctionnerait aussi sur un Pi sans mobiliser le port caméra dédié, mais aucune
donnée de prix précise n'a été vérifiée pour ce rapport.

### Google Coral USB Accelerator — statut en 2026 : à éviter pour un nouveau projet

- **Le dépôt GitHub officiel `google-coral/edgetpu` a été archivé le 19 avril 2026** (vu le
  21/09/2026) : plus aucune mise à jour, plus de support actif de la part de Google.
- Le stock neuf via les canaux officiels (coral.ai) est annoncé à zéro sur plusieurs listings ;
  ce qui reste disponible passe par des distributeurs tiers (pi3g.com en Europe, Seeed Studio,
  Mouser/RS) avec des réapprovisionnements irréguliers, ou le marché de l'occasion (eBay).
- Le matériel reste techniquement utilisable (compatible Linux/Mac/Windows, spécifications
  inchangées) mais **sans garantie de support logiciel à long terme** — à éviter comme socle
  pour un projet qui doit encore tourner dans plusieurs années. Si un accélérateur IA local
  s'avère nécessaire pour une future voie « identification visuelle », il vaudrait mieux
  regarder du côté d'alternatives activement maintenues en 2026 plutôt que de miser sur du
  matériel dont l'écosystème logiciel est à l'arrêt (non investigué en détail ici, hors
  périmètre de la mission).

### Recommandation pratique

Ne pas inclure la caméra ni le Coral dans le BOM minimum viable ou confort — les mentionner
comme piste d'extension future si le projet évolue vers une identification visuelle, en gardant
à l'esprit que ce serait un développement logiciel à part entière, pas un simple ajout matériel.

## 5. Cadre et mécanique

### Ça rentre vraiment ?

**Oui, confirmé directement sur la page d'assemblage officielle du projet Fugleramme**
(`arnegiacomo.dev/fugleramme/hardware/`, vue le 21/09/2026) :
- La carte Inky Impression 13,3" mesure **exactement 297 × 210 mm — c'est-à-dire le format A4
  pile poil.**
- Le cadre **IKEA RÖDALM 21×30 cm (6,99 €, vu sur ikea.com/fr le 21/09/2026)** propose une
  ouverture **sans passe-partout de 30 × 21 cm**, soit une correspondance quasi exacte avec le
  panneau (3 mm d'écart sur la longueur, invisible une fois le passe-partout en place).
- Profondeur du cadre : **3 cm**, décrite par l'auteur du projet comme « tout juste assez
  profonde pour que le Pi tienne à l'intérieur sans toucher le mur » — c'est un montage serré,
  pas confortable, mais ça rentre.

### Découpe du passe-partout

Instructions précises données par Fugleramme, à reproduire :
- Découper **20 mm sur les côtés courts, 15 mm sur les côtés longs** — cette marge cache le
  cadre/bezel du panneau et le bord de la carte électronique sans trop empiéter sur l'image
  affichée.
- Conseil pratique de l'auteur : découper « en plusieurs passes légères plutôt qu'une seule
  entaille profonde », et **prévoir des passe-partout de rechange** (« recommended from
  experience » — sous-entendu : on en rate au moins un).

### Fixation du Pi derrière l'écran

- Le Pi se visse directement sur le panneau Inky via **les vis fournies** avec l'écran.
- L'entretoise plastique fournie avec le cadre RÖDALM sert de cale, serrée contre les fixations
  métalliques du cadre.
- **Point de vigilance thermique explicite du projet** : ne pas fermer complètement l'arrière du
  montage. Citation : « the constant BirdNET inference gets them quite hot. Don't close the back
  up. » → **laisser le panneau arrière du cadre absent, ou y percer une large ouverture** pour
  la ventilation. Des patins en caoutchouc aux coins arrière donnent un peu de jeu par rapport
  au mur.

### Alternatives de cadre en France

- **IKEA RÖDALM 21×30 cm** reste la référence la plus simple : disponible en France
  (ikea.com/fr), 6,99 €, existe en plusieurs finitions (blanc, noir, motif bouleau, motif chêne).
- **Action (FR)** propose un « Cadre photo avec passe-partout – 21 x 29,5 cm » (vu dans les
  résultats de recherche, page produit non accessible directement pour vérifier le prix — HTTP
  403 lors de la tentative de consultation le 21/09/2026, **prix non confirmé, à vérifier en
  magasin ou sur action.com**), même format que le RÖDALM, probablement dans une gamme de prix
  similaire (Action est positionné comme discount).
- Toute solution « cadre photo A4 avec passe-partout, minimum ~3 cm de profondeur » fonctionne
  en théorie — le point dur n'est pas la référence exacte mais la **profondeur intérieure** (il
  faut au moins ~3 cm pour loger le Pi) et l'ouverture proche de 297×210 mm.
- Pour l'écran 7,3" (plus petit, 800×480 px physiquement plus compact), le choix de cadre est
  moins contraint — un cadre plus petit et moins profond suffit, mais aucune dimension précise
  n'a été vérifiée dans cette recherche pour ce format.

## 6. Alimentation et réseau

### Wifi vs Ethernet

- Aucune recommandation officielle spécifique à BirdNET-Go n'a été trouvée sur ce point précis,
  mais un article communautaire de test (« Captain Bodgit: BirdNet Systems Testing #1 », vu le
  21/09/2026) indique que les testeurs utilisent délibérément l'Ethernet plutôt que le wifi
  « pour éviter les problèmes de sans-fil qui pourraient perturber les systèmes en aval » — un
  choix de prudence plutôt qu'une nécessité stricte : BirdNET-Go fonctionne aussi en wifi (le
  processus de configuration prévoit explicitement de saisir un SSID/mot de passe).
- **Contrainte pratique propre au projet cadre photo** : un cadre accroché au mur, potentiellement
  loin d'une prise réseau, se prête mal à un câble Ethernet visible. Le wifi reste dans la
  pratique le choix par défaut pour ce type de montage, sauf si le mur choisi est déjà proche
  d'une prise RJ45.
- Point de vigilance : le débit réseau n'est pas le facteur limitant ici (l'inférence BirdNET
  tourne localement, seules de petites requêtes API sortent pour Inky Bird Frame) — la seule
  vraie exigence réseau est une connexion **stable**, pas rapide.

### PoE (Power over Ethernet)

- **Il n'existe pas de HAT PoE officiel Raspberry Pi Foundation pour le Pi 5** au moment de la
  recherche (21/09/2026) — seulement des HAT PoE tiers (Waveshare PoE HAT (G), 52Pi P30,
  GeeekPi P33, PoE Texas, etc.).
- Peu adapté à ce projet précis : la section 5 montre que le cadre IKEA RÖDALM n'offre que
  **3 cm de profondeur, déjà juste pour loger le Pi seul** — ajouter un HAT PoE (qui s'empile
  en plus du Pi) rendrait probablement le montage trop épais pour refermer le cadre. Le PoE
  reste une option pertinente seulement si vous changez de cadre pour un modèle plus profond,
  ou si le Pi est déporté hors du cadre (via le câble d'extension GPIO évoqué en section 2).

### Passage du câble d'alimentation

- Aucune information spécifique trouvée dans cette recherche sur des solutions de dissimulation
  de câble pour ce projet précis. Point de bon sens non vérifié par une source : un cadre mural
  alimenté en secteur implique un câble d'alimentation visible sortant du cadre, sauf à percer
  le mur ou utiliser une goulotte — à anticiper selon l'emplacement choisi, indépendamment du
  choix Pi/écran.

## Pièges d'achat

1. **Écran Waveshare = pas de compatibilité logicielle automatique.** Les deux projets de
   référence dépendent de la librairie `inky` de Pimoroni, qui auto-détecte le panneau via une
   EEPROM propre aux cartes Pimoroni. Un Waveshare, même avec un panneau Spectra 6 identique,
   nécessite sa propre librairie Python (`Waveshare EPD`) et une réécriture de la couche
   d'affichage. Ne pas acheter un Waveshare en pensant « c'est juste un écran e-ink, ça doit
   marcher pareil ».

2. **Le 13,3" Pimoroni est en tension d'approvisionnement fin 2026.** Rupture chez The Pi Hut,
   indisponible chez Berrybase, pré-commande chez Pimoroni directement au moment de la
   recherche (21/09/2026). Compter un délai, ou se rabattre sur le Waveshare 13,3" Spectra 6
   équivalent chez Berrybase (en stock au moment de la recherche) en acceptant le coût de
   réécriture logicielle.

3. **Commande UK post-Brexit : vérifier qui gère la TVA/douane, retailer par retailer.**
   Pimoroni annonce collecter TVA et droits de douane dès la commande (livraison « duties and
   taxes paid », pas de mauvaise surprise à la livraison, selon leur page shipping consultée le
   21/09/2026) — mais ce n'est pas automatiquement le cas de tous les revendeurs UK (The Pi Hut
   non vérifié sur ce point précis dans cette recherche). Par ailleurs, **une nouvelle règle
   douanière UE s'applique à partir du 1er juillet 2026 : 3 € de droit de douane par article**
   sur les colis de faible valeur (≤150 €) importés hors UE, y compris depuis le UK — à ajouter
   au calcul même pour un petit article.

4. **Le Pi 5 exige une alimentation USB-C PD 27 W (5V/5A).** Un chargeur de téléphone USB-C
   générique (souvent 5V/3A, ou PD mal négocié) peut sous-alimenter le Pi 5, provoquant des
   instabilités ou redémarrages sous charge — typiquement quand écran + wifi + calcul tirent du
   courant simultanément. L'alimentation officielle ne coûte que 12,90 € chez Kubii : pas de
   raison de prendre le risque avec un chargeur générique. Le Pi 4 et le Zero 2 W n'ont pas
   cette contrainte stricte.

5. **Carte microSD générique = panne annoncée.** Le wiki matériel officiel de BirdNET-Go
   documente lui-même ce risque : écritures continues (logs, clips audio) usent vite une carte
   SD grand public. Prendre une carte explicitement « High Endurance »/« Surveillance
   Grade »/« Dashcam Rated », V30 minimum, 64 Go ou plus.

6. **Raspberry Pi Zero 2 W en pénurie généralisée en Europe fin 2026.** Rupture chez Pimoroni UK,
   chez Kubii (19,50 € catalogue mais indisponible au moment de la recherche), retailers
   allemands en statut « incoming » sans date. Attention aux vendeurs tiers qui profitent de la
   pénurie pour vendre un Zero 2 W à plus de 100 € sur des places de marché — le prix catalogue
   reste ~19,50 €.

7. **Crise des prix mémoire 2026 : les prix « de mémoire » sont probablement obsolètes.**
   Les tarifs officiels Raspberry Pi ont été relevés trois fois en 2026 (+83% sur le Pi 5 4GB,
   +119% sur le Pi 5 8GB selon Comptoir du Hardware/Hardware & Co, vus le 21/09/2026). Un Pi 4
   4GB et un Pi 5 4GB coûtent aujourd'hui des prix quasi identiques chez Kubii (117 € vs
   130,50 €) — ne pas se fier à un ancien article ou une ancienne estimation de prix.

8. **Les dates de réapprovisionnement affichées sur les fiches produit peuvent être obsolètes.**
   Exemple concret rencontré pendant cette recherche : la fiche Kubii du Pi 5 8GB/16GB annonçait
   au moment de la consultation une date de réassort « mi-février 2026 » — déjà dans le passé à
   la date d'aujourd'hui (21/09/2026). Ne pas planifier un achat sur la foi d'une date affichée
   sans la revérifier en direct.

9. **BirdNET-Go ne supporte plus le Pi Zero 2 W ni le Pi 3.** Ne pas acheter un Zero 2 W en
   pensant faire tourner BirdNET-Go dessus — il est réservé à la voie Inky Bird Frame (agrégation
   API, sans inférence locale).

10. **Le cadre RÖDALM ne laisse que 3 cm de profondeur.** Suffisant pour un Pi nu vissé sur le
    panneau, mais ça ne laisse quasiment aucune marge pour empiler un HAT supplémentaire (PoE,
    NVMe). Si vous voulez un de ces HAT, il faudra soit déporter le Pi hors du cadre (câble
    d'extension GPIO), soit choisir un cadre plus profond.

11. **Câble d'extension GPIO : sens de branchement critique.** Plusieurs fabricants (Pimoroni,
    Adafruit) avertissent explicitement qu'un branchement à l'envers entre le connecteur GPIO du
    Pi et celui du HAT peut endommager le Pi et/ou le HAT — repérer le fil rouge/la ligne
    blanche marquant la broche 1 avant de brancher.

12. **L'Inky Impression 5,7" est discontinué chez Pimoroni** (« we no longer stock this
    product », vu le 21/09/2026) — ne pas bâtir un plan d'achat dessus même si son prix
    apparaît encore dans d'anciens articles ou chez des revendeurs hors UE avec du stock résiduel.

13. **Google Coral USB Accelerator : écosystème logiciel à l'arrêt depuis avril 2026** (dépôt
    GitHub officiel archivé). Le matériel reste utilisable mais sans garantie de support futur —
    à éviter comme brique d'un nouveau projet censé durer.

## BOM — Minimum viable (partir de zéro)

Hypothèse : voie **Fugleramme** (détection audio locale), écran de référence Pimoroni 13,3"
pour garantir zéro travail logiciel. Pi 4 plutôt que Pi 5 car BirdNET-Go tourne bien dessus en
usage standard et il coûte quasiment le même prix que le Pi 5 dans le contexte de pénurie 2026
— mais évitez le Pi 5 4 Go de justesse plus cher pour du minimum viable si vous pouvez vous en
passer.

| Poste | Choix | Prix vu | Source / statut au 21/09/2026 |
|---|---|---|---|
| Raspberry Pi | Pi 4 Model B 4 Go | 117,00 € | Kubii, **précommande** (pas de stock immédiat) |
| Alimentation | Officielle USB-C 15,3W (Pi 4) | 9,60 € | Kubii, en stock |
| Stockage | microSD High Endurance 64 Go (SanDisk High Endurance ou équiv.) | **~25 € [ESTIMATION]** | Fourchette basse vue sur comparateurs de prix FR (21,17-24,99 €), page produit unique non re-vérifiée |
| Micro | Boya BY-LM40 (USB) | 43,90 € | Galaxus.fr, en ligne |
| Écran | Inky Impression 13,3" (PIM774) | 299,90 € | Berrybase, **indisponible** au moment de la recherche (alternative UK : The Pi Hut £229,50, également en rupture) |
| Cadre | IKEA RÖDALM 21×30, blanc | 6,99 € | ikea.com/fr, en stock à vérifier en magasin |
| **Total** | | **≈ 502,39 €** | Hors frais de port, hors éventuels frais de douane si commande hors UE |

**Remarque honnête** : ce total suppose qu'on trouve l'écran 13,3" Pimoroni en stock quelque
part au prix Berrybase. Au moment de la recherche, ce n'était le cas nulle part en UE/FR vérifié
— il faut soit attendre un réassort, soit basculer sur le Waveshare 13,3" Spectra 6 (259,90 €,
en stock chez Berrybase) en acceptant de réécrire la couche d'affichage du projet.

## BOM — Confort / recommandé

Pi 5 pour la marge de puissance (multi-modèles BirdNET, UI plus réactive), refroidissement actif
par précaution, micro Clippy EM272 de qualité naturaliste avec interface XLR dédiée, HAT NVMe
pour ne plus dépendre de l'endurance de la carte SD comme unique stockage.

| Poste | Choix | Prix vu | Source / statut au 21/09/2026 |
|---|---|---|---|
| Raspberry Pi | Pi 5, 4 Go | 130,50 € | Kubii, **rupture de stock** |
| Alimentation | Officielle USB-C PD 27W (Pi 5) | 12,90 € | Kubii, en stock |
| Refroidissement | Ventilateur/dissipateur actif officiel Pi 5 | 6,00 € | Kubii, en stock |
| Stockage carte SD | microSD High Endurance 64 Go | **~25 € [ESTIMATION]** | Voir remarque BOM minimum |
| Stockage NVMe (optionnel) | M.2 HAT+ officiel (adaptateur seul, **SSD NVMe non inclus et non chiffré dans cette recherche**) | 14,10 € (HAT seul) | Kubii, en stock |
| Micro | Clippy EM272 XLR (mono) | 85,00 € | Le Club Biotope (FR), boutique naturaliste |
| Interface audio | Focusrite Scarlett Solo (3e gén.), pour alimentation fantôme du Clippy XLR | **~130 € [ESTIMATION, prix vu dans une discussion communautaire, pas sur une page boutique]** | À vérifier avant achat |
| Écran | Inky Impression 13,3" (PIM774) | 299,90 € | Berrybase, indisponible au moment de la recherche |
| Cadre | IKEA RÖDALM 21×30 | 6,99 € | ikea.com/fr |
| **Total (sans SSD NVMe)** | | **≈ 710,39 €** | Hors port, hors SSD NVMe si vous l'ajoutez, hors douane éventuelle |

**Pourquoi ce n'est pas juste « plus cher »** : le Pi 5 + refroidisseur sécurise le
fonctionnement 24/7 sans throttling ; le Clippy XLR + Focusrite améliore nettement le rapport
signal/bruit par rapport au Boya USB simple (le wiki BirdNET-Go note explicitement la faible
sensibilité du Boya) — pertinent si vous comptez sur la qualité de détection plutôt que sur le
strict minimum fonctionnel. Le HAT NVMe est optionnel : ajoutez-le seulement si vous voulez
éliminer le risque d'usure de la carte SD plutôt que de simplement prendre une carte endurante.

## Variante — tester sans acheter l'écran

Objectif : valider que le pipeline de détection (BirdNET-Go + micro) fonctionne réellement chez
vous, **avant** d'engager les ~300 € de l'écran e-ink. Confirmé en lisant le dépôt
`tphakala/birdnet-go` : le projet publie des **images Docker pour `linux/amd64` et
`linux/arm64`**, et l'extrait de documentation vu sur la page du projet mentionne explicitement
un usage « on a Linux box with a USB mic » indépendamment de tout Raspberry Pi. BirdNET-Go a
aussi sa propre interface web (accessible depuis un navigateur) qui permet de voir les
détections sans aucun écran e-ink.

**Concrètement, si vous avez déjà un Mac ou un PC Linux/Windows (WSL) :**

| Poste | Choix | Prix | Remarque |
|---|---|---|---|
| Ordinateur | Le vôtre (Mac Apple Silicon = arm64, Mac Intel/PC = amd64) | 0 € | Déjà possédé |
| BirdNET-Go | Image Docker officielle | 0 € | Open source |
| Micro (option zéro euro) | Micro intégré de l'ordinateur/webcam | 0 € | Qualité insuffisante pour un vrai déploiement extérieur, mais suffit pour vérifier que l'installation et la détection fonctionnent sur des sons de test ou en intérieur |
| Micro (option réaliste, réutilisable ensuite) | Boya BY-LM40 (USB) | 43,90 € | Le même micro pourra servir tel quel dans le BOM minimum viable — aucun argent perdu si vous continuez le projet |
| **Total** | | **0 à 43,90 €** | |

**Ce que ça valide** : que BirdNET-Go s'installe, tourne, écoute le micro et détecte
correctement des espèces locales — donc que la partie « intelligence » du projet fonctionne
avant d'investir dans le Raspberry Pi et l'écran. Ce que ça ne valide *pas* : le comportement en
extérieur 24/7 (chaleur, humidité, alimentation), ni l'intégration avec l'écran e-ink (couche
d'affichage `inky`), qui reste à tester séparément une fois le matériel définitif en main.

**Si vous voulez aussi tester la voie Inky Bird Frame (agrégation API) sans rien acheter** :
c'est encore plus simple, puisque ce projet n'a besoin d'aucun capteur — seulement d'un accès
réseau pour interroger iNaturalist/eBird. Un simple test du script d'agrégation sur votre
ordinateur habituel, sans Pi ni écran, permet de vérifier que les données récupérées autour de
chez vous sont pertinentes avant d'investir dans le cadre physique.

## Sources

### Projets de référence
- [Fugleramme — dépôt GitHub](https://github.com/arnegiacomo/fugleramme)
- [Fugleramme — page matériel/assemblage](https://arnegiacomo.dev/fugleramme/hardware/)
- [Inky Bird Frame — dépôt GitHub](https://github.com/veteranbv/inky-bird-frame)
- [Librairie Python `inky` de Pimoroni](https://github.com/pimoroni/inky)
- [BirdNET-Go — wiki matériel officiel](https://github.com/tphakala/birdnet-go/wiki/hardware)
- [BirdNET-Go — dépôt GitHub](https://github.com/tphakala/birdnet-go)
- [BirdNET-Go — discussion sur le bruit Pi 5 / interférences USB](https://github.com/tphakala/birdnet-go/discussions/2541)
- [BirdNET-Go — discussion charge CPU](https://github.com/tphakala/birdnet-go/discussions/3163)
- [BirdNET-Pi — discussion micros USB](https://github.com/mcguirepr89/BirdNET-Pi/discussions/39)
- [BirdNET-Pi — issue micro étanche](https://github.com/mcguirepr89/BirdNET-Pi/issues/1001)
- [Recommandation micro BirdNET-Pi — dzombak.com](https://www.dzombak.com/blog/2025/07/recommendation-microphone-setup-for-birdnet-pi/)
- [Build a Weather-Resistant BirdNET-Pi Box — Kindalame.com](https://kindalame.com/2026/05/20/build-a-weather-resistant-birdnet-pi-box-keep-your-mic-dry-and-listening/)

### Écran e-ink
- [Inky Impression 13.3" (2025 Edition) — The Pi Hut](https://thepihut.com/products/inky-impression-13-3-2025-edition)
- [Inky Impression 7.3" (2025 Edition) — The Pi Hut](https://thepihut.com/products/inky-impression-7-3-2025-edition)
- [Inky Impression 5.7" — The Pi Hut (discontinued)](https://thepihut.com/products/inky-impression-7-colour-epaper-eink-epd)
- [Inky Impression — boutique Pimoroni](https://shop.pimoroni.com/en-us/products/inky-impression)
- [Inky Impression 5.7" — boutique Pimoroni (discontinué)](https://shop.pimoroni.com/en-us/products/inky-impression-5-7)
- [Pimoroni — page shipping (TVA/douane UE)](https://shop.pimoroni.com/en-us/pages/shipping-information)
- [Inky Impression 13.3" — Berrybase](https://www.berrybase.de/en/pimoroni-inky-impression-13-3-epaper-display-fuer-raspberry-pi-spectra-6-1600x1200-6-farben-gpio)
- [Waveshare 13.3" e-Paper HAT+ (E), Spectra 6 — Berrybase](https://www.berrybase.de/en/waveshare-e-ink-colour-display-hat-13.3-inch-1600x1200-spectra-6-spi-with-driver-board-3.3-5v)
- [Waveshare 13.3inch e-Paper HAT+ (E) — page produit officielle Waveshare](https://www.waveshare.com/13.3inch-e-paper-hat-plus-e.htm)
- [Waveshare 7.3inch ACeP 7-Color — page produit officielle Waveshare](https://www.waveshare.com/7.3inch-e-paper-hat-f.htm)
- [Waveshare 7.3inch ACeP 7-Color — Opencircuit.shop](https://opencircuit.shop/product/7.3inch-acep-7-color-e-paper-e-ink-display)
- [Discussion compatibilité Waveshare / EEPROM inky — pimoroni/inky-phat issue #17](https://github.com/pimoroni/inky-phat/issues/17)

### Raspberry Pi et accessoires
- [Raspberry Pi 5 (4/8/16 Go) — Kubii](https://www.kubii.com/en/nano-computers/4106-1831-raspberry-pi-5-3272496315938.html)
- [Raspberry Pi 4 Model B 4 Go — Kubii](https://www.kubii.com/fr/2772-nouveau-raspberry-pi-4-modele-b-4gb-kubii-3272496309333.html)
- [Raspberry Pi Zero 2 W — Kubii](https://www.kubii.com/en/raspberry-pi-boards/3455-raspberry-pi-zero-2-w-5056561800004.html)
- [Alimentation officielle 27W USB-C (Pi 5) — Kubii](https://www.kubii.com/fr/alimentations/4107-1890-alimentation-raspberry-pi-27w-usb-c-3272496315761.html)
- [Alimentation officielle 15,3W USB-C (Pi 4) — Kubii](https://www.kubii.com/fr/alimentations/3292-alimentation-officielle-raspberry-pi-4-51-v-30-a-usb-type-c-prise-us-644824914893.html)
- [Ventilateur/dissipateur actif officiel Pi 5 — Kubii](https://www.kubii.com/fr/ventilateurs-dissipateurs-thermiques/4109-ventilateur-dissipateur-pour-raspberry-pi-5-5056561803357.html)
- [M.2 HAT+ officiel pour Pi 5 — Kubii](https://www.kubii.com/en/raspberry-pi-5/4114-m2-hat-for-raspberry-pi-5-5056561803463.html)
- [Hausse des prix Raspberry Pi 2026 — Hardware & Co](https://hardwareand.co/actualites/breves/cest-lete-il-faut-chaud-mais-les-prix-des-raspberry-pi-eux-font-froid-dans-le-dos)
- [Pénurie Pi Zero 2 W 2026 — raspberry.tips](https://raspberry.tips/en/raspberrypi-infos/raspberry-pi-zero-2-w-alternative-sold-out)
- [Nouvelle règle douanière UE juillet 2026 — Simarco](https://www.simarco.com/frances-vat-shake-up-the-2026-rule-change-that-will-reshape-uk-eu-exports/)
- [Throttling thermique Pi 5 — Raspberry Pi (officiel)](https://www.raspberrypi.com/news/heating-and-cooling-raspberry-pi-5/)
- [SanDisk High Endurance microSD 64 Go — comparateur LeGuide/Kelkoo](https://www.leguide.com/gtin/00619659173081)

### Micro
- [Clippy EM272 XLR — Le Club Biotope (FR)](https://leclub-biotope.com/en/equipment-for-naturalists/2902-clippy-em272-xlr-audible-microphone-mono-or-stereo-option)
- [Clippy EM272 — micbooster.com (UK)](https://micbooster.com/product/clippy-em272-microphone/)
- [Boya BY-LM40 — Galaxus.fr](https://www.galaxus.fr/fr/s1/product/boya-by-lm40-microphone-lavaliermicrophone-a-clipser-microphone-20693189)

### Caméra / Coral
- [Raspberry Pi Camera Module v3 — Kubii](https://www.kubii.com/en/cameras-sensors/3878-1689-camera-module-v3-raspberry-pi-3272496313699.html)
- [Archivage du dépôt Google Coral edgetpu — GitHub issue #363](https://github.com/google-coral/edgetpu/issues/363)

### Cadre
- [IKEA RÖDALM 21x30, blanc](https://www.ikea.com/fr/fr/p/roedalm-cadre-blanc-10548886/)
- [Cadre photo avec passe-partout 21x29,5 cm — Action FR](https://www.action.com/fr-fr/p/2566696/cadre-photo-avec-passe-partout/)

### Note méthodologique
Recherche effectuée le 21/09/2026 via recherche web et lecture directe de pages produit. Les
statuts de stock, prix et disponibilités évoluent vite (le contexte 2026 de pénurie/inflation
mémoire le confirme) — **tout prix ou statut de stock listé ici doit être revérifié avant achat
réel**, en particulier pour les postes marqués [ESTIMATION] dans ce document, qui n'ont pas été
vus tels quels sur une page produit unique et fiable.
