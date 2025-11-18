from typing import Awaitable, Callable, Dict

from services.event_bus import EventBus
from services.models import ConnectorConfig
from services.user_engine import UserEngine


class UserEngineRegistry:
    """
    Lazily instantiates and caches UserEngine instances per user_id.
    """

    def __init__(
        self,
        connector_config_resolver: Callable[[str], Awaitable[Dict[str, ConnectorConfig]]],
        bus: EventBus,
    ):
        self._resolver = connector_config_resolver
        self._bus = bus
        self._engines: Dict[str, UserEngine] = {}

    async def get_or_start(self, user_id: str) -> UserEngine:
        if user_id not in self._engines:
            configs = await self._resolver(user_id)
            engine = UserEngine(user_id=user_id, connector_configs=configs, bus=self._bus)
            await engine.start()
            self._engines[user_id] = engine
        return self._engines[user_id]
