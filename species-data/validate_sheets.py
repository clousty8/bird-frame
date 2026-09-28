#!/usr/bin/env python3
"""Validation déterministe des fiches species-data/sheets/*.json contre le contrat (docs/api-contract.md §8.3).
Usage : uv run --project server python species-data/validate_sheets.py [--json]"""
import json, re, sys, urllib.parse
from pathlib import Path
import jsonschema

HERE = Path(__file__).resolve().parent
contract = (HERE.parent / "docs/api-contract.md").read_text()
m = re.search(r'"\$id": "bird-frame/species-sheet-v1".*?\n```', contract, re.S)
schema = json.loads("{" + m.group(0)[: m.group(0).rfind("}") + 1].split("{", 0)[0] if False else "{\n  \"$schema\": \"https://json-schema.org/draft/2020-12/schema\",\n  " + m.group(0)[: m.group(0).rfind("}") + 1])
validator = jsonschema.Draft202012Validator(schema)

def norm(u):
    return urllib.parse.unquote(u or "").replace("http://", "https://").rstrip("/")

bad, warn = {}, {}
for f in sorted((HERE / "sheets").glob("*.json")):
    key = f.stem
    problems, warnings = [], []
    try:
        d = json.loads(f.read_text())
    except Exception as e:
        bad[key] = [f"JSON invalide : {e}"]; continue
    for err in validator.iter_errors(d):
        problems.append(f"{'/'.join(map(str, err.path)) or '(racine)'} : {err.message[:120]}")
    if d.get("scientific_name") != key.replace("_", " "):
        problems.append(f"scientific_name ≠ nom de fichier ({d.get('scientific_name')})")
    n = len((d.get("summary_fr") or "").split())
    if n < 80 or n > 260: problems.append(f"summary_fr : {n} mots (hors 80-260)")
    elif n < 120 or n > 200: warnings.append(f"summary_fr : {n} mots (cible 120-200)")
    basef = HERE / "base" / f.name
    if basef.exists():
        b = json.loads(basef.read_text())
        wfr = b["wikipedia"]["fr"].get("url") or b["wikipedia"]["en"].get("url")
        if wfr and norm(wfr) not in [norm(s) for s in d.get("sources", [])]:
            problems.append(f"sources sans l'URL Wikipédia de la base ({wfr})")
        ms = (b.get("france_universe") or {}).get("max_score", 0)
        rn = (d.get("rarity_note") or "").lower()
        if ms >= 0.5 and re.search(r"\b(rare|exceptionnel|accidentel)", rn): warnings.append(f"rarity_note dit rare alors que max_score={ms}")
    for fld in ("summary_fr", "habitat", "diet", "seasonality_fr", "song_fr", "rarity_note"):
        v = d.get(fld) or ""
        if "\n" in v or "**" in v or "#" in v: problems.append(f"{fld} : retour à la ligne ou Markdown")
    for lk in d.get("lookalikes", []):
        if isinstance(lk, dict) and lk.get("scientific_name") == d.get("scientific_name"): problems.append("lookalikes : auto-référence")
    if problems: bad[key] = problems
    if warnings: warn[key] = warnings

if "--json" in sys.argv:
    print(json.dumps({"invalid": bad, "warnings": warn}, ensure_ascii=False, indent=1))
else:
    print(f"fiches : {len(list((HERE/'sheets').glob('*.json')))} ; invalides : {len(bad)} ; avertissements : {len(warn)}")
    for k, v in bad.items(): print(f"✗ {k}: " + " | ".join(v))
    for k, v in list(warn.items())[:60]: print(f"~ {k}: " + " | ".join(v))
