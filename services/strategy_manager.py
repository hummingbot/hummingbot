from typing import Protocol

from services.models import StrategyConfig, StrategyJobSpec
from services.user_engine_registry import UserEngineRegistry


class StrategyStore(Protocol):
    async def save_strategy_config(self, config: StrategyConfig) -> None:
        ...

    async def update_strategy_config(self, config: StrategyConfig) -> None:
        ...

    async def get_strategy_config(self, strategy_id: str) -> StrategyConfig:
        ...


class StrategyManager:
    def __init__(self, registry: UserEngineRegistry, store: StrategyStore):
        self._registry = registry
        self._store = store

    async def create_and_start(self, job: StrategyJobSpec) -> StrategyConfig:
        config = StrategyConfig.from_job(job)
        await self._store.save_strategy_config(config)
        engine = await self._registry.get_or_start(job.user_id)
        strategy_id = await engine.start_ema_atr_strategy(config)
        config.id = strategy_id
        config.status = "running"
        await self._store.update_strategy_config(config)
        return config

    async def stop(self, strategy_id: str) -> StrategyConfig:
        config = await self._store.get_strategy_config(strategy_id)
        engine = await self._registry.get_or_start(config.user_id)
        await engine.stop_strategy(strategy_id)
        config.status = "stopped"
        await self._store.update_strategy_config(config)
        return config
