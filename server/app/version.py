"""Version du serveur bird-frame — constante unique côté serveur.

Ne pas modifier à la main : `scripts/bump.py` met à jour d'un coup cette constante, `VERSION`
à la racine, les deux `pyproject.toml`, les deux `uv.lock`, `web/package.json` (+ lock) et
`node/bridge/__init__.py`. `scripts/bump.py --check` (CI) échoue si l'un d'eux diverge.
"""

__version__ = "0.2.0"
