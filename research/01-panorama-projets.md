# Panorama de l'écosystème « cadre e-ink oiseaux » (recherche, sept. 2026)

## Méthode et niveau de confiance

Cette recherche s'appuie sur :
- l'API GitHub (`gh api repos/OWNER/REPO`, dates, stars, issues, statut d'archivage) pour tous les dépôts cités — ce sont des chiffres **vérifiés en direct le 2026-09-21**, pas des estimations ;
- la lecture des README/docs officiels des projets ;
- des recherches web pour les produits commerciaux et le contexte francophone ;
- quelques recherches complémentaires que j'ai effectuées moi-même en fin de collecte, une fois le quota de recherche web de la session épuisé par les sous-recherches.

Convention utilisée partout : **Vérifié** = confirmé via API GitHub, doc officielle ou README lu directement. **Non confirmé / supposé** = information non retrouvée dans une source primaire dans le temps imparti — signalé explicitement plutôt que deviné.

Remarque de prudence : les deux projets de référence n'ont que ~2,5 mois d'existence (créés en juillet 2026) mais affichent déjà des centaines, voire des milliers de stars. C'est un niveau d'adoption élevé pour un projet hobby aussi jeune ; il est corroboré par une couverture presse tech (Korben, MiniMachines, relais français de Hacker News — voir section 6), ce qui rend le chiffre plausible plutôt que suspect, mais je le signale pour transparence.

---

## 1. Les deux projets de référence

### 1.1 Fugleramme — github.com/arnegiacomo/fugleramme

**Vérifié (API GitHub, 2026-09-21) :**
- Créé le 2026-07-08, dernier push le 2026-09-21 (quelques heures avant cette recherche) — **activité quotidienne, plusieurs commits/jour**
- 3215 stars, 85 forks, 15 issues ouvertes, **non archivé**
- Licence MIT
- Releases taguées avec CI (dernière : v0.23.0, 2026-09-19), assets générés automatiquement (`uv.lock`)
- Commits récents observés : ajout d'espèces (Bombycilla cedrorum, espèces sud-africaines, Glaucidium gnoma, Junco hyemalis…), corrections de rendu ("halo levelling", crop précision), tests

**Créateur** : Arne Giacomo Munthe-Kaas, basé à Bergen, **Norvège** (et non danois comme le laissait supposer la lecture initiale — « fugleramme » est un mot scandinave commun, mais le créateur et le contexte du projet sont norvégiens ; voir section 6). Un fork collaboratif actif existe (oyvij/fugleramme).

**Ce que fait le projet** : détection audio via BirdNET-Go tournant localement sur Raspberry Pi 5, rendu de planches naturalistes illustrées façon XIXe siècle sur écran Inky Impression 13,3". Les tailles relatives des espèces suivent la base AVONET (masse corporelle réelle), arrangement en spirale. Ne redessine que si la liste d'espèces change (économie de rafraîchissement e-ink).

