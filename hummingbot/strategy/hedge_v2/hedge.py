import logging
from decimal import Decimal
from typing import Any, List, Optional, Tuple

import pandas as pd

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.derivative.position import Position
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionSide, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.strategy.utils import order_age

hedge_logger = None


class HedgeStrategy(StrategyPyBase):
    """
    This strategy checks the total asset value of market_pairs and,
    hedges if the value is greater than the minimum trade value.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hedge_logger
        if hedge_logger is None:
            hedge_logger = logging.getLogger(__name__)
        return hedge_logger

    def __init__(
        self,
        hedge_market_pair: MarketTradingPairTuple,
        market_pairs: List[MarketTradingPairTuple],
        hedge_ratio: float,
        hedge_leverage: float,
        slippage: float,
        max_order_age: float,
        min_trade_size: float,
        hedge_interval: float,
        status_report_interval: float = 900,
    ):
        super().__init__()
        self._hedge_market_pair = hedge_market_pair
        self._market_pairs = market_pairs
        self._hedge_ratio = hedge_ratio
        self._leverage = hedge_leverage
        self._slippage = slippage
        self._max_order_age = max_order_age
        self._min_trade_size = min_trade_size
        self._hedge_interval = hedge_interval
        self._status_report_interval = status_report_interval
        self._all_markets = [self._hedge_market_pair] + self._market_pairs
        self._last_timestamp = 0
        self._all_markets_ready = False
        derivative_markets = AllConnectorSettings.get_derivative_names()
        self._derivatives_list = [
            market_pair for market_pair in self._all_markets if market_pair.market.name in derivative_markets
        ]
        all_markets = list(set([market_pair.market for market_pair in self._all_markets]))
        self.add_markets(all_markets)

    def is_derivative(self, market_pair: MarketTradingPairTuple) -> bool:
        """
        Check if the market is derivative.
        """
        return market_pair in self._derivatives_list

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Connector", "Symbol", "Type", "Entry", "Amount", "Leverage"]
        data = []
        for market_pair in self._all_markets:
            if not self.is_derivative(market_pair):
                continue
            market, trading_pair = market_pair.market, market_pair.trading_pair
            for position in market_pair.market.account_positions.values():
                if trading_pair != position.trading_pair:
                    continue
                data.append(
                    [
                        market.name,
                        position.trading_pair,
                        position.position_side.name,
                        position.entry_price,
                        position.amount,
                        position.leverage,
                    ]
                )
        return pd.DataFrame(data=data, columns=columns)

    def wallet_df(self) -> pd.DataFrame:
        data = []
        columns = ["Connector", "Asset", "Price", "Amount", "Value"]

        def get_data(market_pair: MarketTradingPairTuple) -> List[Any]:
            market, trading_pair = market_pair.market, market_pair.trading_pair
            return [
                market.name,
                trading_pair,
                market_pair.get_mid_price(),
                self.get_base_amount(market_pair),
                self.get_base_amount(market_pair) * market.get_mid_price(),
            ]
        for market_pair in self._market_pairs:
            data.append(get_data(market_pair))

        total_value = self.get_total_asset_value()
        required_hedge_value = total_value * self._hedge_ratio
        data.append(["Markets", "Total", "", "", f"{total_value:.4g}"])
        data.append(["Required Hedge", "Total", "", "", f"{required_hedge_value:.4g}"])

        market_pair = self._hedge_market_pair
        hedge_value = self.get_base_amount(market_pair) * market_pair.get_mid_price()
        net_hedge = required_hedge_value + hedge_value

        data.append(get_data(market_pair))
        data.append(["Net Hedge", "Total", "", "", f"{net_hedge:.4g}"])
        return pd.DataFrame(data=data, columns=columns)

    def format_status(self) -> str:
        """
        Format the status of the strategy.
        """
        lines = []
        warning_lines = []
        active_orders = self.order_tracker.market_pair_to_active_orders.get(self._hedge_market_pair, [])
        warning_lines.extend(self.network_warning(self._all_markets))
        markets_df = self.market_status_data_frame(self._all_markets)
        lines.extend(["", "  Markets:"] + ["    " + line for line in str(markets_df).split("\n")])
        assets_df = self.wallet_df()
        lines.extend(["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")])
        positions_df = self.active_positions_df()
        if not positions_df.empty:
            lines.extend(["", "  Positions:"] + ["    " + line for line in str(positions_df).split("\n")])
        else:
            lines.extend(["", "  No positions."])
        # See if there're any open orders.
        if active_orders:
            df = LimitOrder.to_pandas(active_orders)
            df_lines = str(df).split("\n")
            lines.extend(["", "  Active orders:"] + ["    " + line for line in df_lines])
        else:
            lines.extend(["", "  No active maker orders."])
        return "\n".join(lines) + "\n" + "\n".join(warning_lines)

    def start(self, clock: Clock, timestamp: float) -> None:
        """
        Start the strategy.
        """
        self._last_timestamp = timestamp
        self.apply_initial_setting()

    def apply_initial_setting(self) -> None:
        """
        Check if the market is derivative, and if so, set the initial setting.
        """
        if not self.is_derivative(self._hedge_market_pair):
            return
        market = self._hedge_market_pair.market
        trading_pair = self._hedge_market_pair.trading_pair
        market.set_leverage(trading_pair, self._leverage)

    def tick(self, timestamp: float) -> None:
        """
        Check if hedge interval has passed and process hedge if so
        """
        if timestamp - self._last_timestamp < self._hedge_interval:
            return
        current_tick = timestamp // self._status_report_interval
        last_tick = self._last_timestamp // self._status_report_interval
        should_report_warnings = current_tick > last_tick
        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self.active_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning("Markets are not ready. No hedge trades are permitted.")
                    return

            if should_report_warnings and not all(
                [market.network_status is NetworkStatus.CONNECTED for market in self.active_markets]
            ):
                self.logger().warning(
                    "WARNING: Some markets are not connected or are down at the moment. "
                    "Hedging may be dangerous when markets or networks are unstable."
                )

            self.hedge()
        finally:
            self._last_timestamp = timestamp

    def get_positions(self, market_pair: MarketTradingPairTuple) -> List[Position]:
        return [
            position
            for position in market_pair.market.account_positions.values()
            if position.trading_pair == market_pair.trading_pair
        ]

    def get_derivative_base_amount(self, market_pair: MarketTradingPairTuple) -> Decimal:
        """
        Get the value of the derivative base asset.
        Returns the amount of the base asset of the derivative market pair.
        """
        positions = self.get_positions(market_pair)
        amount = 0
        for position in positions:
            if position.position_side in [PositionSide.LONG, PositionSide.BOTH]:
                amount += position.amount
            if position.position_side == PositionSide.SHORT:
                amount -= abs(position.amount)
        return amount

    def get_base_amount(self, market_pair: MarketTradingPairTuple) -> Decimal:
        """
        Get the amount of the base asset of the market pair.

        :params market_pair: The market pair to get the amount of the base asset of.
        :returns: The amount of the base asset of the market pair.
        """
        if self.is_derivative(market_pair):
            return self.get_derivative_base_amount(market_pair)
        return market_pair.base_balance

    def get_base_value(self, market_pair: MarketTradingPairTuple) -> Decimal:
        """
        Get the base asset value of a market. e.g BTC/USDT = BTC amount * BTC/USDT price.

        :params market_pair: The market pair to get the base asset value of.
        :returns: The base asset value of the market pair.
        """
        base_amount = self.get_base_amount(market_pair)
        base_price = market_pair.get_mid_price()
        return base_amount * base_price

    def get_total_asset_value(self) -> Decimal:
        """
        Get the total base asset value of all markets.

        :returns: The total base asset value of all market_pairs.
        """
        return sum([self.get_base_value(market_pair) for market_pair in self._market_pairs])

    def get_hedge_asset_value(self) -> Decimal:
        """
        Get the asset value on hedge exchange.
        """
        return self.get_base_value(self._hedge_market_pair)

    def get_hedge_direction_and_value(self) -> Tuple[bool, Decimal]:
        """
        Calculate the value that is required to be hedged.
        Returns the direction to hedge (buy/sell) and the value of hedge
        """
        total_value = self.get_total_asset_value()
        hedge_value = self.get_hedge_asset_value()
        net_value = total_value * self._hedge_ratio + hedge_value
        is_buy = net_value < 0
        value_to_hedge = abs(net_value)
        return is_buy, value_to_hedge

    def calculate_hedge_price_and_amount(self, is_buy: bool, value_to_hedge: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Calculate the price and amount to hedge.
        """
        price = self._hedge_market_pair.get_mid_price()
        amount = value_to_hedge / price
        slippage_ratio = 1 + self._slippage if is_buy else 1 - self._slippage
        price = price * slippage_ratio
        trading_pair = self._hedge_market_pair.trading_pair
        quantized_price = self._hedge_market_pair.market.quantize_order_price(trading_pair, price)
        quantized_amount = self._hedge_market_pair.market.quantize_order_amount(trading_pair, amount)
        return quantized_price, quantized_amount

    def hedge(self) -> None:
        """
        The main process of the strategy.
        """
        if self.check_and_cancel_active_orders():
            return
        is_buy, value_to_hedge = self.get_hedge_direction_and_value()
        price, amount = self.calculate_hedge_price_and_amount(is_buy, value_to_hedge)
        if not self.get_order_candidate(is_buy, amount, price):
            return
        self.place_order(is_buy, amount, price)

    def get_order_candidate(self, is_buy: bool, amount: Decimal, price: Decimal) -> Optional[OrderCandidate]:
        """
        Check if the balance is sufficient to place an order.
        if not, adjust the amount to the balance available.
        returns the order candidate if the order meets the accepted criteria
        else, return None
        """
        market_info = self._hedge_market_pair
        budget_checker = market_info.market.budget_checker
        if self.is_derivative(self._hedge_market_pair):
            order_candidate = PerpetualOrderCandidate(
                trading_pair=market_info.trading_pair,
                is_maker=False,
                order_type=OrderType.LIMIT,
                order_side=TradeType.BUY if is_buy else TradeType.SELL,
                amount=amount,
                price=price,
                leverage=Decimal(self._leverage),
            )
        else:
            order_candidate = OrderCandidate(
                trading_pair=market_info.trading_pair,
                is_maker=False,
                order_type=OrderType.LIMIT,
                order_side=TradeType.BUY if is_buy else TradeType.SELL,
                amount=amount,
                price=price,
            )
        adjusted_candidate_order = budget_checker.adjust_candidate(order_candidate)
        if adjusted_candidate_order.amount * adjusted_candidate_order.price < self._min_trade_size:
            return None
        return adjusted_candidate_order

    def place_order(self, is_buy: bool, amount: float, price: float) -> None:
        """
        Place an order.
        """

        self.logger().info(
            f"Create {'buy' if is_buy else 'sell'} {amount} {self._hedge_market_pair.base_asset} "
            f"at {price} {self._hedge_market_pair.quote_asset}"
        )
        trade = self.buy_with_specific_market if is_buy else self.sell_with_specific_market
        trade(self._hedge_market_pair, amount, order_type=OrderType.LIMIT, price=price)

    def check_and_cancel_active_orders(self) -> bool:
        """
        Check if there are any active orders and,
        cancel them if the order age has exceeded the expected time.
        returns True if there are active orders.
        """
        active_orders = self.order_tracker.market_pair_to_active_orders.get(self._hedge_market_pair, [])
        if not active_orders:
            return False
        for order in active_orders:
            order_time = order_age(order, self._current_timestamp)
            if order_time > self._max_order_age:
                self.logger().debug(f"Cancelling order {order.client_order_id} because it is {order_time} seconds old.")
                self.cancel_order(self._hedge_market_pair, order.client_order_id)
        return True
