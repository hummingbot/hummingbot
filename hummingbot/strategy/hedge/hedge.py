import logging
from decimal import Decimal
from typing import Any, Dict, List, Tuple, Union

import pandas as pd

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.derivative.position import Position
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.hedge.hedge_config_map_pydantic import HedgeConfigMap
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.strategy.utils import order_age

hedge_logger = None


class HedgeStrategy(StrategyPyBase):
    """
    This strategy contains 2 mode of hedging.
    1. Hedge by amount
    2. Hedge by value

    1. Hedge by amount
    The strategy will hedge by amount by calculating the amount to hedge by each asset.
    The amount of asset to hedge is calculated by the following formula:
    for each asset in the hedge market pair,
        amount_to_hedge = sum of asset amount with the same base asset * hedge_ratio + hedge asset amount
    The amount of asset to hedge must be greater than the minimum trade size to be traded.

    2. Hedge by value
    The strategy will hedge by value by calculating the amount of asset to hedge.
    The amount of asset to hedge is calculated by the following formula:
    amount_to_hedge = sum of asset value of all market pairs * hedge_ratio + hedge asset value
    The amount of asset to hedge must be greater than the minimum trade size to be traded.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hedge_logger
        if hedge_logger is None:
            hedge_logger = logging.getLogger(__name__)
        return hedge_logger

    def __init__(
        self,
        config_map: HedgeConfigMap,
        hedge_market_pairs: List[MarketTradingPairTuple],
        market_pairs: List[MarketTradingPairTuple],
        offsets: Dict[MarketTradingPairTuple, Decimal],
        status_report_interval: float = 900,
        max_order_age: float = 5,
        enable_auto_set_position_mode: bool = True,
    ):
        """
        Initializes the hedge strategy.
        :param hedge_market_pair: Market pair to hedge.
        :param market_pairs: Market pairs to trade.
        :param hedge_ratio: Ratio of total asset value to hedge.
        :param hedge_leverage: Leverage to use for hedging.
        :param slippage: Slippage to use for hedging.
        :param max_order_age: Maximum age of an order before it is cancelled.
        :param min_trade_size: Minimum trade size.
        :param hedge_interval: Interval to check for hedging.
        :param value_mode: True if the strategy is in value mode, False otherwise.
        :param hedge_position_mode: Position mode (ONEWAY or HEDGE) to use for hedging.
        :param status_report_interval: Interval to report status.
        """
        super().__init__()
        self._hedge_market_pairs = hedge_market_pairs
        self._market_pairs = market_pairs
        self._hedge_ratio = config_map.hedge_ratio
        self._leverage = config_map.hedge_leverage
        self._position_mode = PositionMode.ONEWAY if config_map.hedge_position_mode == "ONEWAY" else PositionMode.HEDGE
        self._slippage = config_map.slippage
        self._min_trade_size = config_map.min_trade_size
        self._hedge_interval = config_map.hedge_interval
        self._value_mode = config_map.value_mode
        self._offsets = offsets
        self._status_report_interval = status_report_interval
        self._all_markets = self._hedge_market_pairs + self._market_pairs
        self._last_timestamp = 0
        self._all_markets_ready = False
        self._max_order_age = max_order_age
        self._status_messages = []
        self._last_report_timestamp = {}
        self._enable_auto_set_position_mode = enable_auto_set_position_mode
        if config_map.value_mode:
            self.hedge = self.hedge_by_value
            self._hedge_market_pair = hedge_market_pairs[0]
            self.logger().info(f"Hedge market pair: {self._hedge_market_pair}")
        else:
            self.hedge = self.hedge_by_amount
            self._market_pair_by_asset = self.get_market_pair_by_asset()
            self.logger().info(f"Market pair by asset: {self._market_pair_by_asset}")

        derivative_markets = AllConnectorSettings.get_derivative_names()
        self._derivatives_list = [
            market_pair for market_pair in self._all_markets if market_pair.market.name in derivative_markets
        ]
        self.get_order_candidates = (
            self.get_perpetual_order_candidates
            if self.is_derivative(self._hedge_market_pairs[0])
            else self.get_spot_order_candidates
        )

        all_markets = list(set([market_pair.market for market_pair in self._all_markets]))
        self.add_markets(all_markets)

    def get_market_pair_by_asset(self) -> Dict[MarketTradingPairTuple, List[MarketTradingPairTuple]]:
        """
        sort market pair belonging to the same market as hedge market together
        :return: market pair belonging to the same market as hedge market together
        """
        self.logger().info(f"Market pairs: {self._market_pairs}")
        return {
            hedge_pair: [
                market_pair for market_pair in self._market_pairs
                if market_pair.trading_pair.split("-")[0] == hedge_pair.trading_pair.split("-")[0]
            ]
            for hedge_pair in self._hedge_market_pairs
        }

    def is_derivative(self, market_pair: MarketTradingPairTuple) -> bool:
        """
        Check if the market is derivative.
        :param market_pair: Market pair to check.
        :return: True if the market is derivative, False otherwise.
        """
        return market_pair in self._derivatives_list

    def active_positions_df(self) -> pd.DataFrame:
        """
        Get the active positions of all markets.
        :return: The active positions of all markets.
        """
        columns = ["Connector", "Symbol", "Type", "Entry", "Amount", "Leverage"]
        data = []
        for market_pair in self._all_markets:
            if not self.is_derivative(market_pair):
                continue
            for position in self.get_positions(market_pair):
                if not position:
                    continue
                data.append(
                    [
                        market_pair.market.name,
                        position.trading_pair,
                        position.position_side.name,
                        position.entry_price,
                        position.amount,
                        position.leverage,
                    ]
                )
        return pd.DataFrame(data=data, columns=columns)

    def wallet_df(self) -> pd.DataFrame:
        """
        Processes the data required for wallet dataframe.
        :return: wallet dataframe
        """
        data = []
        columns = ["Connector", "Asset", "Price", "Amount", "Value"]

        def get_data(market_pair: MarketTradingPairTuple) -> List[Any]:
            market, trading_pair = market_pair.market, market_pair.trading_pair
            return [
                market.name,
                trading_pair,
                market_pair.get_mid_price(),
                f"{self.get_base_amount(market_pair):.6g}",
                f"{self.get_base_amount(market_pair) * market_pair.get_mid_price():.6g}",
            ]

        for market_pair in self._all_markets:
            data.append(get_data(market_pair))
        return pd.DataFrame(data=data, columns=columns)

    @property
    def active_orders(self) -> List[Tuple[Any, LimitOrder]]:
        """
        Get the active orders of all markets.
        :return: The active orders of all hedge markets.

        """
        return self.order_tracker.active_limit_orders

    def format_status(self) -> str:
        """
        Format the status of the strategy.
        """
        def get_wallet_status_str() -> List[str]:
            wallet_df = self.wallet_balance_data_frame(self._all_markets)
            return ["", "  Wallet:"] + ["    " + line for line in str(wallet_df).split("\n")]

        def get_asset_status_str() -> List[str]:
            assets_df = self.wallet_df()
            return ["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")]

        def get_position_status_str() -> List[str]:
            positions_df = self.active_positions_df()
            if not positions_df.empty:
                return ["", "  Positions:"] + ["    " + line for line in str(positions_df).split("\n")]
            return ["", "  No positions."]

        def get_order_status_str() -> List[str]:
            if self.active_orders:
                orders = [order[1] for order in self.active_orders]
                df = LimitOrder.to_pandas(orders)
                df_lines = str(df).split("\n")
                return ["", "  Active orders:"] + ["    " + line for line in df_lines]
            return ["", "  No active maker orders."]

        def get_value_mode_status_str(value_mode: bool) -> List[str]:
            if not value_mode:
                return []

            lines = []
            total_value = sum(self.get_base_value(market_pair) for market_pair in self._market_pairs)
            hedge_value = self.get_base_value(self._hedge_market_pair)
            is_buy, value_to_hedge = self.get_hedge_direction_and_value()
            price, amount = self.calculate_hedge_price_and_amount(is_buy, value_to_hedge)
            lines.extend(["", f"   Mode: Value, Total value: {total_value:.6g}, Hedge value: {hedge_value:.6g}"])
            if amount > 0:
                lines.extend(
                    [
                        "",
                        f"   Next Hedge direction: {'buy' if is_buy else 'sell'}, Hedge price: {price:.6g}, Hedge amount: {amount:.6g}",
                    ]
                )
            return lines

        def get_amount_mode_status_str(value_mode: bool) -> List[str]:
            if value_mode:
                return []
            lines = ["", "   Mode: Amount"]
            data = []
            for hedge_market, market_list in self._market_pair_by_asset.items():
                hedge_market_name = hedge_market.market.name
                asset = hedge_market.trading_pair.split("-")[0]
                market_names = ", ".join([market.market.name for market in market_list])
                total_amount = sum(self.get_base_amount(market_pair) for market_pair in market_list)
                hedge_amount = self.get_base_amount(hedge_market)
                net_amount = total_amount * self._hedge_ratio + hedge_amount
                data.append([
                    hedge_market_name,
                    asset,
                    total_amount,
                    hedge_amount,
                    net_amount,
                    market_names,
                ])

            df = pd.DataFrame(data=data, columns=["Hedge Market", "Asset", "Total Amount", "Hedge Amount", "Net Amount", "Markets"])
            lines.extend(["    " + line for line in str(df).split("\n")])
            return lines

        def get_last_checked_seconds_str() -> List[str]:
            if self._last_timestamp < 1e9:
                return ["  Last checked: Not started."]
            return [f"  Last checked {self.current_timestamp - self._last_timestamp} seconds ago."]

        def get_status_messages() -> List[str]:
            if self._status_messages:
                return ["", "  Status Messages:"] + ["    " + line for line in self._status_messages]
            return []

        lines = (
            get_wallet_status_str()
            + get_asset_status_str()
            + get_position_status_str()
            + get_order_status_str()
            + get_value_mode_status_str(self._value_mode)
            + get_amount_mode_status_str(self._value_mode)
            + get_last_checked_seconds_str()
            + get_status_messages()
            + [""]
            + self.network_warning(self._all_markets)
        )
        return "\n".join(lines)

    def start(self, clock: Clock, timestamp: float) -> None:
        """
        Start the strategy.
        :param clock: Clock to use.
        :param timestamp: Current time.
        """
        self._last_timestamp = timestamp
        self.apply_initial_setting()

    def apply_initial_setting(self) -> None:
        """
        Check if the market is derivative, and if so, set the initial setting.
        """
        if not self.is_derivative(self._hedge_market_pairs[0]):
            return
        if not self._enable_auto_set_position_mode:
            logging.info("Auto set position mode is disabled.")
            return
        position_mode = "ONEWAY" if self._position_mode == PositionMode.ONEWAY else "HEDGE"
        msg = (
            f"Please ensure that the position mode on {self._hedge_market_pairs[0].market.name} "
            f"is set to {position_mode}. "
            f"The bot will try to automatically set position mode to {position_mode}. "
            f"You may ignore the message if the position mode is already set to {position_mode}.")
        self.notify_hb_app(msg)
        self.logger().warning(msg)
        for market_pair in self._hedge_market_pairs:
            market = market_pair.market
            trading_pair = market_pair.trading_pair
            market.set_leverage(trading_pair, self._leverage)
            market.set_position_mode(self._position_mode)

    def interval_log(self, key: str, message: str) -> None:
        """
        Log message at interval.
        :param key: Key to identify the last recorded timestamp.
        :param message: Message to log.
        """
        if self._last_timestamp - self._last_report_timestamp.get(key, 0) > self._status_report_interval:
            self.logger().info(message)
            self._last_report_timestamp[key] = self._last_timestamp

    def tick(self, timestamp: float) -> None:
        """
        Check if hedge interval has passed and process hedge if so
        :param timestamp: clock timestamp
        """
        if self.check_and_cancel_active_orders():
            self.interval_log("hedge", "Active orders present. Skipping hedge check until active orders expires.")
            return
        if timestamp - self._last_timestamp < self._hedge_interval:
            return
        self._all_markets_ready = all([market.ready for market in self.active_markets])
        if not self._all_markets_ready:
            # Markets not ready yet. Don't do anything.
            for market in self.active_markets:
                if not market.ready:
                    self.logger().warning(f"Market {market.name} is not ready.")
            self.logger().warning("Markets are not ready. No hedge trades are permitted.")
            return

        if not all([market.network_status is NetworkStatus.CONNECTED for market in self.active_markets]):
            self.logger().warning(
                "WARNING: Some markets are not connected or are down at the moment. "
                "Hedging may be dangerous when markets or networks are unstable. "
                "Retrying after %ss.",
                self._hedge_interval,
            )
            return
        self.interval_log("hedge", "Checking hedge conditions...")
        self._status_messages = []
        self.hedge()
        self._last_timestamp = timestamp

    def get_positions(self, market_pair: MarketTradingPairTuple, position_side: PositionSide = None) -> List[Position]:
        """
        Get the active positions of a market.
        :param market_pair: Market pair to get the positions of.
        :return: The active positions of the market.
        """
        trading_pair = market_pair.trading_pair
        positions: List[Position] = [
            position
            for position in market_pair.market.account_positions.values()
            if not isinstance(position, PositionMode) and position.trading_pair == trading_pair
        ]
        if position_side:
            return [position for position in positions if position.position_side == position_side]
        return positions

    def get_derivative_base_amount(self, market_pair: MarketTradingPairTuple) -> Decimal:
        """
        Get the value of the derivative base asset.
        :param market_pair: The market pair to get the value of the derivative base asset.
        :return: The value of the derivative base asset.
        """
        positions = self.get_positions(market_pair)
        amount = 0

        for position in positions:
            if position.position_side in [PositionSide.LONG, PositionSide.BOTH]:
                amount += position.amount
            if position.position_side == PositionSide.SHORT:
                amount -= abs(position.amount)
        return amount + self._offsets[market_pair]

    def get_base_amount(self, market_pair: MarketTradingPairTuple) -> Decimal:
        """
        Get the amount of the base asset of the market pair.

        :params market_pair: The market pair to get the amount of the base asset of.
        :returns: The amount of the base asset of the market pair.
        """
        if self.is_derivative(market_pair):
            self.logger().debug(f"Getting derivative base amount for {market_pair.trading_pair}")
            return self.get_derivative_base_amount(market_pair)
        return market_pair.base_balance + self._offsets[market_pair]

    def get_base_value(self, market_pair: MarketTradingPairTuple) -> Decimal:
        """
        Get the base asset value of a market. e.g BTC/USDT = BTC amount * BTC/USDT price.

        :params market_pair: The market pair to get the base asset value of.
        :returns: The base asset value of the market pair.
        """
        base_amount = self.get_base_amount(market_pair)
        base_price = market_pair.get_mid_price()
        return base_amount * base_price

    def get_hedge_direction_and_value(self) -> Tuple[bool, Decimal]:
        """
        Calculate the value that is required to be hedged.
        :returns: A tuple of the hedge direction (buy/sell) and the value to be hedged.
        """
        total_value = sum(self.get_base_value(market_pair) for market_pair in self._market_pairs)
        hedge_value = self.get_base_value(self._hedge_market_pair)
        net_value = total_value * self._hedge_ratio + hedge_value
        is_buy = net_value < 0
        value_to_hedge = abs(net_value)
        return is_buy, value_to_hedge

    def get_slippage_ratio(self, is_buy: bool) -> Decimal:
        """
        Get the slippage ratio for a buy or sell.
        :param is_buy: True if buy, False if sell.
        :returns: The ratio to multiply the price by to account for slippage.
        """
        return 1 + self._slippage if is_buy else 1 - self._slippage

    def calculate_hedge_price_and_amount(self, is_buy: bool, value_to_hedge: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Calculate the price and amount to hedge.
        :params is_buy: The direction of the hedge.
        :params value_to_hedge: The value to hedge.
        :returns: The price and amount to hedge.
        """
        price = self._hedge_market_pair.get_mid_price()
        amount = value_to_hedge / price
        price = price * self.get_slippage_ratio(is_buy)
        trading_pair = self._hedge_market_pair.trading_pair
        quantized_price = self._hedge_market_pair.market.quantize_order_price(trading_pair, price)
        quantized_amount = self._hedge_market_pair.market.quantize_order_amount(trading_pair, amount)
        return quantized_price, quantized_amount

    def hedge_by_value(self) -> None:
        """
        The main process of the strategy for value mode = True.
        """
        is_buy, value_to_hedge = self.get_hedge_direction_and_value()
        price, amount = self.calculate_hedge_price_and_amount(is_buy, value_to_hedge)
        if amount == Decimal("0"):
            self.logger().debug("No hedge required.")
            self._status_messages.append("No hedge required.")
            return
        self.logger().info(
            f"Hedging by value. Hedge direction: {'buy' if is_buy else 'sell'}. "
            f"Hedge price: {price}. Hedge amount: {amount}."
        )
        order_candidates = self.get_order_candidates(self._hedge_market_pair, is_buy, amount, price)
        if not order_candidates:
            self.logger().info("No order candidates.")
            self._status_messages.append("No order candidates.")
            return
        self.place_orders(self._hedge_market_pair, order_candidates)

    def get_hedge_direction_and_amount_by_asset(
        self, hedge_pair: MarketTradingPairTuple, market_list: List[MarketTradingPairTuple]
    ) -> Tuple[bool, Decimal]:
        """
        Calculate the amount that is required to be hedged.
        :params hedge_pair: The market pair to hedge.
        :params market_list: The list of markets to get the amount of the base asset of.
        :returns: The direction to hedge (buy/sell) and the amount of the base asset of the market pair.
        """
        total_amount = 0
        for market_pair in market_list:
            amount = self.get_base_amount(market_pair)
            total_amount += self.get_base_amount(market_pair)
            self.logger().debug("Market pair: %s amount: %s, total_amount: %s", market_pair, amount, total_amount)

        hedge_amount = self.get_base_amount(hedge_pair)
        net_amount = total_amount * self._hedge_ratio + hedge_amount
        is_buy = net_amount < 0
        amount_to_hedge = abs(net_amount)
        self.logger().debug("Hedge direction: %s, amount to hedge: %s net amount: %s", is_buy, amount_to_hedge, net_amount)
        return is_buy, amount_to_hedge

    def hedge_by_amount(self) -> None:
        """
        The main process of the strategy for value mode = False.
        """
        for hedge_market, market_list in self._market_pair_by_asset.items():
            is_buy, amount_to_hedge = self.get_hedge_direction_and_amount_by_asset(hedge_market, market_list)
            asset = hedge_market.trading_pair.split("-")[0]
            self.logger().debug("Hedge by amount for %s: %s", asset, amount_to_hedge)
            self._status_messages.append(f"Hedge by amount for {asset}: {amount_to_hedge}")
            if amount_to_hedge == 0:
                self.logger().debug("No hedge required for %s.", asset)
                self._status_messages.append(f"No hedge required for {asset}.")
                continue
            price = hedge_market.get_mid_price() * self.get_slippage_ratio(is_buy)
            self.logger().info(
                "Hedge by amount. Mid price: %s Hedge direction: %s. Hedge price: %s. Hedge amount: %s",
                hedge_market.get_mid_price(), is_buy, price, amount_to_hedge
            )
            order_candidates = self.get_order_candidates(hedge_market, is_buy, amount_to_hedge, price)
            if not order_candidates:
                self.logger().info("Difference in hedge_amount found but no order candidates for %s is available. “This is either due to insufficient balance to perform hedge or min trade size not reached or minimum exchange trade size not met", asset)
                self._status_messages.append(f"No order candidates for {asset}.")
                continue
            self.place_orders(hedge_market, order_candidates)

    def get_perpetual_order_candidates(
        self, market_pair: MarketTradingPairTuple, is_buy: bool, amount: Decimal, price: Decimal
    ) -> List[PerpetualOrderCandidate]:
        """
        Check if the balance is sufficient to place an order.
        if not, adjust the amount to the balance available.
        returns the order candidate if the order meets the accepted criteria
        else, return None
        """
        self.logger().info("Checking perpetual order candidates for %s %s %s %s", market_pair, "buy" if is_buy else "sell", amount, price)

        def get_closing_order_candidate(is_buy: bool, amount: Decimal, price: Decimal) -> Union[PerpetualOrderCandidate, None]:
            opp_position_side = PositionSide.SHORT if is_buy else PositionSide.LONG
            opp_position_list = self.get_positions(market_pair, opp_position_side)
            # opp_position_list should only have 1 position
            for opp_position in opp_position_list:
                close_amount = min(amount, abs(opp_position.amount))
                order_candidate = PerpetualOrderCandidate(
                    trading_pair=market_pair.trading_pair,
                    is_maker=False,
                    order_side=TradeType.BUY if is_buy else TradeType.SELL,
                    amount=close_amount,
                    price=price,
                    order_type=OrderType.LIMIT,
                    leverage=Decimal(self._leverage),
                    position_close=True,
                )
                adjusted_candidate_order = budget_checker.adjust_candidate(order_candidate, all_or_none=False)
                return adjusted_candidate_order
            return None

        budget_checker = market_pair.market.budget_checker
        if amount * price < self._min_trade_size:
            self.logger().info("trade value (%s) is less than min trade size. (%s)", amount * price, self._min_trade_size)
            return []
        order_candidates = []
        if self._position_mode == PositionMode.HEDGE:
            order_candidate = get_closing_order_candidate(is_buy, amount, price)
            if order_candidate:
                order_candidates.append(order_candidate)
                amount -= order_candidate.amount
        order_candidate = PerpetualOrderCandidate(
            trading_pair=market_pair.trading_pair,
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_buy else TradeType.SELL,
            amount=amount,
            price=price,
            leverage=Decimal(self._leverage),
        )
        self.logger().info("order candidate: %s", order_candidate)
        adjusted_candidate_order = budget_checker.adjust_candidate(order_candidate, all_or_none=False)
        self.logger().info("adjusted order candidate: %s", adjusted_candidate_order)
        if adjusted_candidate_order.amount > 0:
            order_candidates.append(adjusted_candidate_order)
        return order_candidates

    def get_spot_order_candidates(
        self, market_pair: MarketTradingPairTuple, is_buy: bool, amount: Decimal, price: Decimal
    ) -> List[OrderCandidate]:
        """
        Check if the balance is sufficient to place an order.
        if not, adjust the amount to the balance available.
        returns the order candidate if the order meets the accepted criteria
        else, return None
        """
        budget_checker = market_pair.market.budget_checker
        if amount * price < self._min_trade_size:
            self.logger().info("trade value (%s) is less than min trade size. (%s)", amount * price, self._min_trade_size)
            return []
        order_candidate = OrderCandidate(
            trading_pair=market_pair.trading_pair,
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_buy else TradeType.SELL,
            amount=amount,
            price=price,
        )
        self.logger().info("order candidate: %s", order_candidate)
        adjusted_candidate_order = budget_checker.adjust_candidate(order_candidate, all_or_none=False)
        self.logger().info("adjusted order candidate: %s", adjusted_candidate_order)
        if adjusted_candidate_order.amount > 0:
            return [adjusted_candidate_order]
        return []

    def place_orders(
        self, market_pair: MarketTradingPairTuple, orders: Union[List[OrderCandidate], List[PerpetualOrderCandidate]]
    ) -> None:
        """
        Place an order refering the order candidates.
        :params market_pair: The market pair to place the order.
        :params orders: The list of orders to place.
        """
        self.logger().info("Placing %s orders", len(orders))
        for order in orders:
            self.logger().info(f"Create {order.order_side} {order.amount} {order.trading_pair} at {order.price}")
            is_buy = order.order_side == TradeType.BUY
            amount = order.amount
            price = order.price
            position_action = PositionAction.OPEN
            if isinstance(order, PerpetualOrderCandidate) and order.position_close:
                position_action = PositionAction.CLOSE
            trade = self.buy_with_specific_market if is_buy else self.sell_with_specific_market
            trade(market_pair, amount, order_type=OrderType.LIMIT, price=price, position_action=position_action)

    def check_and_cancel_active_orders(self) -> bool:
        """
        Check if there are any active orders and cancel them
        :return: True if there are active orders, False otherwise.
        """
        if not self.active_orders:
            return False
        for market_pair, order in self.active_orders:
            if order_age(order, self.current_timestamp) < self._max_order_age:
                continue
            self.logger().info(
                f"Cancel {'buy' if order.is_buy else 'sell'} {order.quantity} {order.trading_pair} at {order.price}"
            )
            market_pair.cancel(order.trading_pair, order.client_order_id)
        return True
