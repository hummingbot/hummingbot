from decimal import Decimal
from typing import Union

from hummingbot.connector.derivative.position import PositionSide
from hummingbot.core.data_type.common import OrderType, PositionAction
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DirectionalPosition:
    def __init__(self, order_id: str, trading_pair: str, position_side: PositionSide, take_profit: float, stop_loss: float, time_in_position: float):
        self._order_id = order_id
        self._position_side = position_side
        self._trading_pair = trading_pair
        self._leverage = None
        self._take_profit = Decimal(take_profit)
        self._stop_loss = Decimal(stop_loss)
        self._time_in_position = time_in_position
        self._entry_price = Decimal("0")
        self._stop_loss_price = Decimal("0")
        self._take_profit_price = Decimal("0")
        self._take_profit_order = None
        self._position_state = OrderState.PENDING_CREATE
        self._creation_timestamp = None
        self._filled_timestamp = None
        self._trades = []

    def update_with_order_creation_event(self, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        self._entry_price = event.price
        self._leverage = event.leverage
        self._creation_timestamp = event.creation_timestamp
        self._position_state = OrderState.OPEN
        if self._position_side == PositionSide.SHORT:
            self._stop_loss_price = self._entry_price * (1 + self._stop_loss)
            self._take_profit_price = self._entry_price * (1 - self._take_profit)
        elif self._position_side == PositionSide.LONG:
            self._stop_loss_price = self._entry_price * (1 - self._stop_loss)
            self._take_profit_price = self._entry_price * (1 + self._take_profit)

    def update_with_order_complete_event(self, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        self._entry_price = Decimal(event.quote_asset_amount / event.base_asset_amount)
        self._filled_timestamp = event.timestamp
        self._position_state = OrderState.FILLED


class DirectionalStrategyPerpetuals(ScriptStrategyBase):
    position_cfg = {
        "signal_id": 1,
        "stages": [
            {
                "stage": 1,
                "take_profit": 0.05,
                "stop_loss": 0.02,
                "time_in_position": 30
            }
        ],
        "order_amount_usd": 20,
        "exchange": "binance_perpetual_testnet",
        "trading_pair": "ETH-USDT"
    }
    signal_thresholds = {
        "long": 0.8,
        "short": -0.8
    }
    active_position = {
        "position": None,
        "stage": None,
    }
    max_positions = 1
    directional_positions = {}
    markets = {position_cfg["exchange"]: {position_cfg["trading_pair"]}}

    def on_tick(self):
        if len(self.directional_positions.keys()) < self.max_positions:
            self.check_and_place_position()
        else:
            self.logger().info(self.connectors[self.position_cfg["exchange"]].account_positions)
            self.logger().info(self.connectors[self.position_cfg["exchange"]].in_flight_orders)
            self.control_position()

    def check_and_place_position(self):
        signal = self.get_signal()
        if signal > self.signal_thresholds["long"] or signal < self.signal_thresholds["short"]:
            price = self.connectors[self.position_cfg["exchange"]].get_mid_price(self.position_cfg["trading_pair"])
            is_buy = True if signal > self.signal_thresholds["long"] else False
            order_id = self.place_order(
                connector_name=self.position_cfg["exchange"],
                trading_pair=self.position_cfg["trading_pair"],
                amount=Decimal(self.position_cfg["order_amount_usd"]) / price,
                price=price,
                order_type=OrderType.MARKET,
                position_action=PositionAction.OPEN,
                is_buy=is_buy
            )
            self.directional_positions[order_id] = DirectionalPosition(
                order_id=order_id,
                trading_pair=self.position_cfg["trading_pair"],
                position_side=PositionSide.LONG if is_buy else PositionSide.SHORT,
                take_profit=self.position_cfg["stages"][0]["take_profit"],
                stop_loss=self.position_cfg["stages"][0]["stop_loss"],
                time_in_position=self.position_cfg["stages"][0]["time_in_position"],
            )

    def control_position(self):
        # active_positions = self.connectors[self.position_cfg["exchange"]].account_positions.values()
        # active_trading_pairs = [position.trading_pair for position in active_positions]
        #
        # for order_id, directional_position in self.directional_positions.items():
        #     pass
        pass

    def get_signal(self):
        return 0.9

    def place_order(self,
                    connector_name: str,
                    trading_pair: str,
                    is_buy: bool,
                    amount: Decimal,
                    order_type: OrderType,
                    position_action: PositionAction,
                    price=Decimal("NaN"),
                    ):
        if is_buy:
            return self.buy(connector_name, trading_pair, amount, order_type, price, position_action)
        else:
            return self.sell(connector_name, trading_pair, amount, order_type, price, position_action)

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        if event.order_id in self.directional_positions:
            self.directional_positions[event.order_id].update_with_order_complete_event(event)

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        if event.order_id in self.directional_positions:
            self.directional_positions[event.order_id].update_with_order_complete_event(event)

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        self.directional_positions[event.order_id].update_with_order_creation_event(event)

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        self.directional_positions[event.order_id].update_with_order_creation_event(event)
