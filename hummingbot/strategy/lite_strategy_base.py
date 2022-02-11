from decimal import Decimal
from typing import Dict, Set, List, Any
from time import perf_counter
import asyncio
import logging
import pandas as pd
import numpy as np
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, PositionAction
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

lsb_logger = None
s_decimal_nan = Decimal("NaN")


class LiteStrategyBase(StrategyPyBase):

    markets: Dict[str, Set[str]]

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global lsb_logger
        if lsb_logger is None:
            lsb_logger = logging.getLogger(__name__)
        return lsb_logger

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__()
        self.connectors: Dict[str, ConnectorBase] = connectors
        self.ready_to_trade: bool = False
        self.tick_size: float = 1.
        self.add_markets(list(connectors.values()))

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self.ready_to_trade:
            # Check if there are restored orders, they should be canceled before strategy starts.
            self.ready_to_trade = all(ex.ready for ex in self.connectors.values())
            if not self.ready_to_trade:
                for con in [c for c in self.connectors.values() if not c.ready]:
                    self.logger().warning(f"{con.name} is not ready. Please wait...")
                return
            else:
                self.logger().info("All connector(s) are ready. Trading started.")

    async def run(self):
        while True:
            start_time = perf_counter()
            if self.ready_to_trade:
                await self.on_tick()
            end_time = perf_counter()
            await asyncio.sleep(self.tick_size - (end_time - start_time))

    async def on_tick(self):
        pass

    def start(self, clock: Clock, timestamp: float):
        self.run_task = safe_ensure_future(self.run())

    def stop(self, clock: Clock):
        self.run_task.cancel()

    def buy(self,
            connector_name: str,
            trading_pair: str,
            amount: Decimal,
            order_type: OrderType,
            price=s_decimal_nan,
            position_action=PositionAction.OPEN):
        market_pair = self.get_market_trading_pair_tuple(connector_name, trading_pair)
        self.logger().info(f"Creating {trading_pair} buy order: price: {price} amount: {amount}.")
        self.buy_with_specific_market(market_pair, amount, order_type, price, position_action=position_action)

    def sell(self,
             connector_name: str,
             trading_pair: str,
             amount: Decimal,
             order_type,
             price=s_decimal_nan,
             position_action=PositionAction.OPEN):
        market_pair = self.get_market_trading_pair_tuple(connector_name, trading_pair)
        self.logger().info(f"Creating {trading_pair} sell order: price: {price} amount: {amount}.")
        self.sell_with_specific_market(market_pair, amount, order_type, price, position_action=position_action)

    def get_active_orders(self, connector_name: str = None) -> List[LimitOrder]:
        orders = self.order_tracker.active_limit_orders
        if not connector_name:
            if len(self.connectors.values()) > 1:
                raise Exception("There are more than one connector, please specify connector parameter.")
            connector = self.connectors.values()[0]
        else:
            connector = self.connectors[connector_name]
        return [o[1] for o in orders if o[0] == connector]

    def get_assets(self, connector_name: str) -> List[str]:
        result: List = []
        for trading_pair in self.markets[connector_name]:
            for asset in trading_pair.split("-"):
                if asset not in result:
                    result.append(asset)
        return sorted(result)

    def get_market_trading_pair_tuple(self,
                                      connector_name: str,
                                      trading_pair: str) -> MarketTradingPairTuple:
        base, quote = trading_pair.split("-")
        return MarketTradingPairTuple(self.connectors[connector_name], trading_pair, base, quote)

    def get_market_trading_pair_tuples(self) -> List[MarketTradingPairTuple]:
        result: List[MarketTradingPairTuple] = []
        for name, connector in self.connectors.items():
            for trading_pair in self.markets[name]:
                result.append(self.get_market_trading_pair_tuple(name, trading_pair))
        return result

    def get_balance_df(self) -> pd.DataFrame:
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

    async def active_orders_df(self) -> pd.DataFrame:
        """
        Return the active orders in a DataFrame.
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

    async def format_status(self) -> str:
        """
        Return the budget, market, miner and order statuses.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        try:
            df = await self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
