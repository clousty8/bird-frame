# Pièges et retours d'expérience — cadre e-ink Raspberry Pi / BirdNET

Veille centrée sur les galères réelles (issues GitHub ouvertes et fermées, forums, Reddit, blogs),
pas sur les articles enthousiastes. Chaque ligne est sourcée par une URL réelle, vérifiée soit
directement (via `gh` sur les dépôts GitHub, soit via récupération de page), soit par un des
agents de recherche dédiés dont les citations ont ensuite été re-vérifiées par échantillonnage.
Quand une source n'a pas pu être confirmée, ou quand un point relève de la déduction/connaissance
générale plutôt que d'un témoignage précis, c'est marqué explicitement **« supposé / non
vérifié »**.

Repères de gravité : **Bloquant** (empêche le projet de fonctionner tel quel) · **Majeur**
(dégrade fortement l'usage, demande un vrai contournement) · **Mineur** (gênant mais vivable) ·
**Cosmétique** (visuel/confort) · **Point d'attention** (pas un bug technique, mais un sujet à
trancher soi-même).

---

## Top 10 des pièges

| # | Problème | Gravité | Comment l'éviter dès le départ |
|---|----------|---------|----------------------------------|
| 1 | Avec les réglages BirdNET par défaut (seuil de confiance 0.1), on récolte une avalanche de faux positifs — jusqu'à ~83 % de détections non fiables sur certains témoignages | Bloquant | Monter le seuil de confiance à 0.5–0.7 minimum dès l'installation, envisager des seuils par espèce, exclure d'emblée les espèces non-oiseaux (insectes, chauves-souris) du modèle |
| 2 | Les bruits du quotidien sont pris pour des oiseaux de façon *récurrente et prévisible* : klaxon → Cygne trompette (95 % confiance), feu d'artifice → Bihoreau gris, aboiement de chien → Grand corbeau/faisan | Majeur | Constituer une liste d'exclusion locale dès le premier mois d'écoute ; activer le filtre « humain »/confidentialité même s'il est imparfait |
| 3 | BirdNET-Pi (`mcguirepr89/BirdNET-Pi`), le projet historique le plus documenté sur le web, est **archivé et non maintenu depuis août 2025** | Bloquant (à moyen terme) | Partir sur `tphakala/birdnet-go` (actif, c'est ce qu'utilise Fugleramme) ou le fork `Nachtzuster/BirdNET-Pi` — pas sur le dépôt original |
| 4 | Le passage à Bookworm (2023) puis Trixie (2025) casse `RPi.GPIO` et une partie des libs GPIO existantes, dont potentiellement le pilote de l'écran e-ink | Bloquant | Vérifier la compatibilité OS de chaque lib *avant* de choisir la version de Raspberry Pi OS ; utiliser `gpiozero`/`lgpio`, jamais `RPi.GPIO`, sur une install neuve |
| 5 | L'Inky Impression 13,3" met réellement 20–35 s à se rafraîchir (pas les ~12 s annoncés), et la dalle en verre est décrite comme « extrêmement fragile » par Pimoroni lui-même | Majeur | Concevoir l'UI en acceptant des rafraîchissements lents et rares (1/minute maximum recommandé par Pimoroni) ; manipuler la dalle avec des gants et sans jamais appuyer dessus |
| 6 | Le micro USB peut « disparaître » après un redémarrage, sans erreur visible dans les logs, et rester silencieux indéfiniment | Majeur | Identifier le périphérique par ID/série USB stable (pas par index `hw:N`, qui change) ; prévoir un service de supervision qui détecte l'absence de signal audio et relance |
| 7 | En fonctionnement 24/7, la carte SD se corrompt ou le disque sature en quelques jours à quelques semaines (enregistrements + logs) | Bloquant | Démarrer et stocker sur SSD/NVMe USB plutôt que sur la carte SD ; activer une politique de purge automatique **dès l'installation**, pas après le premier incident |
| 8 | Étanchéifier un micro extérieur n'a pas de solution commerciale simple — « surprisingly hard to find », tout le monde bricole son boîtier | Majeur | Budgéter du temps (et des itérations) pour un boîtier fait-maison avec évent anti-condensation + mousse anti-vent ; ne pas espérer un micro USB « étanche » prêt à l'emploi |
| 9 | BirdWeather est peu fiable en usage réel : stats bloquées à zéro, erreurs 403, voire gel complet du système à l'activation de l'upload | Majeur | Traiter BirdWeather comme un bonus optionnel et non bloquant, jamais comme un composant central du pipeline |
| 10 | Le cadre juridique français sur un micro extérieur qui capte en continu (et donc parfois des voisins) n'est pas clair, et aucune doctrine CNIL spécifique à ce type de projet n'existe | Point d'attention | Se renseigner activement (CNIL, article 226-1 du code pénal) avant un déploiement extérieur permanent ; garder le filtre de confidentialité activé même s'il n'est pas parfait |

---

## 1. BirdNET : faux positifs, calibration, biais géographique

### 1.1 Le taux de faux positifs réel

