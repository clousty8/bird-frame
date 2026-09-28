#!/usr/bin/env python3
"""Pré-remplissage déterministe (sans IA) des fiches espèces.

Pour chaque espèce de species_universe_fr.json :
  - taxonomie via le nœud BirdNET-Go local (GET /api/v2/species/taxonomy)
  - résumé, URL et photo HD via Wikipédia REST (fr puis en)
  - licence / auteur de la photo via l'API Commons (imageinfo/extmetadata)
  - texte intégral (plain text) des articles fr et en dans cache/ (pour les agents rédacteurs)
Sortie : base/<Nom_scientifique>.json (une fiche pré-remplie), cache/<Nom>.fr.txt, cache/<Nom>.en.txt

Usage : python3 build_base.py [--limit N] [--only "Erithacus rubecula"] [--force]
"""
import argparse, html, json, re, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
UNIVERSE = HERE / "species_universe_fr.json"
BASE = HERE / "base"
CACHE = HERE / "cache"
NODE = "http://localhost:8080"
UA = "bird-frame/0.1 (projet personnel; contact: armand.mounsi@gmail.com) httpx"
MAX_TXT = 24000

client = httpx.Client(headers={"User-Agent": UA, "Accept-Encoding": "gzip"}, timeout=30, follow_redirects=True)


def get_json(url, **params):
    for attempt in range(4):
        try:
            r = client.get(url, params=params or None)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1)); continue
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            if attempt == 3:
                print(f"  !! {url} : {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def wiki_summary(lang, title):
    return get_json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ', '_'))}")


def wiki_fulltext(lang, title):
    d = get_json(f"https://{lang}.wikipedia.org/w/api.php", action="query", prop="extracts", explaintext=1,
                 redirects=1, titles=title, format="json", formatversion=2)
    if not d:
        return None
    pages = d.get("query", {}).get("pages", [])
    if not pages or "extract" not in pages[0]:
        return None
    return pages[0]["extract"][:MAX_TXT]


def commons_info(image_url):
    if not image_url:
        return None
    fname = urllib.parse.unquote(image_url.split("?", 1)[0].rsplit("/", 1)[-1])
    fname = re.sub(r"^\d+px-", "", fname)
    d = get_json("https://commons.wikimedia.org/w/api.php", action="query", titles=f"File:{fname}",
                 prop="imageinfo", iiprop="extmetadata|url", iiurlwidth=1600, format="json")
    if not d:
        return None
    pages = list(d.get("query", {}).get("pages", {}).values())
    if not pages or "imageinfo" not in pages[0]:
        return None
    ii = pages[0]["imageinfo"][0]
    m = ii.get("extmetadata", {})
    g = lambda k: strip_tags(m.get(k, {}).get("value", "")) or None
    return {
        "file": fname,
        "url_1600": ii.get("thumburl"),
        "url_original": ii.get("url"),
        "license": g("LicenseShortName"),
        "license_url": g("LicenseUrl"),
        "author": g("Artist"),
        "credit": g("Credit"),
        "description_url": ii.get("descriptionurl"),
    }


def node_taxonomy(sci):
    d = get_json(f"{NODE}/api/v2/species/taxonomy", scientific_name=sci, locale="fr")
    return (d or {}).get("taxonomy")


def build_one(entry, force=False):
    sci = entry["scientificName"]
    key = sci.replace(" ", "_")
    out = BASE / f"{key}.json"
    if out.exists() and not force:
        return f"= {sci} (déjà fait)"
    fr = wiki_summary("fr", sci)
    en = wiki_summary("en", sci)
    # Wikipédia FR : le nom scientifique redirige normalement vers l'article du nom vernaculaire
    fr_title = fr.get("title") if fr else None
    en_title = en.get("title") if en else None
    fr_txt = wiki_fulltext("fr", fr_title) if fr_title else None
    en_txt = wiki_fulltext("en", en_title) if en_title else None
    if fr_txt:
        (CACHE / f"{key}.fr.txt").write_text(fr_txt)
    if en_txt:
        (CACHE / f"{key}.en.txt").write_text(en_txt)
    img = (fr or {}).get("originalimage") or (en or {}).get("originalimage")
    photo = commons_info(img["source"]) if img else None
    tax = node_taxonomy(sci)
    base = {
        "scientific_name": sci,
        "common_name_fr": entry["commonName"],
        "birdnet_label": entry["label"],
        "taxonomy": tax,
        "wikipedia": {
            "fr": {"title": fr_title, "url": (fr or {}).get("content_urls", {}).get("desktop", {}).get("page"),
                    "description": (fr or {}).get("description"), "extract": (fr or {}).get("extract"),
                    "fulltext_chars": len(fr_txt) if fr_txt else 0},
            "en": {"title": en_title, "url": (en or {}).get("content_urls", {}).get("desktop", {}).get("page"),
                    "description": (en or {}).get("description"), "extract": (en or {}).get("extract"),
                    "fulltext_chars": len(en_txt) if en_txt else 0},
        },
        "photo": ({"source": "wikipedia", "url_original": img["source"].split("?", 1)[0], "width": img.get("width"),
                    "height": img.get("height"), **(photo or {})} if img else None),
        "france_universe": {"max_score": round(entry["maxScore"], 4), "cities": {k: round(v, 3) for k, v in entry["cities"].items()},
                             "months": entry["months"]},
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out.write_text(json.dumps(base, ensure_ascii=False, indent=1))
    flags = [] if fr else ["sans-wiki-fr"]
    if not img: flags.append("sans-photo")
    if not tax: flags.append("sans-taxonomie")
    return f"+ {sci} → {fr_title or en_title} {' '.join(flags)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    BASE.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
    uni = json.load(open(UNIVERSE))
    if a.only:
        uni = [e for e in uni if e["scientificName"] == a.only]
    if a.limit:
        uni = uni[: a.limit]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for line in ex.map(lambda e: build_one(e, a.force), uni):
            print(line, flush=True)


if __name__ == "__main__":
    main()
