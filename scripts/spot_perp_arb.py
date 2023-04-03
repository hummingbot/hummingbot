from decimal import Decimal
from typing import Dict, List

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SpotPerpArb(ScriptStrategyBase):
    spot_connector = "kucoin"
    perp_connector = "kucoin_perpetual"
    trading_pair = "SXP-USDT"

    base_order_amount = Decimal("50")
    spread_bps = 30  # minimal profit margin in order to execute trade
    slippage_buffer_bps = (
        5  # buffer to account for slippage when placing limit taker orders
    )
    leverage = 2
    markets = {spot_connector: {trading_pair}, perp_connector: {trading_pair}}

    is_perp_in_long = False
    is_perp_in_short = False

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.set_leverage()

    def set_leverage(self):
        perp_connector = self.connectors[self.perp_connector]
        perp_connector.set_position_mode(PositionMode.HEDGE)
        perp_connector.set_leverage(
            trading_pair=self.trading_pair, leverage=self.leverage
        )
        self.logger().info(
            f"Completed setting leverage to {self.leverage}x for {self.perp_connector} on {self.trading_pair}"
        )

    def on_tick(self):
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

        if self.is_perp_round_trip():
            self.reset_perp_flag()

    def is_perp_round_trip(self):
        """
        reset flag when a round trip of trade is completed:
        e.g. (long perp, sell spot) => (short perp, buy spot)
        e.g. (short perp, buy spot) => (long perp, sell spot)
        """
        return self.is_perp_in_long and self.is_perp_in_short

    def reset_perp_flag(self):
        self.is_perp_in_long = False
        self.is_perp_in_short = False

    def should_buy_spot_short_perp(self) -> bool:
        spot_buy_price = self.limit_taker_price(self.spot_connector, is_buy=True)
        perp_sell_price = self.limit_taker_price(self.perp_connector, is_buy=False)
        ret_pbs = float((perp_sell_price - spot_buy_price) / spot_buy_price) * 10000
        is_profitable = ret_pbs >= self.spread_bps
        if is_profitable:
            self.logger().info(
                f"Profitable spread: {ret_pbs:.2f} bps for buy spot sell perp!!"
            )
        return is_profitable

    def can_buy_spot_short_perp(self) -> bool:
        # check balance
        return True

    # TODO: handle partial fill (e.g. if spot is partial fill with 50%, then perp should be partial fill with 50%)
    # TODO: explore borrowing/ lending from spot
    def buy_spot_short_perp(self) -> None:
        return

    def should_sell_spot_long_perp(self) -> bool:
        spot_sell_price = self.limit_taker_price(self.spot_connector, is_buy=False)
        perp_buy_price = self.limit_taker_price(self.perp_connector, is_buy=True)
        ret_pbs = float((spot_sell_price - perp_buy_price) / perp_buy_price) * 10000
        return ret_pbs >= self.spread_bps

    def can_sell_spot_long_perp(self) -> bool:
        return True

    def sell_spot_long_perp(self) -> None:
        return

    def create_order_proposals(self) -> List[OrderCandidate]:
        buy_price = Decimal("1.")
        sell_price = Decimal("1.")
        buy_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal(self.order_amount),
            price=buy_price,
        )
        sell_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal(self.order_amount),
            price=sell_price,
        )

        return [buy_order, sell_order]

    def limit_taker_buy_price_with_slippage(
        self, connector_name: str, is_buy: bool
    ) -> Decimal:
        price = self._limit_taker_price(connector_name, is_buy)
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

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        spot_buy_price = self.limit_taker_price(self.spot_connector, is_buy=True)
        perp_sell_price = self.limit_taker_price(self.perp_connector, is_buy=False)
        ret_percent = float((perp_sell_price - spot_buy_price) / spot_buy_price) * 100
        lines.append(f"Perp Buy: {spot_buy_price}")
        lines.append(f"Spot Sell: {perp_sell_price}")
        lines.append(f"Return: {ret_percent:.2f}%")

        spot_sell_price = self.limit_taker_price(self.spot_connector, is_buy=False)
        perp_buy_price = self.limit_taker_price(self.perp_connector, is_buy=True)
        ret_percent = float((spot_sell_price - perp_buy_price) / perp_buy_price) * 100
        lines.append(f"Spot Buy: {spot_sell_price}")
        lines.append(f"Perp Sell: {perp_buy_price}")
        lines.append(f"Return: {ret_percent:.2f}%")
        return "\n".join(lines)
