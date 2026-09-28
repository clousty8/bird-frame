# Cadre, mécanique, alimentation, réseau — rapport PARTIEL

> ⚠️ Rapport issu d'un sous-agent orphelin, mais **le mieux sourcé des quatre** (prix réellement
> relevés sur les pages). Deux réserves signalées plus bas.
> Il contredit utilement le rapport `02c` : il situe le **Pi 5 2 Go à 60-70 €**, ce qui confirme
> que le « Pi 5 8 Go à 204 € » de l'autre rapport était faux.

## Le cadre — c'est réglé, et c'est pas cher
**IKEA RÖDALM 21×30 cm : 6,99 €** (prix relevé sur ikea.com/fr), toujours au catalogue, en noir,
blanc, bouleau, chêne, noyer. Le 21×30 correspond au format A4.

Et ça tombe bien : le **PCB de l'Inky Impression 13,3" fait exactement 297 × 210 mm**, soit l'A4 pile.
L'épaisseur n'est pas documentée chez Pimoroni (estimation 5-8 mm, non confirmée).

Alternatives FR : Leroy Merlin (dès 23,69 €), IKEA SILVERHÖJDEN, Action, Hema — toutes 2 à 3× plus chères.
Le RÖDALM est imbattable.

## Passe-partout
Indispensable pour masquer les bords du PCB et les connecteurs. Fugleramme préconise des marges
de 20 mm et 15 mm. ⚠️ Les passe-partout A4 du commerce sont percés pour du 13×18 cm : il faut du
**sur-mesure** (20-40 €) — Chassis-en-bois.fr, Encadrement-sur-mesure.fr, Leroy Merlin, Rougier & Plé.

## Fixer le Pi derrière
| Méthode | Coût | Avis |
|---|---|---|
| Scotch double-face 3M extra-fort | 2-5 € | Le plus simple, mais permanent |
| **Velcro réutilisable** | ~10 € | **Recommandé** — réversible, démontable |
| Support imprimé en 3D | gratuit si imprimante | Des inserts Inky 7,3" pour RÖDALM existent sur Printables, variantes 13,3" aussi |

🔥 **Point thermique important** : retirer le carton de fond du cadre. Un Pi 5 + BirdNET-Go chauffe
beaucoup, il faut de la circulation d'air derrière l'écran.

## Alimentation : PoE ou USB-C ?
**USB-C classique, sans hésiter.** Le PoE demande un switch PoE (200-400 €) que les box domestiques
n'ont pas ; c'est surdimensionné pour un cadre posé près d'une prise. Le PoE HAT officiel (~20 €,
avec ventilateur intégré) ne se justifie que si le cadre est à plus de 10 m d'une prise ou si un
switch PoE existe déjà.

## Réseau : Ethernet si possible
Plus stable pour le polling continu de BirdNET-Go et les appels API. Le wifi reste acceptable avec
un bon signal. Écart réel modeste — ne pas tirer un câble juste pour ça.

## Longueur de câble pour un micro déporté
| Configuration | Distance max |
|---|---|
| USB 2.0 passif | ~5 m |
| USB 3.0 passif | ~6-10 m |
| USB + répéteur actif | ~30 m |
| XLR symétrique (analogique) | 50-100 m |

Au-delà de 5 m en USB, prévoir un **répéteur actif** (20-50 €, CSL / deleyCON / StarTech sur Amazon.fr).
C'est la vraie raison pour laquelle les installations sérieuses passent en XLR : la distance.

### ⚠️ Deux réserves sur ce rapport
- Il recommande le **Blue Yeti Nano (~90 €)** pour les oiseaux. C'est un micro de studio cardioïde,
  pensé pour la voix en intérieur — douteux pour de la captation extérieure omnidirectionnelle.
  Les rapports `02b` et les sources BirdNET pointent plutôt vers l'EM272 ou le Boya.
- Il affirme que « Fugleramme recommande un micro XLR pro » — **non vérifié** dans la doc du dépôt.

## Sources (relevées par le sous-agent)
- https://www.ikea.com/fr/fr/p/roedalm-cadre-noir-00548882/
- https://shop.pimoroni.com/en-us/products/inky-impression
- https://github.com/arnegiacomo/fugleramme/blob/main/docs/hardware.md
- https://www.printables.com/model/1336359-pimoroni-inky-impression-73-insert-for-ikea-rodalm
- https://www.raspberrypi.com/products/poe-plus-hat/
- https://www.jeffgeerling.com/blog/2024/waveshares-poe-hat-first-raspberry-pi-5/
- https://www.dzombak.com/blog/2025/07/recommendation-microphone-setup-for-birdnet-pi/
- https://shop.pimoroni.com/en-us/pages/worldwide-distributors
