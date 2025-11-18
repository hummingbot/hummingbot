import asyncio
import importlib
import sys
from types import ModuleType

import pytest


def _ensure_module(module_path: str, class_name: str):
    try:
        importlib.import_module(module_path)
    except ModuleNotFoundError:  # pragma: no cover - import shim
        module = ModuleType(module_path)

        class Placeholder:  # type: ignore
            pass

        setattr(module, class_name, Placeholder)
        sys.modules[module_path] = module
        parent_path, _, attr = module_path.rpartition(".")
        if parent_path:
            parent_module = importlib.import_module(parent_path)
            setattr(parent_module, attr, module)


_ensure_module("hummingbot.connector.connector_base", "ConnectorBase")
_ensure_module("hummingbot.core.data_type.limit_order", "LimitOrder")

try:
    from hummingbot.strategy.event_driven_strategy_v2_base import EventDrivenStrategyV2Base
except ModuleNotFoundError:  # pragma: no cover - environment missing compiled extensions
    pytest.skip("Skipping event-driven strategy tests because Cython extensions are unavailable.", allow_module_level=True)


class DummySubscription:
    def __init__(self):
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0)
        raise StopAsyncIteration

    async def aclose(self):
        self.closed = True


class DummyStrategy(EventDrivenStrategyV2Base):
    async def _start_loops(self):
        self._spawn_task(self._heartbeat())
        self._track_subscription(DummySubscription())

    async def _heartbeat(self):
        while not self._stopping:
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_event_driven_strategy_start_and_stop_cancel_tasks():
    strategy = DummyStrategy(connectors={})
    await strategy.start_event_driven()
    assert len(strategy._tasks) == 1  # noqa: SLF001 (introspecting for test)
    await strategy.stop_event_driven()
    assert len(strategy._tasks) == 0  # noqa: SLF001


@pytest.mark.asyncio
async def test_event_driven_strategy_closes_subscriptions():
    strategy = DummyStrategy(connectors={})
    await strategy.start_event_driven()
    subscriptions = list(strategy._subscriptions)  # noqa: SLF001
    assert subscriptions
    await strategy.stop_event_driven()
    assert all(getattr(subscription, "closed", True) for subscription in subscriptions)


@pytest.mark.asyncio
async def test_start_event_driven_is_idempotent():
    strategy = DummyStrategy(connectors={})
    await strategy.start_event_driven()
    first_task_count = len(strategy._tasks)  # noqa: SLF001
    await strategy.start_event_driven()
    assert len(strategy._tasks) == first_task_count  # noqa: SLF001