**Installation réelle** : un script one-liner (`curl -fsSL .../install.sh | bash`) existe bien et automatise le setup ; une alternative Docker Compose (BirdNET-Go inclus) est aussi proposée ; le développement local utilise `uv`. Le one-liner est donc réel, pas un abus marketing — mais la doc complète (guides matériel, déploiement conteneur, contribution d'illustrations) montre qu'il y a davantage à comprendre au-delà du simple copier-coller si l'on veut personnaliser.

**Matériel requis** : Raspberry Pi 5, Inky Impression 13,3" (recommandé, pas strictement obligatoire), micro, cadre A4.

**Qualité de la doc** : plusieurs guides séparés (matériel avec recommandations de pièces, installation depuis zéro, déploiement conteneur, contribution — avec process de soumission d'illustrations), FAQ mentionnée dans les guidelines de contribution, démo en ligne et base de couverture d'espèces consultable.

**Pourquoi ça intéresse quelqu'un qui part de zéro en France** : c'est le candidat le plus mûr et le moins risqué des deux — projet très actif, installation réellement simple, aucune dépendance réseau obligatoire pour fonctionner (tout tourne en local), base technique (BirdNET-Go) elle-même très bien maintenue (voir section 2).

### 1.2 Inky Bird Frame — github.com/veteranbv/inky-bird-frame

**Vérifié (API GitHub, 2026-09-21) :**
- Créé le 2026-07-09, dernier push le 2026-09-21 — activité quotidienne également
- 189 stars, 13 forks, 4 issues ouvertes, **non archivé**
- Licence MIT
- Release taguée v0.9.2 (2026-09-19), avec asset Docker (`inky-bird-frame-docker.tar.gz`)
- Commits récents : gestion des timeouts eBird (limite portée de 45 à 90 s), maintenance de dépendances CI, validations qualité (ruff, MyPy, pytest)

**Ce que fait le projet** : pas de détection locale — agrège des observations déclarées (iNaturalist par défaut, eBird sur un rayon de 50 km / 30 jours, BirdWeather, et des flux Bird Buddy) et génère des planches par IA (OpenAI Codex via abonnement ChatGPT) avec un pipeline de validation humaine. Catalogue partagé de 71 espèces approuvées, rotation séquentielle/aléatoire/pondérée, notifications Pushover/Apprise.

**Installation réelle** : deux voies — (1) Docker/NAS via un bundle de release téléchargé et une image tirée depuis GitHub Container Registry (AMD64/ARM64), (2) installation native Python 3.11+ sur macOS/Ubuntu/Raspberry Pi OS. Architecture à deux machines : un Pi Zero 2 W dans le cadre (affichage seul) + un contrôleur séparé (Pi 4/5, Mac ou Linux faisant tourner Docker) qui gère la logique. Au-delà du déploiement basique, la configuration réelle implique diagnostic du contrôleur, flashage du Pi, test du panneau, vérification réseau et activation de la rotation — 5 étapes de vérification documentées.

**Matériel requis** : panneau Inky Impression 13,3" (PIM774) ou 7,3" (PIM773), Pi Zero 2 W avec header pré-soudé pour le cadre, plus un contrôleur séparé. Coût annoncé : ~360 $ pour l'affichage encadré, ~174 $ de plus pour un contrôleur dédié (données juillet 2026, donc avant dévaluation/inflation éventuelle).

**Qualité de la doc** : très soignée — section troubleshooting dédiée avec commande `doctor` de diagnostic, documentation organisée par thème (matériel, installation par les deux méthodes, découverte/config, opérations, notifications, architecture "privacy-first").

**Pourquoi ça intéresse (ou non) quelqu'un qui part de zéro en France** : intéressant pour l'esthétique et l'idée d'agrégation multi-sources, mais architecture plus lourde (deux machines, dépendance réseau permanente aux APIs tierces, abonnement IA payant pour générer de nouvelles planches), communauté nettement plus restreinte (189 vs 3215 stars), et sources de données (eBird notamment) dont la pertinence géographique pour la France est incertaine (voir section 6).

### 1.3 Comparaison synthétique

| Critère | Fugleramme | Inky Bird Frame |
|---|---|---|
| Stars / forks / issues ouvertes | 3215 / 85 / 15 | 189 / 13 / 4 |
| Activité | Quotidienne, releases fréquentes | Quotidienne, releases fréquentes |
| Détection | Audio locale (BirdNET-Go) | Aucune — agrégation d'observations externes |
| Architecture | 1 Raspberry Pi | 2 machines (cadre + contrôleur) |
| Dépendance réseau | Optionnelle | Obligatoire (APIs + éventuellement IA payante) |
| Installation | Un script, ou Docker | Docker (NAS) ou natif, config multi-étapes |
| Coût matériel annoncé | 380-450 € | ~360 $ (+ ~174 $ contrôleur) |
| Doc | Complète, orientée self-service | Excellente, orientée troubleshooting |

---

## 2. Détection audio — l'écosystème BirdNET

**Vérifié (API GitHub, 2026-09-21) :**

| Projet | Archivé | Dernier commit | Stars | Issues ouvertes | Rôle |
|---|---|---|---|---|---|
| [birdnet-team/BirdNET-Analyzer](https://github.com/birdnet-team/BirdNET-Analyzer) | Non | 2026-09-08 | 1711 | 83 | Moteur ML brut (Cornell Lab) |
| [mcguirepr89/BirdNET-Pi](https://github.com/mcguirepr89/BirdNET-Pi) (original) | **Oui** | 2025-08-17 (~13 mois) | 1570 | 79 | Distribution RPi — **mort** |
| [Nachtzuster/BirdNET-Pi](https://github.com/Nachtzuster/BirdNET-Pi) (fork) | Non | 2026-02-28 (~7 mois) | 1128 | 62 | Distribution RPi — semi-actif |
| [tphakala/birdnet-go](https://github.com/tphakala/birdnet-go) | Non | 2026-09-20 (veille) | 2158 | 191 | Solution moderne complète |

**Point clé vérifié** : le README de mcguirepr89/BirdNET-Pi contient une bannière explicite : *« I no longer maintain this project (…) but Nachtzuster and the BirdNET-Pi community are still keeping it alive here »*, avec lien vers Nachtzuster/BirdNET-Pi. L'abandon et la passation de flambeau sont donc officiels, pas une simple constatation d'inactivité. Une recherche des forks actifs de 2026 n'a fait remonter que des clones personnels à 0 star — Nachtzuster est bien **le** fork de référence, mais son propre rythme de commits a nettement ralenti (dernier commit fin février 2026).

**BirdNET-Go** est aujourd'hui le projet le plus actif de tout l'écosystème (commits quotidiens, 2158 stars — davantage que le moteur BirdNET-Analyzer lui-même) : solution auto-hébergée en Go, multi-modèles (BirdNET v2.4, Google Perch v2, BattyBirdNET pour les chauves-souris, BirdNET Geomodel v3.0), interface web avec spectrogramme temps réel, alertes (Discord/Slack/Telegram/ntfy/Pushover/MQTT+Home Assistant), 15 langues d'UI, noms d'espèces en 40+ langues, installation one-liner ou Docker. C'est ce moteur qu'utilise Fugleramme.

**Recommandation factuelle de cette section** : BirdNET-Go pour toute nouvelle installation en 2026. Nachtzuster/BirdNET-Pi reste une alternative viable si on veut une distribution RPi plus simple/ancienne, mais son activité de développement a nettement ralenti. Le dépôt original mcguirepr89/BirdNET-Pi est une impasse déclarée à éviter.

---

## 3. Détection visuelle (caméra)

### 3.1 Écosystème open source

**Vérifié (API GitHub, 2026-09-21) :**

| Projet | Dernier commit | Stars | Rôle / statut |
|---|---|---|---|
| [blakeblackshear/frigate](https://github.com/blakeblackshear/frigate) | 2026-09-21 | 36028 | NVR de détection d'objets temps réel — très actif, sert de socle |
| [mmcc-xx/WhosAtMyFeeder](https://github.com/mmcc-xx/WhosAtMyFeeder) | 2024-05-05 (~2 ans) | 460 | Classification d'espèces sur snapshots Frigate (MQTT + TF Hub) — **stagnant** |
| [jdpdev/birbcam](https://github.com/jdpdev/birbcam) | 2021-08-31 (~4 ans) | 40 | Précurseur historique — obsolète techniquement |
| [ccrenfroe/BirdCam](https://github.com/ccrenfroe/BirdCam) | 2024-06-05 | 19 | Détecteur+classifieur autonome TFLite, sans Frigate — peu de traction |
| [pfortune/featherfeed](https://github.com/pfortune/featherfeed) | 2024-03-03 | 3 | Démo Coral TPU — ancien, peu développé |
| [ekstremedia/rpi5-birdcam-hailo-bioclip](https://github.com/ekstremedia/rpi5-birdcam-hailo-bioclip) | 2026-02-25 | 3 | Pi 5 + Hailo-8 NPU + BioCLIP — récent mais quasi inconnu |
| [sz24sz24-5607/birdy-project](https://github.com/sz24sz24-5607/birdy-project) | 2026-03-19 | 2 | Hybride audio+visuel — très jeune, audience nulle |

**Constat factuel** : contrairement à l'écosystème audio, la détection visuelle par caméra n'a pas de projet équivalent à BirdNET-Go en termes de maturité — le projet le plus référencé (WhosAtMyFeeder) est à l'arrêt depuis mi-2024, et les tentatives plus récentes (Hailo, BioCLIP) ont une audience quasi nulle (2-3 stars). Frigate lui-même est un socle solide et très actif, mais c'est un NVR généraliste, pas un outil dédié oiseaux — il faut lui adjoindre un classifieur.

**Coral USB Accelerator (Google)** : toujours en vente en septembre 2026 (Amazon, Seeed Studio, RS Online), mais aucune nouvelle production connue depuis ~2023 — stocks des revendeurs existants, approvisionnement long terme incertain (non confirmé de façon définitive).

### 3.2 Produits commerciaux (pour comparaison)

| Produit | Prix observé (09/2026) | Base d'espèces | Disponibilité France |
|---|---|---|---|
| [Bird Buddy](https://mybirdbuddy.com/) (Pro Solar) | ~189 $ (promo) | ~1000+ espèces, IA incluse | Confirmée via Zoomalia, SB Supply (Medpets en rupture) |
| [Netvue Birdfy](https://www.birdfy.com/) | ~90-250 $ selon modèle | ~6000+ espèces revendiquées | Probable via Amazon/eBay, non confirmée directement auprès du fabricant |

**Une phrase de comparaison** : les produits commerciaux offrent une expérience plug-and-play (10-30 min de setup) avec une base d'espèces large sans aucune maintenance, contre plusieurs heures/jours de montage pour une chaîne Frigate + classifieur maison qui reste, à ce jour, nettement moins mature que l'équivalent audio (BirdNET-Go) — la détection visuelle n'est donc pas la voie la plus rentable pour démarrer.

---

## 4. Agrégateurs de données

Cette section a été la plus difficile à vérifier : les docs eBird (Postman) et iNaturalist sont des pages construites en JavaScript qui ne se laissent pas lire par un simple fetch automatisé, et ont renvoyé des 403 lors des tentatives directes. Ce qui suit distingue donc explicitement le vérifié du rappelé de mémoire générale (à recontrôler avant de coder).

### BirdWeather

**Vérifié** : documentation accessible en GraphQL (`app.birdweather.com/graphql`) et REST v1 (`app.birdweather.com/api/v1`). Authentification par token (pas une simple clé API — fourni en segment d'URL, paramètre JSON ou header `Authorization`/`X-Auth-Token`), avec une distinction entre niveau station et niveau admin. Les conditions d'utilisation interdisent explicitement de créer *« an unreasonable load on the Services' infrastructure »* mais **aucun quota chiffré n'est publié**. Données disponibles : détections avec score de confiance, métadonnées de stations (position GPS, capteurs), filtrage par zone géographique, période, seuil de confiance, espèce.

**Non confirmé** : la signification exacte de l'acronyme « PUC » que la documentation du cadre Inky Bird Frame évoque — une extraction automatisée a suggéré « Portable Universe Codec », ce qui ne correspond à rien de cohérent dans le contexte et est probablement une erreur de lecture de page ; je ne retiens pas cette définition. À vérifier directement en créant un compte.

**Utilité pour ce projet** : c'est le pont naturel entre Fugleramme (audio local) et un réseau plus large — BirdNET-Go a une intégration native BirdWeather, donc l'activer ne coûte rien de plus une fois BirdNET-Go déployé.

### eBird API 2.0

**Vérifié** : la doc officielle existe à `documenter.getpostman.com/view/664302/S1ENwy59` mais son contenu technique n'a pas pu être extrait automatiquement (page JS). Inky Bird Frame utilise réellement cette API avec un rayon de 50 km et une fenêtre de 30 jours (donnée confirmée par le README de ce projet), ce qui corrobore les limites généralement documentées par Cornell.

**Rappelé de mémoire générale, non re-vérifié en direct dans cette session** : la clé API s'obtient gratuitement via `ebird.org/api/keygen` après création d'un compte eBird/Cornell gratuit ; il n'existe pas de quota strict publié pour un usage personnel raisonnable, mais un usage commercial ou intensif nécessite de contacter Cornell directement ; les données sont des observations déclarées par des birders (donc avec un délai, pas du temps réel) ; usage non commercial gratuit avec attribution requise. **À reconfirmer vous-même avant de construire dessus.**

### iNaturalist API

**Vérifié** : les pages de documentation publique (`inaturalist.org/pages/developers`, `/pages/api+reference`, `api.inaturalist.org/v1/docs`) ont toutes renvoyé une erreur 403 lors des tentatives d'accès automatisé — impossible de confirmer les quotas exacts dans cette session. Le jeu de données ouvert (photos, observations, taxons) est distribué gratuitement en CSV sur S3 par ailleurs (400M+ photos), mais ce n'est pas la même chose que l'API live.

**Rappelé de mémoire générale, non re-vérifié en direct** : les endpoints de lecture (`GET /v1/observations`) sont accessibles sans authentification, l'OAuth n'étant requis que pour écrire ou accéder à des données privées ; il existe une limitation de débit (de l'ordre de quelques dizaines de requêtes/minute) indiquée dans les en-têtes de réponse ; chaque observation porte sa propre licence (CC0, CC-BY, CC-BY-NC, ou tous droits réservés), donc l'attribution dépend de chaque photo. **À reconfirmer vous-même.**

### Tableau récapitulatif

| API | Auth | Quota publié | Type de données | Fiabilité pour la France |
|---|---|---|---|---|
| BirdWeather | Token | Non publié | Détections BirdNET en quasi temps réel, réseau de stations | Bonne — dépend de la densité de stations BirdNET-Go locales |
| eBird 2.0 | Clé API gratuite | Non confirmé en direct | Observations déclarées, rayon 50 km, 30 j | Correcte mais probablement inférieure à Faune-France (section 6) |
| iNaturalist | Ouvert en lecture (a priori) | Non confirmé en direct | Observations avec preuve photo/son | Faible pour l'ornithologie pure (preuve photo souvent difficile) |

---

## 5. Affichage e-ink — logiciels et matériel

### 5.1 Frameworks logiciels (alternatives/inspiration)

**Vérifié (API GitHub, 2026-09-21) :**

| Projet | Dernier commit | Stars | Issues ouvertes | Écrans supportés |
|---|---|---|---|---|
| [fatihak/InkyPi](https://github.com/fatihak/InkyPi) | 2026-08-29 | 4224 | 87 | Inky Impression (4"-13,3"), Inky wHAT, Waveshare Spectra 6, Waveshare N&B — **pas** IT8951 |
| [aceinnolab/Inkycal](https://github.com/aceinnolab/Inkycal) | 2026-09-12 | 1480 | 5 | Waveshare 5,83" à 13,3", N&B / N&B+Rouge/Jaune / 16 niveaux de gris |
| [MikeGawi/ePiframe](https://github.com/MikeGawi/ePiframe) | 2025-08-09 | 73 | 6 | Waveshare (N&B et couleur), Pimoroni Inky, HDMI/Composite |
| [txoof/PaperPi](https://github.com/txoof/PaperPi) | 2025-10-19 | 205 | 28 | Quasi tous les Waveshare SPI, dont IT8951 |

**InkyPi** est le plus actif et le mieux étoilé — architecture à plugins (upload d'images, météo, calendrier, génération IA), support large des écrans couleur y compris le Waveshare Spectra 6, ce qui en fait la base logicielle la plus solide si l'on voulait repartir d'un framework générique plutôt que du pipeline déjà écrit par Fugleramme. **Note** : il ne supporte pas les écrans à contrôleur IT8951 (donc pas le Waveshare 10,3" niveaux de gris).

**ePiframe** est conceptuellement le plus proche d'un « cadre photo », mais sa fonctionnalité historique de tirage depuis Google Photos est cassée (changement d'API côté Google) — seules les sources locales restent utilisables aujourd'hui.

### 5.2 Alternatives matérielles à l'Inky Impression 13,3"

| Écran | Résolution | Couleurs | Rafraîchissement | Prix observé |
|---|---|---|---|---|
| Pimoroni Inky Impression 13,3" | 1600×1200 | 6 (Spectra 6) | ~12-35 s | £229,50 |
| Waveshare 13,3" Spectra 6 | 1600×1200 | 6 (Spectra 6) | ~19 s | 249-260 $ |
| Waveshare 7,3" ACeP | 800×480 | 7 (ACeP) | ~35 s | ~68 $ / 94 € (modèle ancien, remplacé chez Waveshare) |
| Waveshare 10,3" niveaux de gris | 1872×1404 | 2-16 gris (IT8951) | <1 s (rafraîchissement partiel) | ~203 $ |

**À noter** : le Waveshare Spectra 6 13,3" est fonctionnellement quasi identique à l'Inky Impression 13,3" (même génération de panneau E Ink Spectra 6), avec un HAT Waveshare au lieu du HAT Pimoroni — c'est donc une alternative directe et non un compromis technique. Le 10,3" niveaux de gris a un rafraîchissement très supérieur (utile si on veut des mises à jour fréquentes) mais perd toute couleur, ce qui contredit l'esthétique « planche naturaliste colorée » recherchée par les deux projets de référence.

---

## 6. Projets francophones / européens et question des bases d'espèces

### 6.1 Communauté francophone

**Vérifié** : une communauté francophone active existe autour de BirdNET, essentiellement dans l'écosystème **Home Assistant** — tutoriel détaillé sur le forum HACF (forum.hacf.fr) pour repérer et écouter les oiseaux du jardin via Raspberry Pi + BirdNET. **Non trouvé** : pas de communauté Reddit ou Discord francophone dédiée identifiée.

**Vérifié** : Fugleramme a été relayé par des médias tech français (Korben, MiniMachines, et le relais français de Hacker News hada.io), ce qui explique sa croissance rapide malgré son jeune âge. Le créateur est basé à Bergen, Norvège — les échanges GitHub (issues) sont en anglais, sans communauté scandinave visible sur le dépôt lui-même.

**Vérifié (dans le README de Fugleramme)** : les illustrations sont explicitement décrites comme couvrant au mieux la « Scandinavie, les îles britanniques et l'Europe centrale ». Autrement dit, le moteur de détection (BirdNET-Go) reconnaît potentiellement des milliers d'espèces dans le monde, mais le **catalogue d'illustrations** de Fugleramme est, lui, centré sur l'avifaune d'Europe du Nord/centrale — probablement une bonne couverture pour l'essentiel des espèces communes en France, mais avec des trous possibles sur les espèces plus méditerranéennes. Les commits récents montrent que des espèces sont ajoutées en continu (y compris sud-africaines), donc le catalogue s'élargit.

### 6.2 Couverture géographique des bases d'espèces

**Vérifié** : BirdNET (moteur utilisé par Fugleramme) couvre plus de 6000 espèces (oiseaux, mammifères, amphibiens confondus ; plus de 3000 espèces d'oiseaux seules), avec un **filtrage géo-saisonnier documenté** : le « Species Range Model » utilise les données de check-lists eBird pour restreindre les espèces probables selon latitude, longitude et semaine de l'année (nécessite au moins 10 check-lists par semaine/région pour une prédiction fiable). L'Europe est correctement représentée dans eBird (contrairement à de larges parties d'Afrique et d'Asie, moins bien couvertes) — donc la précision géographique de BirdNET devrait être satisfaisante pour la France.

**Vérifié** : en France, la plateforme de référence pour les ornithologues n'est **pas** eBird mais **Faune-France**, portée par la LPO (Ligue pour la Protection des Oiseaux) — environ 90 000 contributeurs, plus de 150 millions de données collectées (2024). eBird existe et est utilisé en France mais dans une moindre mesure. iNaturalist est jugé peu adapté à l'ornithologie pure car il exige une preuve photo/son par observation, contrainte difficile pour du chant d'oiseau.

**Vérifié — absence d'API publique** : ni Faune-France ni la LPO ne documentent d'API publique. Un outil tiers (`ornitho2ebird`, github.com/Zoziologie/ornitho2ebird) permet d'exporter des données de Faune-France vers eBird mais ce n'est pas un accès programmatique direct. Certaines données LPO (réserves naturelles) sont disponibles via GBIF, de façon partielle. **Conséquence pratique pour ce projet** : si l'on veut des observations déclarées de qualité pour la France, il n'existe pas d'équivalent français à l'API eBird — il faudrait soit se contenter d'eBird (moins dense localement), soit contacter directement Biolovision/LPO pour explorer un accès ad hoc.

---

## 7. Recommandation

**Quelles briques combiner pour le meilleur rapport effort/résultat, en partant de zéro en France :**

**1. Fugleramme comme base principale.** C'est de loin le projet le plus mûr des deux références (10× plus de stars, installation réellement en une commande, aucune dépendance réseau obligatoire), construit sur BirdNET-Go — qui s'avère être, après comparaison, le moteur audio le plus activement maintenu de tout l'écosystème (plus actif que le moteur officiel BirdNET-Analyzer et que les distributions BirdNET-Pi historiques). Cela résout d'un coup la détection, le rendu e-ink et le choix matériel (Inky Impression 13,3" ou son équivalent direct, le Waveshare Spectra 6 13,3", si le Pimoroni n'est pas disponible/plus cher à l'achat en France).

**2. Activer l'intégration BirdWeather native de BirdNET-Go.** Puisque BirdNET-Go la propose déjà en configuration, ça ne coûte rien de plus techniquement et ça ouvre une fenêtre sur le réseau de stations BirdNET voisines — un pont low-effort vers ce que font d'autres personnes autour de chez soi, sans avoir à réimplémenter la logique d'agrégation qu'Inky Bird Frame a dû construire de zéro.

**3. En complément optionnel, une couche eBird légère** (pas une réplication de l'architecture Inky Bird Frame) : un appel périodique à l'API eBird « observations récentes à proximité » (clé gratuite, rayon jusqu'à 50 km) pour signaler des espèces vues mais pas forcément entendues par le micro (rapaces silencieux, espèces migratrices de passage). À traiter comme un enrichissement ponctuel, pas une dépendance structurante, sachant que Faune-France — la source de référence en France — n'a pas d'API publique exploitable à ce jour.

**Ce qu'il vaut mieux éviter de construire maintenant** : la détection visuelle par caméra (Frigate + classifieur d'espèces) est nettement moins mature que la voie audio pour ce cas d'usage précis — le projet le plus référencé (WhosAtMyFeeder) est à l'arrêt depuis mi-2024, les tentatives plus récentes ont une audience quasi nulle, et la disponibilité long terme du Coral TPU est incertaine. Ce n'est pas à écarter définitivement (c'est un excellent complément visuel plus tard), mais ce n'est pas le chemin au meilleur rapport effort/résultat pour démarrer. De même, répliquer l'architecture à deux machines d'Inky Bird Frame (cadre + contrôleur séparé, génération de planches par IA payante) ajoute de la complexité et un coût récurrent pour un gain esthétique qui peut aussi s'obtenir, à terme, en contribuant de nouvelles illustrations au catalogue grandissant de Fugleramme.

---

## Sources

**Projets de référence**
- [github.com/arnegiacomo/fugleramme](https://github.com/arnegiacomo/fugleramme)
- [github.com/veteranbv/inky-bird-frame](https://github.com/veteranbv/inky-bird-frame)

**Détection audio**
- [github.com/birdnet-team/BirdNET-Analyzer](https://github.com/birdnet-team/BirdNET-Analyzer)
- [birdnet-team.github.io/BirdNET-Analyzer](https://birdnet-team.github.io/BirdNET-Analyzer/)
- [github.com/mcguirepr89/BirdNET-Pi](https://github.com/mcguirepr89/BirdNET-Pi)
- [github.com/Nachtzuster/BirdNET-Pi](https://github.com/Nachtzuster/BirdNET-Pi)
- [github.com/tphakala/birdnet-go](https://github.com/tphakala/birdnet-go)
- [github.com/tphakala/birdnet-go/wiki](https://github.com/tphakala/birdnet-go/wiki)

**Détection visuelle**
- [github.com/blakeblackshear/frigate](https://github.com/blakeblackshear/frigate)
- [github.com/mmcc-xx/WhosAtMyFeeder](https://github.com/mmcc-xx/WhosAtMyFeeder)
- [github.com/jdpdev/birbcam](https://github.com/jdpdev/birbcam)
- [github.com/ccrenfroe/BirdCam](https://github.com/ccrenfroe/BirdCam)
- [github.com/pfortune/featherfeed](https://github.com/pfortune/featherfeed)
- [github.com/ekstremedia/rpi5-birdcam-hailo-bioclip](https://github.com/ekstremedia/rpi5-birdcam-hailo-bioclip)
- [github.com/sz24sz24-5607/birdy-project](https://github.com/sz24sz24-5607/birdy-project)
- [coral.withgoogle.com/products/accelerator](https://www.coral.withgoogle.com/products/accelerator/)
- [mybirdbuddy.com](https://mybirdbuddy.com/)
- [birdfy.com](https://www.birdfy.com/)

**Agrégateurs de données**
- [app.birdweather.com/api/v1](https://app.birdweather.com/api/v1/index.html)
- [app.birdweather.com/graphql](https://app.birdweather.com/graphql)
- [birdweather.com/terms-of-service](https://www.birdweather.com/terms-of-service)
- [documenter.getpostman.com/view/664302/S1ENwy59](https://documenter.getpostman.com/view/664302/S1ENwy59) (eBird API 2.0)
- [api.inaturalist.org/v1](https://api.inaturalist.org/v1/)

**Affichage e-ink**
- [github.com/fatihak/InkyPi](https://github.com/fatihak/InkyPi)
- [github.com/aceinnolab/Inkycal](https://github.com/aceinnolab/Inkycal)
- [github.com/txoof/PaperPi](https://github.com/txoof/PaperPi)
- [github.com/MikeGawi/ePiframe](https://github.com/MikeGawi/ePiframe)
- [shop.pimoroni.com — Inky Impression](https://shop.pimoroni.com/en-us/products/inky-impression)
- [waveshare.com — 13.3inch Spectra 6](https://www.waveshare.com/13.3inch-e-paper-hat-plus-e.htm)
- [waveshare.com — 7.3inch ACeP](https://www.waveshare.com/7.3inch-e-paper-f.htm)
- [waveshare.com — 10.3inch niveaux de gris](https://www.waveshare.com/10.3inch-e-paper-hat.htm)

**Francophone / Europe / bases d'espèces**
- [forum.hacf.fr — tuto BirdNET](https://forum.hacf.fr/t/birdnet-tuto-comment-reperer-et-ecouter-les-oiseaux-du-jardin/66856)
- [korben.info — Fugleramme](https://korben.info/en/fugleramme-frame-draws-birds-it-hears.html)
- [minimachines.net — Fugleramme](https://www.minimachines.net/actu/fugleramme-raspberry-p-142896)
- [faune-france.org](https://www.faune-france.org/)
- [github.com/Zoziologie/ornitho2ebird](https://github.com/Zoziologie/ornitho2ebird)
- [github.com/birdnet-team/BirdNET-Analyzer/blob/main/docs/best-practices/species-lists.rst](https://github.com/birdnet-team/BirdNET-Analyzer/blob/main/docs/best-practices/species-lists.rst)
