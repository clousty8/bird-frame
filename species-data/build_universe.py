#!/usr/bin/env python3
"""Univers des espèces plausibles en France, d'après le filtre de zone BirdNET du nœud local
(POST /api/v2/range/species/test, 18 villes × 12 mois). Produit species_universe_fr.json et met à jour
france_universe dans base/*.json (sans toucher au reste des fiches de base).
- maxScore : meilleur score toutes villes/mois confondus
- cities : meilleur score par ville
- monthlyScores : meilleur score par mois (toutes villes), 12 valeurs
- months : mois où monthlyScores ≥ MONTH_THRESHOLD (0.05) — « passe le filtre de zone de façon non marginale »
- cityMonthlyScores : score par ville et par mois (18 × 12), pour dire « à Pornic en septembre, c'est courant »
Écrit aussi reference_cities.json (coordonnées des 18 villes de référence).
Usage : python3 species-data/build_universe.py"""
import json, urllib.request, http.cookiejar
from pathlib import Path
HERE = Path(__file__).resolve().parent
BASE = "http://localhost:8080"
MONTH_THRESHOLD = 0.05
CITIES = {"Le Mans": (47.9819, 0.1957), "Pornic": (47.1155, -2.1046), "Rennes": (48.1113, -1.6800), "Poitiers": (46.5802, 0.3404),
          "Paris": (48.8566, 2.3522), "Lille": (50.6292, 3.0573), "Strasbourg": (48.5734, 7.7521), "Lyon": (45.7640, 4.8357),
          "Grenoble": (45.1885, 5.7245), "Marseille": (43.2965, 5.3698), "Toulouse": (43.6047, 1.4442), "Bordeaux": (44.8378, -0.5792),
          "Brest": (48.3904, -4.4861), "Ajaccio": (41.9192, 8.7386), "Clermont-Ferrand": (45.7772, 3.0870), "Chamonix": (45.9237, 6.8694),
          "Perpignan": (42.6887, 2.8948), "Nancy": (48.6921, 6.1844)}
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(BASE + "/").read()
tok = [c.value for c in cj if c.name == "csrf"][0]
uni = {}
for city, (lat, lon) in CITIES.items():
    for m in range(1, 13):
        req = urllib.request.Request(BASE + "/api/v2/range/species/test", data=json.dumps({"latitude": lat, "longitude": lon, "threshold": 0.01, "date": f"2026-{m:02d}-15"}).encode(),
                                     headers={"Content-Type": "application/json", "X-CSRF-Token": tok}, method="POST")
        for s in json.load(op.open(req))["species"]:
            e = uni.setdefault(s["scientificName"], {"scientificName": s["scientificName"], "commonName": s["commonName"], "label": s["label"], "maxScore": 0, "cities": {}, "monthlyScores": [0.0] * 12, "cityMonthlyScores": {}})
            e["maxScore"] = max(e["maxScore"], s["score"]); e["cities"][city] = max(e["cities"].get(city, 0), s["score"])
            e["monthlyScores"][m - 1] = max(e["monthlyScores"][m - 1], s["score"])
            e["cityMonthlyScores"].setdefault(city, [0.0] * 12)[m - 1] = s["score"]
# corrections de noms FR connues (dictionnaire du nœud incomplet)
FIX = {"Acanthis cabaret": "Sizerin cabaret", "Accipiter gentilis": "Autour des palombes"}
out = []
for e in sorted(uni.values(), key=lambda e: -e["maxScore"]):
    e["commonName"] = FIX.get(e["scientificName"], e["commonName"])
    e["monthlyScores"] = [round(x, 4) for x in e["monthlyScores"]]
    e["months"] = [i + 1 for i, x in enumerate(e["monthlyScores"]) if x >= MONTH_THRESHOLD]
    e["maxScore"] = round(e["maxScore"], 4); e["cities"] = {k: round(v, 3) for k, v in e["cities"].items()}
    e["cityMonthlyScores"] = {c: [round(x, 3) for x in (e["cityMonthlyScores"].get(c) or [0.0] * 12)] for c in CITIES}
    out.append(e)
json.dump(out, open(HERE / "species_universe_fr.json", "w"), ensure_ascii=False, indent=1)
json.dump({c: {"lat": lat, "lon": lon} for c, (lat, lon) in CITIES.items()}, open(HERE / "reference_cities.json", "w"), ensure_ascii=False, indent=1)
updated = 0
for e in out:
    p = HERE / "base" / (e["scientificName"].replace(" ", "_") + ".json")
    if not p.exists(): continue
    b = json.loads(p.read_text())
    b["france_universe"] = {"max_score": e["maxScore"], "cities": e["cities"], "monthly_scores": e["monthlyScores"], "months": e["months"], "month_threshold": MONTH_THRESHOLD,
                            "city_monthly_scores": e["cityMonthlyScores"]}
    p.write_text(json.dumps(b, ensure_ascii=False, indent=1)); updated += 1
print(f"espèces : {len(out)} ; bases mises à jour : {updated}")
for n in ("Apus apus", "Erithacus rubecula", "Gavia immer"):
    e = uni[n]; print(n, e["months"], e["monthlyScores"])
