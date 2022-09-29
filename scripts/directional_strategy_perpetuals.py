from decimal import Decimal

from hummingbot.connector.derivative.position import Position, PositionSide
from hummingbot.core.data_type.common import OrderType, PositionAction
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DirectionalPosition:
    def __init__(self, position: Position, take_profit: float, stop_loss: float, time_in_position: float):
        self._position = position
        self._take_profit = take_profit
        self._stop_loss = stop_loss
        self._time_in_position = time_in_position
        if position.position_side == PositionSide.SHORT:
            self._stop_loss_price = position.entry_price * (1 + stop_loss)
            self._take_profit_price = position.entry_price * (1 - take_profit)
        elif position.position_side == PositionSide.LONG:
            self._stop_loss_price = position.entry_price * (1 - stop_loss)
            self._take_profit_price = position.entry_price * (1 + take_profit)
        self._take_profit_order = None


class DirectionalStrategyPerpetuals(ScriptStrategyBase):
    position_cfg = {
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
        "take_profit": None,
        "stop_loss": None
    }
    markets = {position_cfg["exchange"]: {position_cfg["trading_pair"]}}

    def on_tick(self):
        if len(self.connectors[self.position_cfg["exchange"]].account_positions) == 0:
            self.check_and_place_position()
        else:
            self.control_position()

    def check_and_place_position(self):
        signal = self.get_signal()
        if signal > self.signal_thresholds["long"] or signal < self.signal_thresholds["short"]:
            price = self.connectors[self.position_cfg["exchange"]].get_mid_price(self.position_cfg["trading_pair"])
            is_buy = True if signal > self.signal_thresholds["long"] else False
            self.place_order(
                connector_name=self.position_cfg["exchange"],
                trading_pair=self.position_cfg["trading_pair"],
                amount=Decimal(self.position_cfg["order_amount_usd"]) / price,
                price=price,
                order_type=OrderType.MARKET,
                position_action=PositionAction.OPEN,
                is_buy=is_buy
            )

    def control_position(self):
        # positions = self.connectors[self.position_cfg["exchange"]].account_positions
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
            self.buy(connector_name, trading_pair, amount, order_type, price, position_action)
        else:
            self.sell(connector_name, trading_pair, amount, order_type, price, position_action)
