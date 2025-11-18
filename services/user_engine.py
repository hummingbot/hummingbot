import asyncio
import uuid
from typing import TYPE_CHECKING, Dict, Optional

from scripts.jarvis.ema_atr_event_driven import EmaAtrConfig, EmaAtrStrategy
from services.event_bus import EventBus
from services.models import ConnectorConfig, StrategyConfig

if TYPE_CHECKING:  # pragma: no cover
    from hummingbot.client.config.client_config_map import ClientConfigMap
    from hummingbot.core.trading_core import TradingCore


class UserEngine:
    """
    Embeds a Hummingbot TradingCore (connectors + clock) for a specific user and manages event-driven strategies that
    operate on that user's connectors.
    """

    def __init__(
        self,
        user_id: str,
        connector_configs: Dict[str, ConnectorConfig],
        bus: EventBus,
        trading_core: Optional["TradingCore"] = None,
        client_config: Optional["ClientConfigMap"] = None,
    ):
        self.user_id = user_id
        self._connector_configs = connector_configs
        self._bus = bus
        self._client_config = client_config or self._build_client_config()
        self._trading_core = trading_core or self._build_trading_core(self._client_config)
        self._strategies: Dict[str, EmaAtrStrategy] = {}
        self._start_lock = asyncio.Lock()
        self._started = False

    async def start(self):
        async with self._start_lock:
            if self._started:
                return
            await self._initialize_connectors()
            await self._ensure_clock()
            self._started = True

    async def stop(self):
        strategies = list(self._strategies.values())
        for strategy in strategies:
            await strategy.stop_event_driven()
        self._strategies.clear()
        if self._trading_core.clock is not None:
            await self._trading_core.stop_clock()
        self._started = False

    async def start_ema_atr_strategy(self, config: StrategyConfig) -> str:
        await self.start()
        strategy_id = config.id or uuid.uuid4().hex
        ema_config = EmaAtrConfig(
            connector_name=config.connector_name,
            trading_pair=config.trading_pair,
            timeframe=config.timeframe,
            fast_ema_period=config.fast_ema,
            slow_ema_period=config.slow_ema,
            atr_period=config.atr_period,
            atr_threshold=config.atr_threshold,
            risk_pct_per_trade=config.risk_pct_per_trade,
        )
        EmaAtrStrategy.init_markets(ema_config)
        strategy = EmaAtrStrategy(connectors=self._trading_core.connectors, config=ema_config)
        strategy.bind_market_data_bus(self._bus)
        await strategy.start_event_driven()
        self._strategies[strategy_id] = strategy
        return strategy_id

    async def stop_strategy(self, strategy_id: str):
        strategy = self._strategies.pop(strategy_id, None)
        if strategy:
            await strategy.stop_event_driven()

    @property
    def connector_manager(self):
        return self._trading_core.connector_manager

    async def _initialize_connectors(self):
        for cfg in self._connector_configs.values():
            await self._trading_core.create_connector(
                connector_name=cfg.name,
                trading_pairs=cfg.trading_pairs,
                trading_required=cfg.trading_required,
                api_keys=cfg.api_keys,
            )

    async def _ensure_clock(self):
        if self._trading_core.clock is None:
            await self._trading_core.start_clock()

    def _build_client_config(self):
        from hummingbot.client.config.client_config_map import ClientConfigMap

        return ClientConfigMap()

    def _build_trading_core(self, client_config):
        from hummingbot.core.trading_core import TradingCore

        return TradingCore(client_config)
