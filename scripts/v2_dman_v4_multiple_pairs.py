from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide, TradeType
from hummingbot.core.event.events import BuyOrderCompletedEvent, SellOrderCompletedEvent
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v4 import DManV4, DManV4Config
from hummingbot.smart_components.executors.position_executor.data_types import TrailingStop, TripleBarrierConf
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.order_level_distributions.distributions import Distributions
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevelBuilder
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DManV4MultiplePairs(ScriptStrategyBase):
    # Account configuration
    exchange = "binance_perpetual"
    trading_pairs = ["OP-USDT"]
    leverage = 20
    initial_auto_rebalance = False
    extra_inventory_pct = 0.1
    asset_to_rebalance = "USDT"
    rebalanced = False

    # Candles configuration
    candles_exchange = "binance_perpetual"
    candles_interval = "3m"
    candles_max_records = 300
    bollinger_band_length = 200
    bollinger_band_std = 3.0

    # Orders configuration
    order_amount = Decimal("6")
    amount_ratio_increase = 1.5
    n_levels = 5
    top_order_start_spread = 0.0002
    start_spread = 0.02
    spread_ratio_increase = 2.0

    top_order_refresh_time = 60
    order_refresh_time = 60 * 60 * 2
    cooldown_time = 30

    # Triple barrier configuration
    stop_loss = Decimal("0.2")
    take_profit = Decimal("0.06")
    time_limit = 60 * 60 * 12

    # Global Trailing Stop configuration
    global_trailing_stop_activation_price_delta = Decimal("0.01")
    global_trailing_stop_trailing_delta = Decimal("0.002")

    # Advanced configurations
    dynamic_spread_factor = False
    dynamic_target_spread = False
    smart_activation = False
    activation_threshold = Decimal("0.001")
    price_band = False
    price_band_long_filter = Decimal("0.8")
    price_band_short_filter = Decimal("0.8")

    # Applying the configuration
    order_level_builder = OrderLevelBuilder(n_levels=n_levels)
    order_levels = order_level_builder.build_order_levels(
        amounts=Distributions.geometric(n_levels=n_levels, start=float(order_amount), ratio=amount_ratio_increase),
        spreads=[Decimal(top_order_start_spread)] + Distributions.geometric(n_levels=n_levels - 1, start=start_spread, ratio=spread_ratio_increase),
        triple_barrier_confs=TripleBarrierConf(
            stop_loss=stop_loss, take_profit=take_profit, time_limit=time_limit,
        ),
        order_refresh_time=[top_order_refresh_time] + [order_refresh_time] * (n_levels - 1),
        cooldown_time=cooldown_time,
    )
    controllers = {}
    markets = {}
    executor_handlers = {}

    for trading_pair in trading_pairs:
        config = DManV4Config(
            exchange=exchange,
            trading_pair=trading_pair,
            order_levels=order_levels,
            candles_config=[
                CandlesConfig(connector=candles_exchange, trading_pair=trading_pair,
                              interval=candles_interval, max_records=candles_max_records),
            ],
            bb_length=bollinger_band_length,
            bb_std=bollinger_band_std,
            price_band=price_band,
            price_band_long_filter=price_band_long_filter,
            price_band_short_filter=price_band_short_filter,
            dynamic_spread_factor=dynamic_spread_factor,
            dynamic_target_spread=dynamic_target_spread,
            smart_activation=smart_activation,
            activation_threshold=activation_threshold,
            leverage=leverage,
            global_trailing_stop_config={
                TradeType.BUY: TrailingStop(activation_price=global_trailing_stop_activation_price_delta,
                                            trailing_delta=global_trailing_stop_trailing_delta),
                TradeType.SELL: TrailingStop(activation_price=global_trailing_stop_activation_price_delta,
                                             trailing_delta=global_trailing_stop_trailing_delta),
            }
        )
        controller = DManV4(config=config)
        markets = controller.update_strategy_markets_dict(markets)
        controllers[trading_pair] = controller

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        all_assets = set([token for trading_pair in self.trading_pairs for token in trading_pair.split("-")])
        balance_required_in_quote = {asset: Decimal("0") for asset in all_assets}
        for trading_pair, controller in self.controllers.items():
            self.executor_handlers[trading_pair] = MarketMakingExecutorHandler(strategy=self, controller=controller)
            balance_required_by_side = controller.get_balance_required_by_order_levels()
            if self.is_perpetual:
                balance_required_in_quote[trading_pair.split("-")[1]] += (balance_required_by_side[TradeType.SELL] + balance_required_by_side[TradeType.BUY]) / self.leverage
            else:
                balance_required_in_quote[trading_pair.split("-")[0]] += balance_required_by_side.get(TradeType.SELL, Decimal("0"))
                balance_required_in_quote[trading_pair.split("-")[1]] += balance_required_by_side.get(TradeType.BUY, Decimal("0"))
        self.balance_required_in_quote = {asset: float(balance) * (1 + self.extra_inventory_pct) for asset, balance in balance_required_in_quote.items()}
        self.rebalance_orders = {}

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.exchange

    def on_stop(self):
        if self.is_perpetual:
            self.close_open_positions()
        for executor_handler in self.executor_handlers.values():
            executor_handler.stop()

    def close_open_positions(self):
        # we are going to close all the open positions when the bot stops
        for connector_name, connector in self.connectors.items():
            for trading_pair, position in connector.account_positions.items():
                if trading_pair in self.markets[connector_name]:
                    if position.position_side == PositionSide.LONG:
                        self.sell(connector_name=connector_name,
                                  trading_pair=position.trading_pair,
                                  amount=abs(position.amount),
                                  order_type=OrderType.MARKET,
                                  price=connector.get_mid_price(position.trading_pair),
                                  position_action=PositionAction.CLOSE)
                    elif position.position_side == PositionSide.SHORT:
                        self.buy(connector_name=connector_name,
                                 trading_pair=position.trading_pair,
                                 amount=abs(position.amount),
                                 order_type=OrderType.MARKET,
                                 price=connector.get_mid_price(position.trading_pair),
                                 position_action=PositionAction.CLOSE)

    def on_tick(self):
        """
        This shows you how you can start meta controllers. You can run more than one at the same time and based on the
        market conditions, you can orchestrate from this script when to stop or start them.
        """
        if not self.rebalanced and len(self.rebalance_orders) == 0:
            self.rebalance()
        else:
            for executor_handler in self.executor_handlers.values():
                if executor_handler.status == SmartComponentStatus.NOT_STARTED:
                    executor_handler.start()

    def rebalance(self):
        current_balances = self.get_balance_df()
        for asset, balance_needed in self.balance_required_in_quote.items():
            if asset != self.asset_to_rebalance:
                trading_pair = f"{asset}-{self.asset_to_rebalance}"
                balance_diff_in_base = Decimal(balance_needed) / self.connectors[self.exchange].get_mid_price(trading_pair) - Decimal(current_balances[current_balances["Asset"] == asset]["Total Balance"].item())
                if balance_diff_in_base > self.connectors[self.exchange].trading_rules[trading_pair].min_order_size:
                    if balance_diff_in_base > 0:
                        self.rebalance_orders[trading_pair] = self.buy(connector_name=self.exchange, trading_pair=trading_pair, amount=balance_diff_in_base, order_type=OrderType.MARKET)
                    elif balance_diff_in_base < 0:
                        self.rebalance_orders[trading_pair] = self.sell(connector_name=self.exchange, trading_pair=trading_pair, amount=abs(balance_diff_in_base), order_type=OrderType.MARKET)
        if len(self.rebalance_orders) == 0:
            self.rebalanced = True

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        for trading_pair, executor_handler in self.executor_handlers.items():
            lines.extend(
                [f"Strategy: {executor_handler.controller.config.strategy_name} | Trading Pair: {trading_pair}",
                 executor_handler.to_format_status()])
        return "\n".join(lines)

    def did_complete_buy_order(self, order_completed_event: BuyOrderCompletedEvent):
        if not self.rebalanced:
            self.check_rebalance_orders(order_completed_event)

    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        if not self.rebalanced:
            self.check_rebalance_orders(order_completed_event)

    def check_rebalance_orders(self, order_completed_event):
        if order_completed_event.order_id in self.rebalance_orders.values():
            trading_pair = f"{order_completed_event.base_asset}-{order_completed_event.quote_asset}"
            del self.rebalance_orders[trading_pair]
        if len(self.rebalance_orders) == 0:
            self.rebalanced = True
