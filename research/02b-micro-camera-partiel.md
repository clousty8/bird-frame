# Micro + caméra — rapport PARTIEL (à vérifier)

> ⚠️ **Statut : brouillon non validé.** Ce rapport vient d'un sous-agent orphelin d'une première
> passe de recherche qui s'est mal terminée. Il contient des informations utiles mais **plusieurs
> prix sont douteux** (ex. « Clippy EM272 mono à £3,70 » est manifestement faux — c'est probablement
> le prix d'un accessoire, pas du micro). **Revérifier tout prix avant d'acheter.**
> Le rapport matériel principal est dans `02-materiel.md`.

## Micros — recommandations communauté BirdNET

| Micro | Prix annoncé | Remarque |
|---|---|---|
| Boya BY-LM40 (USB lavalier omni, câble 4 m) | 43,90 € Galaxus / 53,83 € Darty | Le plus cité. Sensibilité un peu faible. |
| Clippy EM272 (capsule Primo EM272Z1, XLR) | £86–111 la paire stéréo | Excellente sensibilité, 14 dBA de bruit propre. Demande une interface XLR + alim fantôme. |
| Capsule EM272Z1 seule | £14,70 | La voie DIY. Vendue aussi par Le Club Biotope (FR). |
| AudioMoth USB | £59,99 (+£6,95 port UE) | Conçu pour le monitoring faune, jusqu'à 384 kHz. |
| PUI Audio AOM-5024L-HD-R | — | Capsule DIY, -24 dB, omni. |

Bon marché : Amazon Basics USB condenser (<30 €), Fifine K669 (~30 €), TONOR TC30, AGPTEK AC02B.
⚠️ Les micros très bon marché manquent de sensibilité et ont du souffle électrique.

**Meilleur rapport qualité/prix DIY identifié** : Behringer UCA202 (~25 €) + capsule EM272 (£14,70) ≈ 45 €,
meilleur qu'un micro USB d'entrée de gamme.

### Cartes son USB (si micro analogique)
- UGREEN USB Audio Adapter ~18 € (estimé)
- Behringer UCA202 ~25 € — historiquement utilisé avec l'EM272 en DIY
- Focusrite Scarlett Solo 4e gén. 125,99 € — alim fantôme 48 V, si budget
- Pisound (Blokas) — pensé pour Raspberry Pi, premium
⚠️ Éviter les cartes son USB sans marque : souffle et buzz.

## Étanchéité du micro en extérieur

Recette communautaire :
1. Boîtier électrique extérieur IP65+, profondeur ≥ 65 mm, couvercle à joint.
2. Câble : 3 tours de ruban isolant + silicone, passage par presse-étoupe M20 à joint comprimé.
3. **Boucle d'égouttage** en U d'environ 5 cm à l'extérieur, fixée par collier — sinon l'eau suit le câble jusque dans le boîtier.
4. Pare-pluie acoustique : pot de semis plastique ~10 cm garni de mousse/feutre 2 mm (colle chaude + silicone).

Presse-étoupe M20 nylon IP68 : 1,42–7,10 € (RS France) ; version laiton 17,55 € HT (Farnell).
Boîtier étanche : 20–40 € estimé (Amazon.fr, ManoMano).

**Réglages** : gain en manuel (pas d'AGC) pour du monitoring 24/7 ; le vent sature — bonnette indispensable.

## Caméra (voie visuelle optionnelle)

- **Pi Camera Module 3** : 12 MP IMX708, autofocus, HDR — 25 $ standard / 35 $ Wide (102°).
  Versions **NoIR** au même prix pour le nocturne avec LED IR. Prix France non confirmé (~25–35 € estimé).
- **Webcam USB** : Logitech C270 (~13–15 €) fonctionne, mais bien moins sensible la nuit qu'une NoIR + IR.

### ⚠️ Google Coral USB TPU — NE PAS ACHETER
Le dépôt edgeTPU de Google aurait été archivé en avril 2026, sans mise à jour des dépendances
depuis ~2022 ; Frigate ne le recommande plus depuis la v0.17 et les runtimes Coral ne sont plus
compatibles avec TensorFlow Lite récent. **À revérifier**, mais la tendance est claire.
Alternative vivante : **Raspberry Pi AI Kit (Hailo-8L, 13 TOPS)**, bien intégré au Pi 5.

## Sources citées par le sous-agent (non revérifiées)
- https://github.com/tphakala/birdnet-go/wiki (page hardware)
- https://github.com/mcguirepr89/BirdNET-Pi/discussions/39
- https://www.wildlifemonitoringsolutions.com/audiomoth
- micbooster.com, veldshop.nl, fr.rs-online.com, Farnell France
- dzombak.com (2025), kindalame.com (2026), beaktech.org
