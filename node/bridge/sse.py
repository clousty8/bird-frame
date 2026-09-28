"""Parseur SSE minimal (pas de dépendance dédiée : le format utilisé par BirdNET-Go est un SSE
classique — lignes `event:`/`data:`, séparateur ligne vide, cf. api-contract.md §6.4 pour le
format identique côté serveur bird-frame)."""

from __future__ import annotations

from collections.abc import AsyncIterator


async def iter_sse_events(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str | None, str]]:
    """Regroupe un flux de lignes en évènements `(event, data)`. `event` est `None` si le flux
    n'en précise pas (par défaut `message`, mais on laisse l'appelant décider quoi en faire).
    Les lignes `data:` multiples d'un même évènement sont jointes par `\\n` (spec SSE)."""
    event_name: str | None = None
    data_lines: list[str] = []

    async for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue  # commentaire / keep-alive
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
        # les autres champs (id:, retry:) ne servent pas à ce bridge, ignorés délibérément
