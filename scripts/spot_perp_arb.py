from decimal import Decimal
from typing import Dict, List

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import (
    OrderType,
    PositionAction,
    PositionMode,
    TradeType,
)
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


# TODO: handle corner cases -- spot price and perp price never cross again after position is opened
class SpotPerpArb(ScriptStrategyBase):
    """
    PRECHECK:
    1. enough base and quote balance in spot, enough quote balance in perp
    2. better to empty your position in perp
    """

    spot_connector = "kucoin"
    perp_connector = "kucoin_perpetual"
    trading_pair = "LINA-USDT"

    base_order_amount = Decimal("100")
    buy_spot_short_perp_profit_margin_bps = 30
    sell_spot_long_perp_profit_margin_bps = 30
    # buffer to account for slippage when placing limit taker orders
    slippage_buffer_bps = 5
    
    leverage = 2
    markets = {spot_connector: {trading_pair}, perp_connector: {trading_pair}}

    is_perp_in_long = False
    is_perp_in_short = False

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.set_leverage()

    # TODO: resolve error when setting leverage
    def set_leverage(self) -> None:
        perp_connector = self.connectors[self.perp_connector]
        perp_connector.set_position_mode(PositionMode.HEDGE)
        perp_connector.set_leverage(
            trading_pair=self.trading_pair, leverage=self.leverage
        )
        self.logger().info(
            f"Completed setting leverage to {self.leverage}x for {self.perp_connector} on {self.trading_pair}"
        )

    def on_tick(self) -> None:
        if (
            self.should_buy_spot_short_perp()
            and self.can_buy_spot_short_perp()
            and not self.is_perp_in_short
        ):
            self.buy_spot_short_perp()
            self.is_perp_in_short = True
        elif (
            self.should_sell_spot_long_perp()
            and self.can_sell_spot_long_perp()
            and not self.is_perp_in_long
        ):
            self.sell_spot_long_perp()
            self.is_perp_in_long = True

        if self.is_perp_complete_round_trip():
            self.reset_perp_flag()

    def is_perp_complete_round_trip(self) -> bool:
        """
        reset flag when a round trip of trade is completed:
        e.g. (long perp, sell spot) => (short perp, buy spot)
        e.g. (short perp, buy spot) => (long perp, sell spot)
        """
        return self.is_perp_in_long and self.is_perp_in_short

    def reset_perp_flag(self) -> None:
        self.is_perp_in_long = False
        self.is_perp_in_short = False
        self.logger().info(
            "A round trip is completed, reset is_perp_in_long and is_perp_in_short to False"
        )
        return

    def should_buy_spot_short_perp(self) -> bool:
        spot_buy_price = self.limit_taker_price(self.spot_connector, is_buy=True)
        perp_sell_price = self.limit_taker_price(self.perp_connector, is_buy=False)
        ret_pbs = float((perp_sell_price - spot_buy_price) / spot_buy_price) * 10000
        is_profitable = ret_pbs >= self.buy_spot_short_perp_profit_margin_bps
        return is_profitable

    # TODO: check if balance is deducted when it has position
    def can_buy_spot_short_perp(self) -> bool:
        spot_balance = self.get_balance(self.spot_connector, is_base=False)
        buy_price_with_slippage = self.limit_taker_price_with_slippage(
            self.spot_connector, is_buy=True
        )
        spot_required = buy_price_with_slippage * self.base_order_amount
        is_spot_enough = Decimal(spot_balance) >= spot_required
        if not is_spot_enough:
            _, quote = split_hb_trading_pair(self.trading_pair)
            float_spot_required = float(spot_required)
            self.logger().info(
                f"Insufficient balance in {self.spot_connector}: {spot_balance} {quote}. "
                f"Required {float_spot_required:.4f} {quote}."
            )
        perp_balance = self.get_balance(self.perp_connector, is_base=False)
        # short order WITHOUT any splippage takes more capital
        short_price = self.limit_taker_price(self.perp_connector, is_buy=False)
        perp_required = short_price * self.base_order_amount
        is_perp_enough = Decimal(perp_balance) >= perp_required
        if not is_perp_enough:
            _, quote = split_hb_trading_pair(self.trading_pair)
            float_perp_required = float(perp_required)
            self.logger().info(
                f"Insufficient balance in {self.perp_connector}: {perp_balance:.4f} {quote}. "
                f"Required {float_perp_required:.4f} {quote}."
            )
        return is_spot_enough and is_perp_enough

    # TODO: handle partial fill (e.g. if spot is partial fill with 50%, then perp should be partial fill with 50%)
    # TODO: explore borrowing/ lending from spot
    def buy_spot_short_perp(self) -> None:
        spot_buy_price_with_slippage = self.limit_taker_price_with_slippage(
            self.spot_connector, is_buy=True
        )
        perp_short_price_with_slippage = self.limit_taker_price_with_slippage(
            self.perp_connector, is_buy=False
        )
        self.buy(
            self.spot_connector,
            self.trading_pair,
            amount=self.base_order_amount,
            order_type=OrderType.LIMIT,
            price=spot_buy_price_with_slippage,
        )
        self.logger().info(
            f"Submitted buy order in {self.spot_connector} for {self.trading_pair} "
            f"at price {spot_buy_price_with_slippage:.06f}@{self.base_order_amount}"
        )
        position_action = (
            PositionAction.CLOSE if self.is_perp_in_long else PositionAction.OPEN
        )
        self.sell(
            self.perp_connector,
            self.trading_pair,
            amount=self.base_order_amount,
            order_type=OrderType.LIMIT,
            price=perp_short_price_with_slippage,
            position_action=position_action,
        )
        self.logger().info(
            f"Submitted short order in {self.perp_connector} for {self.trading_pair} "
            f"at price {perp_short_price_with_slippage:.06f}@{self.base_order_amount}"
        )
        return

    def should_sell_spot_long_perp(self) -> bool:
        spot_sell_price = self.limit_taker_price(self.spot_connector, is_buy=False)
        perp_buy_price = self.limit_taker_price(self.perp_connector, is_buy=True)
        ret_pbs = float((spot_sell_price - perp_buy_price) / perp_buy_price) * 10000
        is_profitable = ret_pbs >= self.sell_spot_long_perp_profit_margin_bps
        return is_profitable

    def can_sell_spot_long_perp(self) -> bool:
        spot_balance = self.get_balance(self.spot_connector, is_base=True)
        spot_required = self.base_order_amount
        is_spot_enough = Decimal(spot_balance) >= spot_required
        if not is_spot_enough:
            base, _ = split_hb_trading_pair(self.trading_pair)
            float_spot_required = float(spot_required)
            self.logger().info(
                f"Insufficient balance in {self.spot_connector}: {spot_balance} {base}. "
                f"Required {float_spot_required:.4f} {base}."
            )
        perp_balance = self.get_balance(self.perp_connector, is_base=False)
        # long order WITH any splippage takes more capital
        long_price_with_slippage = self.limit_taker_price(
            self.perp_connector, is_buy=True
        )
        perp_required = long_price_with_slippage * self.base_order_amount
        is_perp_enough = Decimal(perp_balance) >= perp_required
        if not is_perp_enough:
            _, quote = split_hb_trading_pair(self.trading_pair)
            float_perp_required = float(perp_required)
            self.logger().info(
                f"Insufficient balance in {self.perp_connector}: {perp_balance:.4f} {quote}. "
                f"Required {float_perp_required:.4f} {quote}."
            )
        return is_spot_enough and is_perp_enough

    def sell_spot_long_perp(self) -> None:
        perp_long_price_with_slippage = self.limit_taker_price_with_slippage(
            self.perp_connector, is_buy=True
        )
        spot_sell_price_with_slippage = self.limit_taker_price_with_slippage(
            self.spot_connector, is_buy=False
        )
        position_action = (
            PositionAction.CLOSE if self.is_perp_in_short else PositionAction.OPEN
        )
        self.buy(
            self.perp_connector,
            self.trading_pair,
            amount=self.base_order_amount,
            order_type=OrderType.LIMIT,
            price=perp_long_price_with_slippage,
            position_action=position_action,
        )
        self.logger().info(
            f"Submitted long order in {self.perp_connector} for {self.trading_pair} "
            f"at price {perp_long_price_with_slippage:.06f}@{self.base_order_amount}"
        )
        self.sell(
            self.spot_connector,
            self.trading_pair,
            amount=self.base_order_amount,
            order_type=OrderType.LIMIT,
            price=spot_sell_price_with_slippage,
        )
        self.logger().info(
            f"Submitted sell order in {self.spot_connector} for {self.trading_pair} "
            f"at price {spot_sell_price_with_slippage:.06f}@{self.base_order_amount}"
        )

        return

    def limit_taker_price_with_slippage(
        self, connector_name: str, is_buy: bool
    ) -> Decimal:
        price = self.limit_taker_price(connector_name, is_buy)
        slippage = (
            Decimal(1 + self.slippage_buffer_bps / 10000)
            if is_buy
            else Decimal(1 - self.slippage_buffer_bps / 10000)
        )
        return price * slippage

    def limit_taker_price(self, connector_name: str, is_buy: bool) -> Decimal:
        limit_taker_price_result = self.connectors[connector_name].get_price_for_volume(
            self.trading_pair, is_buy, self.base_order_amount
        )
        return limit_taker_price_result.result_price

    def get_balance(self, connector_name: str, is_base: bool) -> float:
        if connector_name == self.perp_connector:
            assert not is_base, "Perpetual connector does not have base asset"
        base, quote = split_hb_trading_pair(self.trading_pair)
        balance = self.connectors[connector_name].get_available_balance(
            base if is_base else quote
        )
        return float(balance)

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines: List[str] = []
        self._append_buy_spot_short_perp_status(lines)
        lines.extend(["", ""])
        self._append_sell_spot_long_perp_status(lines)
        lines.extend(["", ""])
        self._append_balances_status(lines)
        lines.extend(["", ""])
        return "\n".join(lines)

    def _append_buy_spot_short_perp_status(self, lines: List[str]) -> None:
        spot_buy_price = self.limit_taker_price(self.spot_connector, is_buy=True)
        perp_short_price = self.limit_taker_price(self.perp_connector, is_buy=False)
        ret_percent = float((perp_short_price - spot_buy_price) / spot_buy_price) * 100
        lines.append("Buy Spot Short Perp Opportunity:")
        lines.append(f"Buy Spot: {spot_buy_price}")
        lines.append(f"Short Perp: {perp_short_price}")
        lines.append(f"Return: {ret_percent:.2f}%")
        lines.append(f"Is In Position: {self.is_perp_in_short}")
        return

    def _append_sell_spot_long_perp_status(self, lines: List[str]) -> None:
        perp_long_price = self.limit_taker_price(self.perp_connector, is_buy=True)
        spot_sell_price = self.limit_taker_price(self.spot_connector, is_buy=False)
        ret_percent = float((spot_sell_price - perp_long_price) / perp_long_price) * 100
        lines.append("Long Perp Sell Spot Opportunity:")
        lines.append(f"Long Perp: {perp_long_price}")
        lines.append(f"Sell Spot: {spot_sell_price}")
        lines.append(f"Return: {ret_percent:.2f}%")
        lines.append(f"Is In Position: {self.is_perp_in_long}")
        return

    def _append_balances_status(self, lines: List[str]) -> None:
        base, quote = split_hb_trading_pair(self.trading_pair)
        spot_base_balance = self.get_balance(self.spot_connector, is_base=True)
        spot_quote_balance = self.get_balance(self.spot_connector, is_base=False)
        perp_quote_balance = self.get_balance(self.perp_connector, is_base=False)
        lines.append("Balances:")
        lines.append(f"Spot Base Balance: {spot_base_balance:.04f} {base}")
        lines.append(f"Spot Quote Balance: {spot_quote_balance:.04f} {quote}")
        lines.append(f"Perp Balance: {perp_quote_balance:04f} USDT")
        return
