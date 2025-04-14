import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd
from pydantic import BaseModel

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, PositionAction
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

lsb_logger = None
s_decimal_nan = Decimal("NaN")


class ScriptConfigBase(BaseModel):
    """
    Base configuration class for script strategies. Subclasses can add their own configuration parameters.
    """
    pass


class ScriptStrategyBase(StrategyPyBase):
    """
    This is a strategy base class that simplifies strategy creation and implements basic functionality to create scripts.
    """

    # This class member defines connectors and their trading pairs needed for the strategy operation,
    markets: Dict[str, Set[str]]

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global lsb_logger
        if lsb_logger is None:
            lsb_logger = logging.getLogger(__name__)
        return lsb_logger

    @classmethod
    def init_markets(cls, config: BaseModel):
        """This method is called in the start command if the script has a config class defined, and allows
        the script to define the market connectors and trading pairs needed for the strategy operation."""
        raise NotImplementedError

    def __init__(self, connectors: Dict[str, ConnectorBase], config: Optional[BaseModel] = None):
        """
        Initialising a new script strategy object.

        :param connectors: A dictionary of connector names and their corresponding connector.
        """
        super().__init__()
        self.connectors: Dict[str, ConnectorBase] = connectors
        self.ready_to_trade: bool = False
        self.add_markets(list(connectors.values()))
        self.config = config

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        Checks if all connectors are ready, if so the strategy is ready to trade.

        :param timestamp: current tick timestamp
        """
        if not self.ready_to_trade:
            self.ready_to_trade = all(ex.ready for ex in self.connectors.values())
            if not self.ready_to_trade:
                for con in [c for c in self.connectors.values() if not c.ready]:
                    self.logger().warning(f"{con.name} is not ready. Please wait...")
                return
        else:
            self.on_tick()

    def on_tick(self):
        """
        An event which is called on every tick, a sub class implements this to define what operation the strategy needs
        to operate on a regular tick basis.
        """
        pass

    async def on_stop(self):
        pass

    def buy(self,
            connector_name: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            price=s_decimal_nan,
            position_action=PositionAction.OPEN) -> str:
        """
        A wrapper function to buy_with_specific_market.

        :param connector_name: The name of the connector
        :param trading_pair: The market trading pair
        :param amount: An order amount in base token value
        :param order_type: The type of the order
        :param price: An order price
        :param position_action: A position action (for perpetual market only)

        :return: The client assigned id for the new order
        """
        market_pair = self._market_trading_pair_tuple(connector_name, trading_pair)
        self.logger().debug(f"Creating {trading_pair} buy order: price: {price} amount: {amount}.")
        return self.buy_with_specific_market(market_pair, amount, order_type, price, position_action=position_action)

    def sell(self,
             connector_name: str,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType,
             price=s_decimal_nan,
             position_action=PositionAction.OPEN) -> str:
        """
        A wrapper function to sell_with_specific_market.

        :param connector_name: The name of the connector
        :param trading_pair: The market trading pair
        :param amount: An order amount in base token value
        :param order_type: The type of the order
        :param price: An order price
        :param position_action: A position action (for perpetual market only)

        :return: The client assigned id for the new order
        """
        market_pair = self._market_trading_pair_tuple(connector_name, trading_pair)
        self.logger().debug(f"Creating {trading_pair} sell order: price: {price} amount: {amount}.")
        return self.sell_with_specific_market(market_pair, amount, order_type, price, position_action=position_action)

    def cancel(self,
               connector_name: str,
               trading_pair: str,
               order_id: str):
        """
        A wrapper function to cancel_order.

        :param connector_name: The name of the connector
        :param trading_pair: The market trading pair
        :param order_id: The identifier assigned by the client of the order to be cancelled
        """
        market_pair = self._market_trading_pair_tuple(connector_name, trading_pair)
        self.cancel_order(market_trading_pair_tuple=market_pair, order_id=order_id)

    def get_active_orders(self, connector_name: str) -> List[LimitOrder]:
        """
        Returns a list of active orders for a connector.
        :param connector_name: The name of the connector.
        :return: A list of active orders
        """
        orders = self.order_tracker.active_limit_orders
        connector = self.connectors[connector_name]
        return [o[1] for o in orders if o[0] == connector]

    def get_assets(self, connector_name: str) -> List[str]:
        """
        Returns a unique list of unique of token names sorted alphabetically

        :param connector_name: The name of the connector

        :return: A list of token names
        """
        result: Set = set()
        for trading_pair in self.markets[connector_name]:
            result.update(split_hb_trading_pair(trading_pair))
        return sorted(result)

    def get_market_trading_pair_tuples(self) -> List[MarketTradingPairTuple]:
        """
        Returns a list of MarketTradingPairTuple for all connectors and trading pairs combination.
        """

        result: List[MarketTradingPairTuple] = []
        for name, connector in self.connectors.items():
            for trading_pair in self.markets[name]:
                result.append(self._market_trading_pair_tuple(name, trading_pair))
        return result

    def get_balance_df(self) -> pd.DataFrame:
        """
        Returns a data frame for all asset balances for displaying purpose.
        """
        columns: List[str] = ["Exchange", "Asset", "Total Balance", "Available Balance"]
        data: List[Any] = []
        for connector_name, connector in self.connectors.items():
            for asset in self.get_assets(connector_name):
                data.append([connector_name,
                             asset,
                             float(connector.get_balance(asset)),
                             float(connector.get_available_balance(asset))])
        df = pd.DataFrame(data=data, columns=columns).replace(np.nan, '', regex=True)
        df.sort_values(by=["Exchange", "Asset"], inplace=True)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        """
        Return a data frame of all active orders for displaying purpose.
        """
        columns = ["Exchange", "Market", "Side", "Price", "Amount", "Age"]
        data = []
        for connector_name, connector in self.connectors.items():
            for order in self.get_active_orders(connector_name):
                age_txt = "n/a" if order.age() <= 0. else pd.Timestamp(order.age(), unit='s').strftime('%H:%M:%S')
                data.append([
                    connector_name,
                    order.trading_pair,
                    "buy" if order.is_buy else "sell",
                    float(order.price),
                    float(order.quantity),
                    age_txt
                ])
        if not data:
            raise ValueError
        df = pd.DataFrame(data=data, columns=columns)
        df.sort_values(by=["Exchange", "Market", "Side"], inplace=True)
        return df

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def _market_trading_pair_tuple(self,
                                   connector_name: str,
                                   trading_pair: str) -> MarketTradingPairTuple:
        """
        Creates and returns a new MarketTradingPairTuple

        :param connector_name: The name of the connector
        :param trading_pair: The trading pair
        :return: A new MarketTradingPairTuple object.
        """
        base, quote = split_hb_trading_pair(trading_pair)
        return MarketTradingPairTuple(self.connectors[connector_name], trading_pair, base, quote)