Le réglage par défaut de BirdNET (seuil de confiance 0.1) génère énormément de bruit. Sur le wiki
officiel de BirdNET-Pi, les mainteneurs eux-mêmes recommandent d'augmenter fortement ce seuil et
expliquent que la sensibilité et la spécificité sont indissociables :
> « It's a decision the user has to make: increase sensitivity and accept lower specificity, OR
> decrease sensitivity for better specificity »
— [BirdNET-Pi wiki, théorie de classification](https://github.com/mcguirepr89/BirdNET-Pi/wiki/BirdNET-Pi:-some-theory-on-classification-&-some-practical-hints)

Un utilisateur ayant analysé 189 910 détections sur sa propre installation a trouvé que 48 650
d'entre elles (~20 %) se situaient dans la tranche 75–80 % de confiance, et conclut que cette
tranche est statistiquement suspecte :
> « My conclusion is that these species detections in the 75-80% range are suspect, and therefore
> I'm happy to exclude them. »
— [captainbodgit.blogspot.com, mai 2025](http://captainbodgit.blogspot.com/2025/05/birdnetpi-false-positives-conf-level.html)

Le même auteur a aussi testé la répétabilité : en relançant l'analyse du **même fichier audio 5
fois de suite**, BirdNET-Go a détecté un Pigeon ramier seulement 1 fois sur 5, et le nombre total
d'événements détectés a varié de 11 à 13 selon les runs :
> « I'm never sure what to accept and what to reject from our BirdNet systems »
— [captainbodgit.blogspot.com, octobre 2025](http://captainbodgit.blogspot.com/2025/10/birdnet-systems-testing-2-critical.html)

### 1.2 Faux positifs déclenchés par le bruit ambiant — des motifs récurrents et documentés

- **Klaxons de voiture → Cygne trompette à 95 % de confiance**, de façon systématique :
  [tphakala/birdnet-go#2741](https://github.com/tphakala/birdnet-go/issues/2741)
- **Feux d'artifice du Nouvel An → Bihoreau gris** et **aboiements du chien du voisin → Grand
  corbeau / Perdrix rouge / Faisan de Colchide** :
  [captainbodgit.blogspot.com](http://captainbodgit.blogspot.com/2025/05/birdnetpi-false-positives-conf-level.html)
- **Sirènes** : demande de fonctionnalité pour filtrer les sirènes par localisation, preuve que
  c'est un problème vécu par plusieurs utilisateurs :
  [tphakala/birdnet-go#1425](https://github.com/tphakala/birdnet-go/issues/1425)
- **Bruit urbain en général confondu avec le Butor étoilé** (dont le ton grave à 150 Hz ressemble
  à un moteur de voiture qui démarre, un hélicoptère ou un avion), qui a motivé une demande de
  « mode urbain » avec liste d'exclusion communautaire pour l'Europe :
  [mcguirepr89/BirdNET-Pi#115](https://github.com/mcguirepr89/BirdNET-Pi/issues/115) (liste
  d'espèces européennes à exclure en ville fournie par la communauté dans les commentaires)
- **Le modèle BirdNET n'est pas exclusivement composé d'oiseaux** : le jeu d'étiquettes v2.4
  inclut des insectes (ex. le grillon *Oecanthus fultoni*), donc des détections d'insectes sont
  attendues et « normales », pas un bug :
  [tphakala/birdnet-go#4063](https://github.com/tphakala/birdnet-go/issues/4063)

### 1.3 Réglage du seuil de confiance — ce que font les gens en pratique

- Sensibilité (sigmoid) : plage valide 0.5–1.5, la communauté recommande 1.0–1.25 ; un seuil de
  confiance minimum de 0.5–0.7 (au lieu du défaut 0.1) est le point de départ typique
  — [BirdNET-Pi discussion #507](https://github.com/mcguirepr89/BirdNET-Pi/discussions/507),
  [BirdNET-Pi wiki](https://github.com/mcguirepr89/BirdNET-Pi/wiki/BirdNET-Pi:-some-theory-on-classification-&-some-practical-hints)
- BirdNET-Go a un système de **seuil dynamique** qui abaisse automatiquement le seuil pour une
  espèce déjà détectée avec confiance, ce qui peut dérouter un utilisateur qui a réglé un seuil
  fixe à 0.8 et voit quand même apparaître des détections plus faibles :
  [tphakala/birdnet-go#239](https://github.com/tphakala/birdnet-go/issues/239) (le mainteneur
  explique le mécanisme dans les commentaires, avec un lien vers la doc dédiée)
- Un utilisateur a vu ses détections **massivement chuter du jour au lendemain après une mise à
  jour**, sans erreur dans les logs — cas non résolu au moment de la recherche, qui montre que le
  pipeline de filtrage peut changer de comportement silencieusement d'une version à l'autre :
  [tphakala/birdnet-go#3225](https://github.com/tphakala/birdnet-go/issues/3225) (20 commentaires)

### 1.4 Filtrage par localisation/saison — utile mais loin d'être infaillible

Le principe (filtrer la liste d'espèces possibles par lat/lon + période de l'année) est réel et
recommandé, mais plusieurs bugs et limites sont documentés :

- **Détection géographiquement impossible malgré le filtre** : un Milan du Mississippi détecté à
  78 % de confiance en Virginie du Nord en décembre (semaine 46), alors que l'espèce n'y est
  jamais présente en hiver — l'utilisateur a vérifié que la génération de la liste d'espèces avec
  les mêmes paramètres ne donnait pas ce résultat, suggérant que le filtre saisonnier n'était pas
  réellement appliqué au moment de l'analyse (« geographical data is really old ») :
  [mcguirepr89/BirdNET-Pi#670](https://github.com/mcguirepr89/BirdNET-Pi/issues/670)
- **Bug du filtre géographique lui-même** : la liste d'espèces filtrée passe parfois de ~184
  espèces (attendu pour la localisation) à plus de 6000 espèces avec 0 détectable, de façon
  intermittente : [tphakala/birdnet-go#3151](https://github.com/tphakala/birdnet-go/issues/3151)
- Une demande de fonctionnalité montre que même des utilisateurs avertis se retrouvent avec des
  « détections à 95 %+ de confiance d'oiseaux qui ne sont clairement pas dans leur région » et
  doivent réclamer un filtrage géographique plus robuste :
  [tphakala/birdnet-go#574](https://github.com/tphakala/birdnet-go/issues/574)
- **Piège spécifique au modèle « Central Europe »** : sur Raspberry Pi 5, le modèle régional
  optimisé recommandé pour l'Europe centrale (Perch v2, variante FP32 no-dft) donnait des
  détections systématiquement fausses (décalage dans la liste d'espèces) à cause d'un bug de
  précision FP16 dans le backend OpenVINO sur ARM — contournement : forcer le backend ONNX ou
  utiliser le modèle non optimisé : [tphakala/birdnet-go#4206](https://github.com/tphakala/birdnet-go/issues/4206)
  (bug confirmé et diagnostiqué par le mainteneur/bot de support dans les commentaires)

### 1.5 Faux positifs de chauve-souris (si jamais activé)

Le classificateur de chauve-souris de BirdNET-Go produit des détections à confiance très élevée
(jusqu'à 99,9 %) sur du bruit ambiant sans aucun appel d'écholocation visible sur le spectrogramme
ultrasonique correspondant :
[rdz-oss/BattyBirdNET-Analyzer#32](https://github.com/rdz-oss/BattyBirdNET-Analyzer/issues/32)

### 1.6 Biais géographique : Amérique du Nord vs Europe/France

C'est un sujet à nuancer, pas à trancher dans un sens unique :

- **Le modèle de détection lui-même** semble globalement correct en Europe : une étude publiée
  (PLOS One, 2024) intitulée *« BirdNET can be as good as experts for acoustic bird monitoring in
  a European city »* rapporte un score F1 de 0,84 avec agrégation temporelle en ville, à condition
  d'utiliser un seuil global autour de 0,6 pour une précision > 0,8 ; l'étude signale aussi que le
  modèle a manqué 5 espèces sur 23 que des experts humains ont identifiées. **Limite de
  vérification** : le PDF complet renvoyait une erreur HTTP 429 lors de la recherche ; seul le
  résumé a pu être confirmé, donc à prendre avec cette réserve. Source :
  [biorxiv.org/content/10.1101/2024.09.17.613451](https://www.biorxiv.org/content/10.1101/2024.09.17.613451v3.full)
- **Le catalogue d'illustrations de Fugleramme**, en revanche, est explicitement centré sur
  l'Amérique du Nord à l'origine, avec pour source principale *Birds of America* d'Audubon. Une
  issue ouverte de longue date recense une cinquantaine d'espèces européennes couramment
  observées par des utilisateurs mais dont l'illustration manque encore au catalogue (à date de la
  recherche, une bonne partie des cases sont cochées mais plusieurs dizaines restent
  ouvertes) : [arnegiacomo/fugleramme#44 « Missing european birds »](https://github.com/arnegiacomo/fugleramme/issues/44)
  et [arnegiacomo/fugleramme#33 « North American bird assets »](https://github.com/arnegiacomo/fugleramme/issues/33).
  **Implication concrète pour ce projet** : même si BirdNET détecte correctement une Corneille
  noire ou une Grive musicienne, Fugleramme peut ne pas avoir de planche pour l'afficher tant que
  la communauté n'a pas ajouté l'illustration.
- **Piège de réconciliation taxonomique** : une reclassification d'espèce (ex. *Ixobrychus
  minutus* renommé *Botaurus minutus* en 2023) fait que BirdNET-Go loggue le même oiseau sous deux
  noms scientifiques différents après une mise à jour ; côté Fugleramme, la planche existante
  (nommée sous l'ancien nom) ne correspond plus jamais aux nouvelles détections, et l'espèce est
  comptée deux fois dans la liste vue. C'est un bug rencontré par le mainteneur lui-même sur son
  propre cadre, encore en discussion sur la meilleure façon de le corriger (alias interne vs
  correctif en amont) : [arnegiacomo/fugleramme#65](https://github.com/arnegiacomo/fugleramme/issues/65)
- **Contre-exemple anecdotique** : les logs d'un utilisateur allemand de BirdNET-Pi montrent des
  détections courantes et cohérentes d'espèces locales (Pinson des arbres, Mésange charbonnière,
  Fauvette à tête noire, Gobemouche noir), preuve que la détection fonctionne au quotidien pour
  des utilisateurs européens : [mcguirepr89/BirdNET-Pi#863](https://github.com/mcguirepr89/BirdNET-Pi/issues/863)
  (mais ceci ne mesure ni précision ni rappel, juste que le pipeline tourne).
- **Non trouvé / suspicion non vérifiée** : les chiffres précis d'entraînement (« 595 espèces
  nord-américaines vs 555 espèces européennes ») évoqués dans certaines recherches n'ont pas pu
  être rattachés à une source précise et vérifiable — à traiter comme un ordre de grandeur
  approximatif, pas un fait confirmé.

### 1.7 Confidentialité et détection de voix humaine (voir aussi § 6)

Le filtre de confidentialité de BirdNET-Pi (`PRIVACY_MODE`) ne supprime pas totalement les voix,
seulement les échantillons où une voix est en tête des 100 premières prédictions :
[mcguirepr89/BirdNET-Pi#227](https://github.com/mcguirepr89/BirdNET-Pi/issues/227) — un
utilisateur rapporte encore capter des voix faibles de sa famille en arrière-plan malgré le mode
activé. Côté BirdNET-Go, un bug confirmé faisait que le seuil de confiance du filtre de
confidentialité ignorait complètement la valeur configurée et retombait toujours sur 0.05 par
défaut, aussi bien globalement que par espèce :
[tphakala/birdnet-go#4068](https://github.com/tphakala/birdnet-go/issues/4068) (corrigé depuis,
mais montre que ce filtre a eu des régressions en production).

---

## 2. L'écran e-ink Inky Impression 13,3"

### 2.1 Durée de rafraîchissement réelle

Un rapport technique très détaillé, avec mesures à l'appui, montre un **bug de polarité du signal
BUSY** sur l'Inky Impression 13,3" (EL133UF1) sous Pi 5 / Trixie / lib `inky` 2.4.0 : la fonction
`show()` retourne environ **19 secondes avant que le panneau ait réellement fini de se
rafraîchir**, et la commande d'extinction (POF) est envoyée pendant que le rafraîchissement est
encore en cours. Le rapport mesure aussi ~6,6 s de temps mort par rafraîchissement dû à un bug de
polling :
[pimoroni/inky#266](https://github.com/pimoroni/inky/issues/266)

Selon un employé Pimoroni (Gadgetoid) sur le forum officiel, l'intervalle minimum recommandé entre
deux rafraîchissements est d'**une minute**, et Pimoroni n'a testé la fiabilité de ses dalles qu'à
des intervalles de 30 secondes sur « des dizaines de milliers de cycles » — au-delà, c'est
inconnu :
> « The minimum we'd recommend is 1 minute (...) we just don't know what might happen »
— [forums.pimoroni.com, fiabilité e-paper](https://forums.pimoroni.com/t/e-paper-e-ink-display-reliability/8809)

### 2.2 Ghosting, burn-in, dégradation

Le ghosting (image rémanente après rafraîchissement) est une caractéristique intrinsèque de la
technologie e-ink, pas un bug — Pimoroni fournit d'ailleurs un script `clean.py` dédié à
« nettoyer » l'écran avec des passages de couleurs pures :
[forum.core-electronics.com.au](https://forum.core-electronics.com.au/t/e-ink-display-integration-ghosting-and-refresh-challenges/23151)
(source rapportée par l'agent de recherche, non re-vérifiée personnellement).

**Non trouvé / suspicion non vérifiée** : malgré une recherche ciblée (issues GitHub, forums
Pimoroni, Reddit), **aucun témoignage documenté de burn-in permanent** (gravure irréversible d'une
image statique) sur l'Inky Impression 13,3" n'a été trouvé. C'est un risque théorique connu sur
d'autres technologies e-ink (liseuses) mais pas confirmé spécifiquement sur ce modèle. De même,
**aucune source vérifiée sur le comportement au froid/à l'humidité** n'a été trouvée au-delà de la
plage de fonctionnement générique annoncée par Adafruit (0–50 °C, sans donnée sur l'humidité
relative) — ce dernier point (0–50 °C) provient d'une fiche produit Adafruit rapportée par l'agent
de recherche et n'a pas été re-vérifié personnellement.

### 2.3 Casse et fragilité physique

Pimoroni prévient explicitement sur sa propre fiche produit que la dalle est en verre et
« extrêmement fragile », qu'il ne faut ni la faire tomber ni appuyer dessus, et que les boutons
latéraux avaient tendance à se casser pendant le transport avant que le design ne soit revu en
novembre 2025 (boutons déplacés à l'arrière) — source rapportée par l'agent de recherche
(shop.pimoroni.com), non re-vérifiée personnellement par récupération directe de page. Deux
signalements de forum (également non re-vérifiés personnellement) décrivent une moitié d'écran qui
cesse de se rafraîchir après manipulation/transport, compatible avec un défaut de nappe/connectique
interne plutôt qu'un défaut de dalle.

### 2.4 Bruit de fonctionnement

Le modèle 13,3" (contrairement aux 7,3" et 5,7") produit un cliquetis audible pendant le
rafraîchissement, confirmé comme normal par un modérateur Pimoroni. Un utilisateur a trouvé qu'un
condensateur de 1000 µF entre le 3V3 et la masse de l'écran atténue significativement ce bruit
(bricolage non officiel) :
[forums.pimoroni.com, « makes noise when updating »](https://forums.pimoroni.com/t/inky-impression-13-3-makes-noise-when-updating/28292)
— vérifié directement, citations confirmées.

### 2.5 SPI, GPIO, conflits, bugs de la lib `inky`

C'est la catégorie la plus documentée. Points confirmés :

- **Conflit SPI CS0 sous Bookworm récent** : la lib essaie de piloter directement GPIO8 (Chip
  Select) alors que le noyau détient déjà cette broche via le driver SPI natif — erreur
  « pins we need are in use! Chip Select currently claimed by spi0 CS0 » :
  [pimoroni/inky#202](https://github.com/pimoroni/inky/issues/202),
  [pimoroni/inky#229](https://github.com/pimoroni/inky/issues/229)
- **Incompatibilité Pi 5 / Bookworm** générale du driver au moment de la transition (nécessitait
  une pré-version) : [pimoroni/inky#183](https://github.com/pimoroni/inky/issues/183),
  [pimoroni/inky#186 « Can't get Inky to work on Raspberry Pi Zero 2 W »](https://github.com/pimoroni/inky/issues/186)
  (résolu via une pré-release pointée dans [pimoroni/inky#182](https://github.com/pimoroni/inky/pull/182))
- **Installation sur Pi Zero 2 W qui échoue** avec des erreurs de compilation Pillow/numpy/lxml,
  contournement = ordre précis de commandes `apt`/`pip` trouvé empiriquement par les utilisateurs
  dans les commentaires, pas documenté officiellement au moment du signalement :
  [pimoroni/inky#220](https://github.com/pimoroni/inky/issues/220) — pertinent puisque
  **Inky Bird Frame utilise justement un Pi Zero 2 W**
- **EEPROM non détectée** → bascule sur initialisation manuelle du modèle d'écran, avec un bug
  logiciel additionnel (`.keys` utilisé sans parenthèses) qui plantait le driver, corrigé en
  revenant à une version antérieure de la lib :
  [pimoroni/inky#136](https://github.com/pimoroni/inky/issues/136),
  [pimoroni/inky#201](https://github.com/pimoroni/inky/issues/201)
- **Conflit avec des cartes d'extension** (ex. Witty Pi en I2C) : sur Pi Zero W/3, le signal BUSY
  reste bloqué et le rafraîchissement ne se termine jamais si une autre carte partage les mêmes
  GPIO — [pimoroni/inky#282](https://github.com/pimoroni/inky/issues/282)

### 2.6 Spécifique aux deux projets de référence

- **Les oiseaux blancs disparaissent sur le fond e-ink** : *Aegithalos caudatus* (Mésange à longue
  queue) et *Larus argentatus* (Goéland argenté) sont plus blancs que le blanc du « papier »
  affiché par l'écran, donc invisibles en pratique. Issue ouverte, non résolue au moment de la
  recherche : [arnegiacomo/fugleramme#138](https://github.com/arnegiacomo/fugleramme/issues/138)
- Le support officiel du Pi Zero 2 W par Fugleramme n'est **pas encore validé** par le mainteneur
  lui-même : « reported working (client only), just slower to render. Needs a unit to verify
  before it can be documented as supported » :
  [arnegiacomo/fugleramme#61](https://github.com/arnegiacomo/fugleramme/issues/61)

---

## 3. Le Raspberry Pi en fonctionnement continu

### 3.1 Corruption de carte SD

C'est le classique. Une installation confrontée à des erreurs fatales après quelques jours a
identifié la cause réelle : le disque saturé (pas la SD corrompue au sens strict), avec la
politique de purge automatique mal configurée :
[mcguirepr89/BirdNET-Pi#619](https://github.com/mcguirepr89/BirdNET-Pi/issues/619). Un autre
utilisateur a documenté un blocage récurrent du script d'analyse quand le débit d'enregistrement
dépasse la capacité d'analyse (la carte SD n'arrive pas à suivre) ; passer sur un SSD NVMe externe
a résolu le problème, avec ce commentaire explicite :
> « A clear recommendation not to use an SD card. »
— [mcguirepr89/BirdNET-Pi#1099](https://github.com/mcguirepr89/BirdNET-Pi/issues/1099)

Les recommandations générales (UPS, démarrage/stockage sur USB/SSD plutôt que SD, overlay en
lecture seule) proviennent d'un fil du forum officiel Raspberry Pi rapporté par l'agent de
recherche et **non re-vérifié personnellement** :
[forums.raspberrypi.com, t=272200](https://forums.raspberrypi.com/viewtopic.php?t=272200).

### 3.2 Surchauffe du Raspberry Pi 5

Les seuils de throttling matériel (80 °C = ralentissement progressif, 85 °C = ralentissement
fort) et un cas où des coupures complètes attribuées à tort à la surchauffe se sont révélées être
un problème d'alimentation sous-dimensionnée (adaptateur générique 65 V/3A insuffisant, résolu
avec le bloc officiel 27 W) proviennent de fils du forum officiel Raspberry Pi rapportés par
l'agent de recherche et **non re-vérifiés personnellement** :
[forums.raspberrypi.com, t=368073](https://forums.raspberrypi.com/viewtopic.php?t=368073),
[forums.raspberrypi.com, t=370876](https://forums.raspberrypi.com/viewtopic.php?t=370876). Ce
point mérite d'être gardé en tête vu que Fugleramme annonce lui-même un refroidisseur actif comme
« obligatoire » sur Pi 5 (voir CLAUDE.md du projet).

### 3.3 Coupures de courant

Conséquence directe du risque de corruption SD (§3.1) : une coupure pendant une écriture peut
laisser le système dans un état incohérent nécessitant un reflash complet. Pas de source
supplémentaire indépendante trouvée au-delà de ce qui est cité en 3.1.

### 3.4 Le Raspberry Pi Zero 2 W est-il trop faible ?

Le verdict est nuancé : **ça tourne, mais c'est tendu**.

- Côté Fugleramme même, le support Pi Zero 2 W n'est documenté qu'à l'état « reported working,
  slower to render, needs a unit to verify » par le mainteneur — donc pas garanti :
  [arnegiacomo/fugleramme#61](https://github.com/arnegiacomo/fugleramme/issues/61)
- Sur le Pi 3B (encore plus faible que le Zero 2W en RAM mais comparable en CPU), le mainteneur de
  BirdNET-Pi confirme que ça fonctionne mais seulement avec zRAM configuré en swap, et prévient :
  « Adequate cooling is a must!! » : [mcguirepr89/BirdNET-Pi#66](https://github.com/mcguirepr89/BirdNET-Pi/issues/66)
  (115 commentaires, fil de référence sur le sujet)
- Des retours (rapportés par l'agent de recherche, **non re-vérifiés personnellement**) évoquent
  un système « marginal » sur Pi Zero 2 W : boot très long, interface web quasi inutilisable,
  blocages occasionnels (~1 fois/semaine), nécessité de couper des services non essentiels
  (spectrogramme, stats, streaming audio en direct) et d'utiliser au moins 2 Go de swap :
  [forums.raspberrypi.com, t=367319](https://forums.raspberrypi.com/viewtopic.php?t=367319),
  [Nachtzuster/BirdNET-Pi discussion #133](https://github.com/Nachtzuster/BirdNET-Pi/discussions/133)

### 3.5 Wifi qui se déconnecte

Deux causes bien distinctes, confirmées :

- **Le mode économie d'énergie wifi**, activé par défaut sur Raspberry Pi OS, met en veille le wifi
  en cas d'inactivité et ne le réveille pas toujours correctement — source rapportée par l'agent de
  recherche, **non re-vérifiée personnellement**.
- **Un vrai bug sous Trixie (2025)** : déconnexions wifi après 4 à 18 h de fonctionnement stable
  sur Raspberry Pi 5, confirmé comme un ticket ouvert du dépôt officiel de retours Trixie — vérifié
  directement : [raspberrypi/trixie-feedback#25](https://github.com/raspberrypi/trixie-feedback/issues/25)
  (titre confirmé : « WiFi disconnects after some time, does not reconnect »)

### 3.6 Le piège de la mise à jour Bookworm/Trixie et les bibliothèques GPIO

C'est un point majeur et bien confirmé, avec plusieurs sources vérifiées directement :

- Le script d'installation de BirdNET-Pi **échoue explicitement sur Bookworm** — l'issue demande
  de mettre à jour le wiki pour dire clairement d'installer Bullseye et pas Bookworm ; vérifié
  directement (titre et corps confirmés) :
  [mcguirepr89/BirdNET-Pi#1202](https://github.com/mcguirepr89/BirdNET-Pi/issues/1202)
- Sur Raspberry Pi 5, le noyau a changé le numéro de puce GPIO utilisé (`gpiochip` passe à 0),
  mais `gpiozero` avec le pin factory `lgpio` avait un numéro de puce **codé en dur à 4**, cassant
  silencieusement toute détection de broche — vérifié directement (corps confirmé, avec
  traceback) : [gpiozero/gpiozero#1166](https://github.com/gpiozero/gpiozero/issues/1166)
- `RPi.GPIO`, préinstallé par défaut sur Bookworm mais non officiellement supporté par la fondation
  Raspberry Pi (qui recommande `gpiozero`), casse en particulier sur le Pi 5 (puce RP1 différente)
  — points rapportés par l'agent de recherche via le forum officiel, **non re-vérifiés
  personnellement** :
  [forums.raspberrypi.com, t=371548](https://forums.raspberrypi.com/viewtopic.php?t=371548),
  [forums.raspberrypi.com, t=372507](https://forums.raspberrypi.com/viewtopic.php?t=372507)
- Côté écran, ce même changement d'écosystème GPIO explique une bonne partie des soucis listés en
  §2.5 (conflit SPI CS0, Pi 5 incompatible avant pré-release, `buttons.py` cassé sous Bookworm sur
  Pi 5 — [pimoroni/inky#192](https://github.com/pimoroni/inky/issues/192)).

**Conclusion pratique** : ce n'est pas un problème abstrait, c'est un piège très concret quand on
part d'un tutoriel un peu ancien (beaucoup de guides BirdNET-Pi datent de l'ère Bullseye) ou quand
on met à jour l'OS d'une installation existante sans revérifier la compatibilité GPIO de chaque
composant.

---

## 4. L'audio

### 4.1 Détection et stabilité du périphérique USB

- Un microphone USB visible par le système (`arecord -l`) mais absent de la liste des
  périphériques dans l'interface web de BirdNET-Go — source rapportée par l'agent de recherche,
  **non re-vérifiée personnellement** : `tphakala/birdnet-go#1506`.
- **Perte de micro après redémarrage** : le système redémarre mais reste silencieux (spectrogrammes
  vides), sans qu'aucune manipulation (redémarrage des services, débranchement/rebranchement) ne
  résolve le problème — seule solution documentée : réinstaller entièrement la carte SD. Titre
  confirmé (« Losing Microphone Input After Crash / Reboots »), contenu rapporté par l'agent de
  recherche : [mcguirepr89/BirdNET-Pi#1036](https://github.com/mcguirepr89/BirdNET-Pi/issues/1036)
- **Instabilité des index ALSA** : le noyau attribue les index de cartes son (`hw:0`, `hw:1`...)
  dans l'ordre de détection USB, qui n'est pas garanti stable d'un redémarrage à l'autre — avec
  deux micros USB, ils peuvent s'inverser silencieusement. Rapporté par l'agent de recherche, **non
  re-vérifié personnellement** : `tphakala/birdnet-go-remote-mic#62`.

### 4.2 Placement, pluie, vent

- **Pas de micro USB étanche « prêt à l'emploi »** : un utilisateur cherchant explicitement un
  micro USB étanche à suspendre à une fenêtre conclut que c'est « surprisingly hard to find » —
  issue ouverte sans solution, vérifiée directement :
  [mcguirepr89/BirdNET-Pi#1001](https://github.com/mcguirepr89/BirdNET-Pi/issues/1001)
- **L'humidité est plus dure à gérer que la pluie** selon un utilisateur suédois faisant tourner
  son installation en extérieur : petit trou d'aération anti-condensation, film alimentaire + ruban
  PVC, boîtiers en fonte, ports USB étanches montés en bas du boîtier — rapporté par l'agent de
  recherche, **non re-vérifié personnellement** : `mcguirepr89/BirdNET-Pi discussion #69`.
- **Solution DIY qui a tenu 1,5 an en extérieur** (toutes conditions météo, Suède) : capsule
  électret PUI AOM 5024 protégée par une mousse anti-vent bon marché + fausse fourrure — mais la
  mousse n'est pas résistante aux UV et doit être remplacée régulièrement. Rapporté par l'agent de
  recherche, **non re-vérifié personnellement** : `mcguirepr89/BirdNET-Pi discussion #373`.
- **Câble jusqu'à 15 m en extérieur** : un utilisateur sur lande écossaise (pluie battante
  horizontale) documente sa configuration avec micro cravate TRRS + adaptateur, câble cheminant le
  long des murs. Confirmé directement (corps du message) :
  [mcguirepr89/BirdNET-Pi discussion #277](https://github.com/mcguirepr89/BirdNET-Pi/discussions/277)
- **Piège de connecteur TRS vs TRRS** : les adaptateurs 3,5 mm à 3 anneaux (TRRS, pensés pour les
  micros de smartphone) sont incompatibles avec les micros électret 2 anneaux (TRS) — source
  rapportée par l'agent de recherche, **non re-vérifiée personnellement** :
  `Nachtzuster/BirdNET-Pi discussion #476`.
- **Non trouvé / suspicion non vérifiée** : aucune source précise n'a été trouvée documentant
  spécifiquement la **saturation de l'enregistrement par le bruit du vent** (au-delà des
  recommandations générales de mousse anti-vent ci-dessus) — c'est un problème plausible et
  généralement connu en captation audio extérieure, mais pas confirmé par un témoignage BirdNET
  précis.

### 4.3 ALSA/PulseAudio et configuration qui ne persiste pas

Le réglage de carte son ne survit pas toujours à un redémarrage si on ne renseigne pas le nom
exact du périphérique tel que retourné par `arecord -L` (ex. `dsnoop:CARD=H1,DEV=0`) plutôt qu'un
nom raccourci — rapporté par l'agent de recherche, **non re-vérifié personnellement** :
`mcguirepr89/BirdNET-Pi discussion #551`.

### 4.4 Consommation CPU

Un correctif de bug dans BirdNET-Go (le paramètre `threads: 0` restait mono-thread par erreur) a
fait passer la consommation CPU moyenne de ~6 % à ~15 %+ une fois corrigé, car le logiciel
utilise désormais tous les cœurs disponibles par défaut — recommandation : plafonner explicitement
`birdnet.threads`. Rapporté par l'agent de recherche, **non re-vérifié personnellement** :
`tphakala/birdnet-go discussion #3163`.

### 4.5 Bruit électrique via les ports USB du Pi 4

Un bourdonnement 50/60 Hz peut être injecté dans l'enregistrement via les ports USB du Pi 4
(« dirty power »), avec comme solutions un isolateur galvanique USB, un hub alimenté de qualité,
ou une mise à la masse commune — rapporté par l'agent de recherche, **non re-vérifié
personnellement** : `tphakala/birdnet-go discussion #3659`.

### 4.6 Le stockage qui se remplit

Un cas documenté de disque saturé (0 octet libre sur ~113 Go) en 1-2 jours sur un Pi 4B — rapporté
par l'agent de recherche avec une citation faible (pas de quote exacte vérifiée), **à confirmer** :
`mcguirepr89/BirdNET-Pi#1131`. Ce risque est cohérent avec les cas vérifiés en §3.1
([#619](https://github.com/mcguirepr89/BirdNET-Pi/issues/619),
[#1099](https://github.com/mcguirepr89/BirdNET-Pi/issues/1099)) où la purge automatique mal
configurée est explicitement en cause.

### 4.7 Qualité du microphone

Une comparaison informelle (pas une étude contrôlée) rapporte qu'un micro USB correct (Rode NT USB,
~125 €) donnait 7× plus de détections et 3× plus d'espèces qu'un micro à ~20 €, et qu'une capsule
électret DIY à 2,70 € (PUI AOM 5024) aurait même fait ~14 % mieux que le Rode NT USB dans ce test —
chiffres à prendre avec prudence puisqu'il s'agit d'un retour d'expérience unique, pas d'un
protocole scientifique. Rapporté par l'agent de recherche, **non re-vérifié personnellement** :
`mcguirepr89/BirdNET-Pi discussion #1092`.

---

## 5. Les APIs (eBird, iNaturalist, BirdWeather)

### 5.1 eBird

Le support officiel eBird indique un délai d'approbation type de 7 jours — mais **attention à la
nuance** : cette phrase concerne spécifiquement les demandes d'accès au jeu de données complet
(EBD, *eBird Basic Dataset*, pour du téléchargement en masse), pas nécessairement l'obtention
d'une clé pour l'API `api.ebird.org` (celle qu'utilise Inky Bird Frame pour les observations dans
un rayon de 50 km). Vérifié directement, mais avec cette réserve importante :
> « New requests are typically approved within 7 days. »
— [support.ebird.org](https://support.ebird.org/en/support/solutions/articles/48000838205-download-ebird-data)

**Non trouvé / suspicion non vérifiée** : aucun témoignage (Reddit, forum) d'un délai plus long ou
d'un refus de clé API eBird n'a été trouvé. Les quotas précis de l'API (souvent cités autour de
« ~1000 requêtes/jour ») n'ont pas pu être confirmés par une source solide — à vérifier directement
sur la documentation Postman officielle avant de concevoir le pipeline.

### 5.2 iNaturalist

Deux fils du forum officiel iNaturalist documentent un comportement réel et gênant : des erreurs
**HTTP 429 (Too Many Requests) alors même que la limite documentée de 60 requêtes/minute est
respectée**, l'erreur survenant après 120 à 190 requêtes plutôt qu'immédiatement (suggérant un bug
d'arrondi côté serveur) ; un modérateur a confirmé qu'un endpoint spécifique appliquait une limite
plus stricte que celle documentée, corrigée depuis. Rapporté par l'agent de recherche, **non
re-vérifié personnellement**, mais avec citations précises et cohérentes :
[forum.inaturalist.org/t/429-error...](https://forum.inaturalist.org/t/429-error-from-observations-histogram-api-when-calling-at-60-calls-minute/64709),
[forum.inaturalist.org/t/discrepancy-between-documented-rate-limit...](https://forum.inaturalist.org/t/discrepancy-between-documented-rate-limit-observed-rate-limit/8612)

**Non trouvé / suspicion non vérifiée** : la limite de téléchargement média (5 Go/heure, 24
Go/jour, blocage permanent en cas de dépassement) a été rapportée sans URL précise vérifiable — à
confirmer sur la documentation officielle avant de s'y fier.

### 5.3 BirdWeather

Trois problèmes distincts et bien documentés :

- **Gel complet du système** à l'activation de l'upload BirdWeather, nécessitant un redémarrage,
  de façon répétée. Vérifié directement (corps du message confirmé) :
  [tphakala/birdnet-go#114](https://github.com/tphakala/birdnet-go/issues/114)
- **Statistiques bloquées à zéro** sur la carte BirdWeather malgré un fonctionnement local correct
  et un « Last Detection » à jour — suggère une déconnexion silencieuse entre la collecte locale et
  l'envoi. Vérifié directement (corps du message confirmé) :
  [mcguirepr89/BirdNET-Pi#1256](https://github.com/mcguirepr89/BirdNET-Pi/issues/1256)
- **Erreur 403 « Access denied »** lors de l'envoi, généralement due à une confusion entre
  l'identifiant de station et le jeton d'API. Vérifié directement (corps du message confirmé) :
  [mcguirepr89/BirdNET-Pi discussion #1209](https://github.com/mcguirepr89/BirdNET-Pi/discussions/1209)

**Non trouvé / suspicion non vérifiée** : l'information selon laquelle BirdWeather n'accepterait
plus que le format audio FLAC depuis juillet 2025 a été rapportée par l'agent de recherche **sans
URL précise vérifiable** (juste « mentionné dans les résultats de recherche ») — à vérifier
directement avant de bâtir un pipeline audio autour de cette hypothèse, ne pas la considérer comme
acquise.

---

## 6. Le juridique / la vie privée en France

**Ce qui a été activement cherché et non trouvé** : aucune doctrine ou communication CNIL
spécifique à un projet type « micro extérieur de détection d'oiseaux » n'a été trouvée, ni par
l'agent de recherche dédié (qui a épuisé son budget de recherche sans résultat sur ce point précis)
ni par des tentatives directes de récupération de pages CNIL/Légifrance ciblées (plusieurs URLs
plausibles ont renvoyé une erreur 404 lors des vérifications de cette session). **C'est donc un vrai
point aveugle de cette veille : traiter la section ci-dessous comme un point de départ, pas comme
un avis juridique.**

Ce qui suit relève de **connaissances juridiques générales** sur le droit français, et non d'une
source fraîche re-vérifiée en ligne pendant cette session (le budget de recherche web a été épuisé
avant d'avoir pu confirmer le texte exact via une page officielle) :

- L'article 226-1 du code pénal français réprime le fait de capter, enregistrer ou transmettre,
  **sans le consentement de leur auteur, des paroles prononcées à titre privé ou confidentiel**
  (peine encourue : 1 an d'emprisonnement et 45 000 € d'amende). Le même article prévoit une
  présomption de consentement quand l'enregistrement a eu lieu « au vu et au su » des personnes
  concernées, sans qu'elles s'y opposent alors qu'elles étaient en mesure de le faire.
- Ce cadre est celui généralement invoqué pour les caméras de vidéosurveillance de particuliers
  qui captent la voie publique ou la propriété d'un voisin (avec ou sans son) — un micro extérieur
  qui capte en continu des conversations de voisins entrerait vraisemblablement dans un cadre
  d'analyse similaire, mais **cette extrapolation n'est pas confirmée par une source spécifique
  trouvée pendant cette recherche**.
- Le RGPD peut aussi s'appliquer si les enregistrements (même à des fins strictement personnelles)
  sont partagés en ligne (BirdWeather, réseaux sociaux) de façon à pouvoir identifier des personnes
  — mais là encore, pas de doctrine CNIL spécifique trouvée sur ce cas précis.

**Recommandation pratique, sans dramatiser** : avant un déploiement extérieur permanent, se
renseigner directement auprès de la CNIL (formulaire de contact sur cnil.fr) ou d'un professionnel
du droit plutôt que de se fier à cette section ; garder activé le filtre de détection de voix
humaine même imparfait (voir §1.7) ; éviter d'orienter le micro directement vers une propriété
voisine ; et, si des extraits audio sont partagés publiquement (BirdWeather, réseaux), vérifier
qu'aucune voix identifiable n'y figure.

---

## 7. Pourquoi les gens abandonnent ce genre de projet

- **Le projet le plus visible du domaine est mort.** `mcguirepr89/BirdNET-Pi`, le dépôt le plus
  cité et documenté sur le web pour ce type de projet, est **archivé depuis le 17 août 2025**
  (vérifié directement via l'API GitHub : `archived: true`, dernier push le 2025-08-17). Le
  mainteneur avait annoncé une pause indéfinie avec ce constat :
  > « the project accumulated change requests that extended far beyond the original intent...
  > it became a rewrite rather than bug fixes »
  — rapporté par l'agent de recherche depuis `mcguirepr89/BirdNET-Pi discussion #1003`, **non
  re-vérifié personnellement**, mais cohérent avec le statut « archived » confirmé indépendamment.
  Conséquence pratique : un nouvel utilisateur qui suit un tutoriel un peu ancien risque
  d'installer un logiciel qui ne recevra plus jamais de correctif.
- **Fragmentation de l'écosystème.** Un nouvel utilisateur doit maintenant choisir entre le dépôt
  original archivé, le fork actif `Nachtzuster/BirdNET-Pi`, et la réécriture complète
  `tphakala/birdnet-go` — sans indication évidente de laquelle privilégier, ce qui est en soi une
  source de découragement précoce (déduction raisonnable à partir des faits vérifiés, pas un
  témoignage direct).
- **Le vrai travail est mécanique, pas logiciel.** Un article de blog indépendant qui a évalué
  BirdNET-Pi pour un usage « homelab » résume ainsi son expérience, confirmée par récupération
  directe de la page :
  > « the weatherproofing: the part nobody has cleanly solved. The community consensus is to
  > shelter the mic under an eave. Sealing it in plastic muffles the exact sound you are trying to
  > capture. »
  — [vdaluz.com/blog/researching-birdnet-pi-for-the-homelab](https://vdaluz.com/blog/researching-birdnet-pi-for-the-homelab/)
  Le même article identifie le choix et le placement du microphone comme « the real constraint »
  du projet — c'est-à-dire que la difficulté n'est pas de faire tourner le logiciel, mais de
  stabiliser l'électronique et le boîtier dans la durée (cohérent avec les problèmes matériels
  documentés en §3 et §4).
- **Les deux projets de référence, eux, sont actuellement actifs** (vérifié directement via l'API
  GitHub à la date de cette recherche) : Fugleramme a 3216 étoiles, 85 forks et 15 issues ouvertes,
  dernier commit le jour de la recherche ; Inky Bird Frame a 189 étoiles, 13 forks et 4 issues
  ouvertes, également poussé le jour de la recherche. **Nuance importante** : Inky Bird Frame a
  encore une issue ouverte intitulée « Track v1.0.0 readiness » avec une période de « soak test »
  de 5 jours en cours au moment de la recherche — c'est donc un logiciel qui ne s'est pas encore
  déclaré stable en version 1.0, malgré une activité de développement soutenue :
  [veteranbv/inky-bird-frame#264](https://github.com/veteranbv/inky-bird-frame/issues/264)

---

## Sources

Vérifiées **directement** pendant cette session (via `gh` CLI sur GitHub, ou récupération directe
de page) :

- [tphakala/birdnet-go#2741](https://github.com/tphakala/birdnet-go/issues/2741) — faux positif klaxon → Cygne trompette
- [tphakala/birdnet-go#239](https://github.com/tphakala/birdnet-go/issues/239) — seuil dynamique, confusion utilisateur
- [tphakala/birdnet-go#3225](https://github.com/tphakala/birdnet-go/issues/3225) — chute de détections après mise à jour
- [tphakala/birdnet-go#4063](https://github.com/tphakala/birdnet-go/issues/4063) — insectes dans le modèle
- [tphakala/birdnet-go#4068](https://github.com/tphakala/birdnet-go/issues/4068) — bug seuil filtre confidentialité
- [tphakala/birdnet-go#4206](https://github.com/tphakala/birdnet-go/issues/4206) — bug modèle « Central Europe » sur Pi 5
- [tphakala/birdnet-go#3681](https://github.com/tphakala/birdnet-go/issues/3681) — exclusion d'espèces cassée par les noms locaux
- [tphakala/birdnet-go#3151](https://github.com/tphakala/birdnet-go/issues/3151) — bug filtre géographique (6000+ espèces)
- [tphakala/birdnet-go#574](https://github.com/tphakala/birdnet-go/issues/574) — demande de filtrage géographique
- [tphakala/birdnet-go#114](https://github.com/tphakala/birdnet-go/issues/114) — gel du système avec BirdWeather
- [mcguirepr89/BirdNET-Pi#115](https://github.com/mcguirepr89/BirdNET-Pi/issues/115) — mode urbain, faux positifs sonores
- [mcguirepr89/BirdNET-Pi#66](https://github.com/mcguirepr89/BirdNET-Pi/issues/66) — fonctionnement sur Pi 3
- [mcguirepr89/BirdNET-Pi#619](https://github.com/mcguirepr89/BirdNET-Pi/issues/619) — erreurs fatales, disque saturé
- [mcguirepr89/BirdNET-Pi#670](https://github.com/mcguirepr89/BirdNET-Pi/issues/670) — détection géographiquement impossible
- [mcguirepr89/BirdNET-Pi#863](https://github.com/mcguirepr89/BirdNET-Pi/issues/863) — arrêt silencieux de l'analyse
- [mcguirepr89/BirdNET-Pi#1099](https://github.com/mcguirepr89/BirdNET-Pi/issues/1099) — boucle de blocage, recommandation anti-SD
- [mcguirepr89/BirdNET-Pi#1202](https://github.com/mcguirepr89/BirdNET-Pi/issues/1202) — installation cassée sous Bookworm
- [mcguirepr89/BirdNET-Pi#1001](https://github.com/mcguirepr89/BirdNET-Pi/issues/1001) — pas de micro USB étanche
- [mcguirepr89/BirdNET-Pi#1256](https://github.com/mcguirepr89/BirdNET-Pi/issues/1256) — stats BirdWeather à zéro
- [mcguirepr89/BirdNET-Pi#227](https://github.com/mcguirepr89/BirdNET-Pi/issues/227) — mode confidentialité imparfait
- [mcguirepr89/BirdNET-Pi discussion #277](https://github.com/mcguirepr89/BirdNET-Pi/discussions/277) — câble micro 15 m
- [mcguirepr89/BirdNET-Pi discussion #1209](https://github.com/mcguirepr89/BirdNET-Pi/discussions/1209) — erreur 403 BirdWeather
- [rdz-oss/BattyBirdNET-Analyzer#32](https://github.com/rdz-oss/BattyBirdNET-Analyzer/issues/32) — faux positifs chauve-souris
- [gpiozero/gpiozero#1166](https://github.com/gpiozero/gpiozero/issues/1166) — bug `gpiochip` sur Pi 5
- [raspberrypi/trixie-feedback#25](https://github.com/raspberrypi/trixie-feedback/issues/25) — wifi qui se déconnecte sous Trixie
- [pimoroni/inky#266](https://github.com/pimoroni/inky/issues/266) — bug BUSY, rafraîchissement réel
- [pimoroni/inky#186](https://github.com/pimoroni/inky/issues/186) — install cassée sur Pi Zero 2 W
- [pimoroni/inky#136](https://github.com/pimoroni/inky/issues/136) — erreur EEPROM, bug `.keys`
- [forums.pimoroni.com, fiabilité e-paper](https://forums.pimoroni.com/t/e-paper-e-ink-display-reliability/8809) — intervalle mini recommandé, cycles non testés
- [forums.pimoroni.com, bruit de rafraîchissement](https://forums.pimoroni.com/t/inky-impression-13-3-makes-noise-when-updating/28292) — cliquetis normal, correctif condensateur
- [captainbodgit.blogspot.com, mai 2025](http://captainbodgit.blogspot.com/2025/05/birdnetpi-false-positives-conf-level.html) — feux d'artifice/chien, tranche 75-80 % suspecte
- [vdaluz.com](https://vdaluz.com/blog/researching-birdnet-pi-for-the-homelab/) — archivage, imperméabilisation non résolue
- [support.ebird.org](https://support.ebird.org/en/support/solutions/articles/48000838205-download-ebird-data) — délai d'approbation EBD (7 jours)
- [arnegiacomo/fugleramme#138](https://github.com/arnegiacomo/fugleramme/issues/138) — oiseaux blancs invisibles sur e-ink
- [arnegiacomo/fugleramme#61](https://github.com/arnegiacomo/fugleramme/issues/61) — Pi Zero 2 W non officiellement validé
- [arnegiacomo/fugleramme#65](https://github.com/arnegiacomo/fugleramme/issues/65) — reclassification taxonomique, doublons
- [arnegiacomo/fugleramme#44](https://github.com/arnegiacomo/fugleramme/issues/44) — espèces européennes manquantes
- [arnegiacomo/fugleramme#33](https://github.com/arnegiacomo/fugleramme/issues/33) — catalogue centré Amérique du Nord
- Statistiques dépôts (`gh api repos/...`) : `arnegiacomo/fugleramme` (3216 ★, 85 forks, 15 issues
  ouvertes, archived: false) et `veteranbv/inky-bird-frame` (189 ★, 13 forks, 4 issues ouvertes) ;
  `mcguirepr89/BirdNET-Pi` confirmé **archived: true** depuis le 2025-08-17.

Rapportées par les agents de recherche dédiés (citations précises fournies, mais **non
re-vérifiées personnellement** pendant cette session — probabilité d'exactitude jugée bonne compte
tenu de la précision des citations et du taux de succès élevé de l'échantillonnage de contrôle
ci-dessus, mais à garder en tête) :

- `captainbodgit.blogspot.com`, octobre 2025 — répétabilité des détections
- `community.home-assistant.io/t/birdnet-discussion/742670` — add-on instable, faux positifs
- `mcguirepr89/BirdNET-Pi discussions #507, #551, #69, #373, #716, #1092` — calibration, humidité, câblage, qualité micro
- `Nachtzuster/BirdNET-Pi discussion #476` — piège connecteur TRS/TRRS
- `Nachtzuster/BirdNET-Pi discussion #133` — Pi Zero 2 W, retours mitigés
- `tphakala/birdnet-go discussions #3163, #3659, #3019` — CPU, bruit électrique, limites chauve-souris
- `tphakala/birdnet-go-remote-mic#62` — instabilité des index ALSA
- `mcguirepr89/BirdNET-Pi discussion #1003` — témoignage du mainteneur sur l'abandon
- `forum.inaturalist.org` (deux fils, rate limiting) — voir §5.2
- `forums.raspberrypi.com` (t=272200, t=368073, t=370876, t=371548, t=372507, t=367319) — voir §3
- `forums.pimoroni.com` (moitié d'écran qui ne se rafraîchit plus, écran endommagé) — voir §2.3
- `shop.pimoroni.com` et `adafruit.com` (fiches produit) — fragilité, plage de température, durée de vie théorique

**Cherché activement et explicitement non trouvé** (à traiter comme suspicion non vérifiée, pas
comme un fait) :
- Burn-in permanent sur l'Inky Impression 13,3"
- Comportement précis au froid/à l'humidité de cette dalle au-delà de la plage générique 0-50 °C
- Chiffres d'entraînement précis du modèle BirdNET par continent
- Doctrine CNIL spécifique à un micro extérieur de détection d'oiseaux
- Témoignages de délai ou refus d'obtention de clé API eBird
- Source précise pour le changement de format audio imposé par BirdWeather (FLAC, juillet 2025)
- Saturation de l'enregistrement par le bruit du vent (documentée en général, pas spécifiquement sur BirdNET)

**Méthode** : 5 agents de recherche (modèle Haiku) ont été lancés en parallèle, un par thème, avec
consigne stricte de vérifier chaque URL avant de la citer et de signaler l'absence de source. En
complément, environ 40 issues/discussions GitHub ont été consultées directement via `gh` CLI par
l'agent rédacteur de ce rapport pour échantillonner et confirmer les affirmations les plus
importantes ou les plus surprenantes — cet échantillonnage n'a révélé aucune source fabriquée,
seulement quelques citations un peu vagues (signalées comme telles ci-dessus). Le budget de
recherche web (WebSearch) de la session a été épuisé avant d'avoir pu boucler complètement le sujet
juridique français (§6) — c'est la limite la plus significative de cette veille.
