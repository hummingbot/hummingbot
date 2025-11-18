import asyncio
from typing import Any, Awaitable, Dict, List, Optional

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class EventDrivenStrategyV2Base(ScriptStrategyBase):
    """
    Base class for strategies that manage their own event-driven loops instead of relying on the global Clock tick.
    Subclasses implement `_start_loops()` to spawn whatever background tasks they require (market data listeners,
    decision loops, etc.). All tasks and subscriptions registered via the helper methods are cancelled/closed when
    `stop_event_driven()` is invoked.
    """

    is_event_driven: bool = True

    def __init__(self, connectors: Dict[str, Any], config: Optional[Any] = None):
        super().__init__(connectors, config)
        self._tasks: List[asyncio.Task] = []
        self._subscriptions: List[Any] = []
        self._start_lock = asyncio.Lock()
        self._stopping: bool = True

    def on_tick(self):
        """
        Event-driven strategies do not use the Clock tick. This override intentionally does nothing to avoid
        double-running logic when TradingCore mistakenly keeps the strategy on the Clock iterator.
        """
        return

    async def start_event_driven(self):
        """
        Entry point invoked by TradingCore (or UserEngine) when the strategy should begin execution.
        Ensures `_start_loops()` only runs once even if multiple start calls race.
        """
        async with self._start_lock:
            if not self._stopping:
                return
            self._stopping = False
            await self._start_loops()

    async def stop_event_driven(self):
        """
        Cancels all background tasks spawned via `_spawn_task()` and closes any tracked subscriptions.
        """
        self._stopping = True

        subscriptions = list(self._subscriptions)
        self._subscriptions.clear()
        for subscription in subscriptions:
            close_callable = getattr(subscription, "aclose", None) or getattr(subscription, "close", None)
            if close_callable is None:
                continue
            try:
                result = close_callable()
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger().warning("Error while closing subscription.", exc_info=True)

        tasks = [task for task in self._tasks if not task.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger().error("Unhandled exception in event-driven task.", exc_info=True)
        self._tasks.clear()

    async def _start_loops(self):
        """
        Subclasses override this method to subscribe to market data/event buses and spawn their internal loops.
        """
        raise NotImplementedError

    def _spawn_task(self, coro: Awaitable[Any]) -> asyncio.Task:
        """
        Helper that wraps a coroutine in `safe_ensure_future` so the strategy can track and cancel it later.
        """
        task = safe_ensure_future(coro)
        self._tasks.append(task)
        return task

    def _track_subscription(self, subscription: Any) -> Any:
        """
        Tracks an async iterator / subscription object that exposes `aclose()` or `close()` so it can be shut down when
        the strategy stops. Returns the same subscription to allow fluent usage.
        """
        self._subscriptions.append(subscription)
        return subscription
