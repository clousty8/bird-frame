"""Backoff exponentiel générique (architecture.md §3.1, api-contract.md §4.1) :
base 5 s, ×2, plafond 300 s, jitter ±25 %, remis à zéro au premier succès."""

from __future__ import annotations

import random


class Backoff:
    def __init__(self, base: float = 5.0, max_delay: float = 300.0, jitter: float = 0.25) -> None:
        self.base = base
        self.max_delay = max_delay
        self.jitter = jitter
        self._attempt = 0

    def reset(self) -> None:
        self._attempt = 0

    def next_delay(self) -> float:
        """Délai à attendre avant le prochain essai, avec jitter, puis incrémente le compteur."""
        raw_delay = min(self.base * (2**self._attempt), self.max_delay)
        self._attempt += 1
        spread = raw_delay * self.jitter
        return max(0.0, raw_delay + random.uniform(-spread, spread))
