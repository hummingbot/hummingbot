from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.pairs_trading import PairsTrading, PairsTradingConfig
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.strategy_frameworks.generic_strategy.generic_executor import GenericExecutor
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class PairsTradingScript(ScriptStrategyBase):
    exchange = "binance_perpetual"
    trading_pair = "MATIC-USDT"
    trading_pair_2 = "ETH-USDT"
    strategy_name = "pairs_trading"
    leverage = 100
    amount = 50
    max_inventory_asset_1 = 100
    max_inventory_asset_2 = 100
    min_inventory_asset_1 = -100
    min_inventory_asset_2 = -100
    min_delta = -50
    max_delta = 50
    order_refresh_time = 60
    bbands_length = 20
    bbands_std_dev = 2.0
    timeframe = "3m"
    spread_factor = 1.0
    global_take_profit = 0.01
    global_stop_loss = 0.01
    max_candles = bbands_length + 100
    candles_config = [
        CandlesConfig(connector=exchange, trading_pair=trading_pair, interval=timeframe, max_records=max_candles),
        CandlesConfig(connector=exchange, trading_pair=trading_pair_2, interval=timeframe, max_records=max_candles)]

    markets = {exchange: {trading_pair, trading_pair_2}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        config = PairsTradingConfig(
            exchange=self.exchange,
            trading_pair=self.trading_pair,
            trading_pair_2=self.trading_pair_2,
            candles_config=self.candles_config,
            strategy_name=self.strategy_name,
            leverage=self.leverage,
            amount=self.amount,
            max_inventory_asset_1=self.max_inventory_asset_1,
            max_inventory_asset_2=self.max_inventory_asset_2,
            min_inventory_asset_1=self.min_inventory_asset_1,
            min_inventory_asset_2=self.min_inventory_asset_2,
            min_delta=self.min_delta,
            max_delta=self.max_delta,
            order_refresh_time=self.order_refresh_time,
            bbands_length=self.bbands_length,
            bbands_std_dev=self.bbands_std_dev,
            spread_factor=self.spread_factor,
            global_take_profit=self.global_take_profit,
            global_stop_loss=self.global_stop_loss,
            order_levels=[]
        )
        self.executor_handlers = [GenericExecutor(strategy=self, controller=PairsTrading(config=config))]

    def on_tick(self):
        """
        This shows you how you can start meta controllers. You can run more than one at the same time and based on the
        market conditions, you can orchestrate from this script when to stop or start them.
        """

        for executor_handler in self.executor_handlers:
            if executor_handler.status == SmartComponentStatus.NOT_STARTED:
                executor_handler.start()

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        for executor_handler in self.executor_handlers:
            lines.extend(
                [f"Strategy: {executor_handler.controller.config.strategy_name}",
                 executor_handler.to_format_status()])
        return "\n".join(lines)

    def on_stop(self):
        for executor_handler in self.executor_handlers:
            executor_handler.stop()
