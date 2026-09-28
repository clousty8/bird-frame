# Écrans e-ink — rapport PARTIEL (le plus solide des quatre)

> ⚠️ Rapport issu d'un sous-agent orphelin. Les **specs et la compatibilité logicielle** sont cohérentes
> et constituent la partie la plus exploitable. Les **prix restent à revérifier** sur les sites.
> Erreur repérée : le rapport cite en source `github.com/vibragiel/fugleramme` — le bon dépôt est
> **github.com/arnegiacomo/fugleramme**.

## Le point dur : l'écran est en rupture

| Écran | Résolution | Couleurs | Rafraîchissement | Prix / dispo constatés |
|---|---|---|---|---|
| **Pimoroni Inky Impression 13,3"** (PIM774, Spectra 6) | 1600×1200, 150 ppp | 6 | ~12 s cœur, 20-35 s réel | BerryBase.de **299,90 € — indisponible** ; The Pi Hut **229,50 £ — rupture** ; pas trouvé chez Kubii |
| **Pimoroni Inky Impression 7,3"** (PIM773, Spectra 6) | 800×480 | 6 | ~28 s cœur | 89 $ chez Adafruit ; dispo UE à confirmer |
| **Pimoroni Inky Impression 5,7"** (ACeP) | 600×448 | 7 | — | ~66 £ — **discontinué**, Pimoroni recentre sur 4,0" / 7,3" / 13,3" |
| **Waveshare 13,3" Spectra 6 (E6)** | 1600×1200 | 6 | 19 s | ~250-280 € (eBay.de ~280 €) |
| **Waveshare 7,3" ACeP** | 800×480 | 7 | — | prix UE non trouvé |

**Le 13,3" est en rupture chez les revendeurs européens testés.** C'est le principal obstacle à court terme.

## Compatibilité logicielle — la chose la plus importante du rapport

Pimoroni (`inky`, auto-détection EEPROM, GPIO direct) et Waveshare (`waveshare-epd`, SPI bas niveau,
sélection manuelle du driver) sont **incompatibles**. Changer de fabricant = réécrire la couche d'affichage,
pas juste changer une résolution.

| Écran | Fugleramme | Inky Bird Frame | Travail |
|---|---|---|---|
| Pimoroni 13,3" | ✅ natif | ✅ référence | aucun |
| Pimoroni 7,3" | ⚠️ à replanifier | ✅ **natif** (redimensionne la canonique 1600×1200) | layout Fugleramme seulement |
| Pimoroni 5,7" | ⚠️ | ⚠️ | layout + palette ACeP vs Spectra 6 |
| Waveshare (toutes) | ❌ | ❌ | **portage driver complet** |

## Recommandation du rapport
1. **Pimoroni 7,3"** = meilleur compromis : natif sur Inky Bird Frame, portage léger sur Fugleramme, moins cher, plus dispo.
2. Pimoroni 13,3" si on veut la résolution max — mais il faut attendre le réapprovisionnement.
3. Waveshare à éviter malgré un prix voisin : le portage logiciel coûte plus cher que l'écart de prix.
4. 5,7" à oublier (discontinué).

## Brexit — frais à prévoir si achat UK
TVA 20 % + droits de douane. Le rapport mentionne une taxe forfaitaire de 3 € par article
pour les colis ≤ 150 € à partir du 1er juillet 2026, et la fin du régime 42 simplifié au 1er janvier 2026.
⚠️ À revérifier, mais acheter chez BerryBase (DE) plutôt qu'au Royaume-Uni évite la question.

## Sources citées (non revérifiées)
- https://thepihut.com/products/inky-impression-13-3-2025-edition
- https://www.berrybase.de/en/pimoroni-inky-impression-13-3-epaper-display-fuer-raspberry-pi-spectra-6-1600x1200-6-farben-gpio
- https://www.pishop.us/product/inky-impression-7-3-2025-edition/
- https://www.adafruit.com/product/6471
- https://www.waveshare.com/13.3inch-e-paper-hat-plus-e.htm
- https://github.com/pimoroni/inky
- https://www.electromaker.io/blog/article/pimoroni-inky-impression-a-practical-guide-to-color-e-ink-displays-for-raspberry-pi
