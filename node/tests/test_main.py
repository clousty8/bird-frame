"""`__main__._supervised` : une exception inattendue dans une boucle ne doit jamais tuer les
boucles sœurs via le `asyncio.TaskGroup` partagé (api-contract.md §4.1, node/README.md : « une
panne d'une boucle n'affecte jamais les autres »)."""

from __future__ import annotations

import asyncio
import logging

import pytest

from bridge.__main__ import _supervised


@pytest.mark.asyncio
async def test_supervised_logs_critical_and_does_not_propagate(caplog) -> None:
    async def _boom() -> None:
        raise RuntimeError("kaboom")

    with caplog.at_level(logging.CRITICAL, logger="bridge"):
        await _supervised("test-loop", _boom())  # ne doit jamais lever

    assert any(r.levelno == logging.CRITICAL and "test-loop" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_supervised_sibling_task_survives_taskgroup_when_one_loop_crashes() -> None:
    """Reproduit le scénario exact du constat : dans un `TaskGroup` unique, une boucle qui lève
    une exception non gérée ne doit plus annuler les boucles sœurs."""
    survivor_completed = asyncio.Event()

    async def _boom() -> None:
        raise RuntimeError("kaboom")

    async def _survivor() -> None:
        await asyncio.sleep(0.05)
        survivor_completed.set()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(_supervised("crasher", _boom()))
        tg.create_task(_supervised("survivor", _survivor()))

    assert survivor_completed.is_set()


@pytest.mark.asyncio
async def test_supervised_still_propagates_cancellation() -> None:
    """`_supervised` ne doit jamais avaler une annulation (arrêt propre sur SIGINT/SIGTERM) —
    seules les exceptions inattendues sont interceptées."""

    async def _sleep_forever() -> None:
        await asyncio.sleep(100)

    task = asyncio.create_task(_supervised("cancellable", _sleep_forever()))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
