# Raspberry Pi et accessoires — rapport PARTIEL (prix NON FIABLES)

> 🔴 **AVERTISSEMENT : les prix de ce rapport sont en grande partie FAUX.**
> Rapport issu d'un sous-agent orphelin. Plusieurs montants sont aberrants d'un facteur 2 à 5 :
> - « Pi 5 8 Go à 204 € chez Kubii » → **invraisemblable**, le tarif habituel tourne autour de 90-110 €
> - « Samsung PRO Endurance 128 Go à 81,52 € » → **invraisemblable**, c'est une carte à ~20-25 €
> - « Transcend MTE220S 256 Go à 168,68 € » → **invraisemblable**, un NVMe 256 Go coûte ~25-35 €
> - « Pi 4 4 Go à 120 € / Pi 4 8 Go à 117 € » → incohérent (le 8 Go moins cher que le 4 Go)
>
> **Ne budgétiser sur aucun de ces chiffres.** Les totaux annoncés (351 € / 533 €) sont donc à jeter.
> En revanche les **conclusions techniques** ci-dessous sont utiles et cohérentes avec les sources citées.

## Quel modèle de Pi

| Modèle | Verdict pour BirdNET-Go | Détail |
|---|---|---|
| **Pi 5 (8 Go)** | ✅ Recommandé | Recommandé par la doc officielle birdnet-go. Inférence nettement plus rapide que le Pi 4, UI web fluide, peut faire tourner plusieurs modèles (BirdNET v2.4, Google Perch v2, BattyBirdNET). 2 Go = minimum théorique, 4 Go = confortable, 8 Go = marge. |
| **Pi 4** | ⚠️ Suffisant, moins bon | Fait tourner BirdNET-Go mais UI plus lente, throttling possible avec Deep Detection, difficultés en multi-stream RTSP. |
| **Pi Zero 2 W** | ❌ Pas pour l'inférence | Plantages occasionnels rapportés en 24/7 (discussions Nachtzuster/BirdNET-Pi #133, #258). **Bon uniquement pour piloter l'écran**, comme dans Inky Bird Frame, si la détection tourne ailleurs. |

## Refroidisseur actif Pi 5 — oui, quasi obligatoire
BirdNET-Go = inférence ML continue 24/7 = charge soutenue. Sans refroidisseur, le Pi 5 throttle vers 80-85 °C.
Le cooler officiel maintient le SoC 20-25 °C sous le seuil à 22 °C ambiant. Le refroidissement passif seul
ne tient pas au-delà de 200-300 s de charge continue.
Source : guide officiel raspberrypi.com « Heating and cooling Raspberry Pi 5 ».

## Alimentation — le piège classique
Le Pi 5 veut du **27 W USB-C PD**. Une alim sous-dimensionnée provoque :
sous-tension (<4,64 V), throttling, icône éclair, déconnexions USB, reboots aléatoires, et surtout
**corruption de la carte SD** par écritures incomplètes.
Consommation : ~2,7 W au repos, jusqu'à ~11 W sous inférence, plus les accessoires. Avec un NVMe, le 27 W devient obligatoire.
(Pi 4 : 15 W suffit. Zero 2 W : 5 W.)

## Carte microSD — prendre de la High Endurance
L'écriture continue (base SQLite BirdNET + logs) tue les cartes grand public.
Problèmes documentés : mcguirepr89/BirdNET-Pi issue #1131 (partition pleine à 100 %), discussions #859 et #716.
Viser **High Endurance / monitoring** (A1-A2, V30, U3), 64 Go minimum, 128 Go confortable.
Modèles cités : SanDisk High Endurance, Samsung PRO Endurance. ⚠️ prix du rapport faux, vérifier.

## Alternative NVMe
M.2 HAT+ officiel Raspberry Pi (SC1166) annoncé à 12 $ — jusqu'à ~500 Mo/s.
Alternatives : Waveshare PCIe to M.2 HAT+ (~28-32 €, avec ventilo), Geekworm série M300.
Un SSD évite complètement le problème d'usure SD. 256 Go largement suffisant.

## Boîtier et câble GPIO
Boîtiers passifs cités : Geekworm P573 alu, GeeekPi heat sink, iUniker. Actifs : Miuzei PWM.
Câble nappe GPIO 40 broches mâle/femelle pour déporter l'écran : 10 cm (serré) ou **20 cm (recommandé)**.
Au-delà de 20 cm, pas de standard — il faudrait du FFC custom. Dispo Audiophonics.fr, Amazon.fr.

## Sources citées (non revérifiées)
- https://github.com/tphakala/birdnet-go/wiki/hardware
- https://beaktech.org/blog/birdnet-monitor-hardware
- https://hannahilea.com/blog/birdnet-setup/
- https://www.raspberrypi.com/news/heating-and-cooling-raspberry-pi-5/
- https://github.com/mcguirepr89/BirdNET-Pi/issues/1131
- https://github.com/Nachtzuster/BirdNET-Pi/discussions/133
- https://forums.raspberrypi.com/viewtopic.php?t=371450
- https://www.raspberrypi.com/news/m-2-hat-on-sale-now-for-12/
