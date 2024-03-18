from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class StrategyAction(Enum):
    NULL = 0
    BUY_SPOT_SHORT_PERP = 1
    SELL_SPOT_LONG_PERP = 2


@dataclass
class Opportunity:
    trading_pair: str
    exchange: str
    info: FundingInfo
    action: StrategyAction


@dataclass
class SpotOrder:
    trading_pair: str
    exchange: str
    side: bool
    amount: Decimal
    price: Decimal


'''
    To begin with this Script Strategy will only have 1 position open per "bot"
    It will scan over a list of given trading pairs rank them by funding rate and
    will open either a long or short position on the perp exchange and hedge it on
    the spot exchange.
    Funding rate is positive -> longs pay short
    Funding rate is negative -> short pay longs
'''


class AutomatedCashNCarry(ScriptStrategyBase):
    CURRENT_STRATEGY_SIDE: PositionSide = None
    STRATEGY_INFLIGHT = False
    inflight_spot_orders: List[SpotOrder] = []

    perp_connector = "binance_perpetual_testnet"
    spot_connector = "kucoin_paper_trade"
    # spot_connector = "kucoin"
    trading_pair = "ETH-USDT"
    trading_pairs_set = {"ETH-USDT", "XRP-USDT", "CRV-USDT", "DOGE-USDT", "UNI-USDT"}
    # trading_pairs_set = {"ETH-USDT"}
    funding_data = {}

    long_opportunities = {}
    short_opportunities = {}

    # trading_pairs_list = ["ETH-USDT", "XRP-USDT", "CRV-USDT", "DOGE-USDT", "UNI-USDT", "PEPE-USDT"]
    leverage = 10
    markets = {
        spot_connector: trading_pairs_set,
        perp_connector: trading_pairs_set
    }

    perp_trading_pairs: List

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.set_leverage()
        # self.get_funding_rate_for_pair()

    '''
        Implement events from async clocks
    '''

    def set_leverage(self):
        self.perp_trading_pairs = self.get_perpetual_market_trading_pair_tuples(True)

    def on_tick(self):
        if self.ready_to_trade:
            for connector_name, connector in self.connectors.items():
                # if connector.is_funding_info_initialized():
                if "perpetual" in connector_name:
                    for marketTradingPair in self.perp_trading_pairs:
                        funding_info = connector._perpetual_trading.get_funding_info(marketTradingPair.trading_pair)
                        '''
                            funding_data ex
                            dict{
                                "BTC-USDT": {},
                                "ETH-USDT": {
                                    "kucoin_perpetual": {
                                        Funding_Info Data
                                    },
                                    "binance_perpetual": {
                                        Funding_Info Data
                                    },
                                    "hyperliquid_perpetual": {
                                        Funding_Info Data
                                    }
                                }
                            }
                        '''
                        if funding_info.trading_pair not in self.funding_data:
                            self.funding_data[funding_info.trading_pair] = {}
                        self.funding_data[funding_info.trading_pair][connector_name] = funding_info
            self.rank_funding_info()

            if not self.STRATEGY_INFLIGHT:
                op = self.get_best_opportunity()
                if op is not None:
                    self.notify_hb_app_with_timestamp(
                        f"going to open short {op.trading_pair} @ {op.exchange} - rate {op.info.rate}")
                    self.notify_hb_app_with_timestamp(f"Heding BUY @ spot for {op.trading_pair}")

                if op.action == StrategyAction.BUY_SPOT_SHORT_PERP:
                    conversion_rate = RateOracle.get_instance().get_pair_rate(op.trading_pair)
                    self.logger().info(f"got the conversion rate {conversion_rate}")
                    amount = Decimal(100) / conversion_rate
                    amount_perp = Decimal(100) / conversion_rate
                    self.logger().info(f"perp amount {amount_perp}")
                    # buy spot
                    print("buying spot")
                    spot_order_id = self.buy(
                        self.spot_connector,
                        op.trading_pair,
                        amount,
                        OrderType.MARKET,
                        self.connectors[self.spot_connector].get_mid_price(op.trading_pair)
                    )
                    self.logger().info(f"order id -> {spot_order_id}")
                    self.inflight_spot_orders.append(SpotOrder(op.trading_pair, self.spot_connector, True, amount,
                                                               self.connectors[self.spot_connector].get_mid_price(
                                                                   op.trading_pair)))

                    self.place_perp_order(op.trading_pair, amount_perp)

            self.STRATEGY_INFLIGHT = True

    def on_stop(self):
        self.logger().info("IM STOPPING MUST CLOSE OPEN POSITIONS")
        self.close_open_positions()
        if len(self.inflight_spot_orders) > 0:
            self.logger().info("reverting spot position")
            order = self.inflight_spot_orders[0]
            sell_order_id = self.sell(
                order.exchange,
                order.trading_pair,
                order.amount,
                OrderType.MARKET,
                order.price
            )
            self.logger().info(f"reverting spot position {sell_order_id}")
            self.inflight_spot_orders.pop()

    def place_perp_order(self, trading_pair: str, amount: Decimal):
        # What is the difference between PositionMode oneway and hedge
        perp_order_id = self.sell(
            self.perp_connector,
            trading_pair,
            amount,
            OrderType.MARKET,
            self.connectors[self.spot_connector].get_mid_price(trading_pair),
            PositionAction.OPEN
        )
        self.logger().info(f"open short perpetual -> {perp_order_id}")

    '''
        Various getters
    '''
    def get_best_opportunity(self) -> Opportunity | None:
        # Retrieve the first item from the sorted dictionary
        first_item_short: Opportunity = next(iter(self.short_opportunities.values()), Decimal('0'))
        first_item_long: Opportunity = next(iter(self.long_opportunities.values()), Decimal('0'))

        # Check if there is any item in the dictionary
        if (first_item_short is not None or
                first_item_long is not None):
            long_op_rate = abs(first_item_long.info.rate) if first_item_long != Decimal('0') else Decimal('0')
            short_op_rate = first_item_short.info.rate if first_item_short != Decimal('0') else Decimal('0')
            if long_op_rate > short_op_rate:
                return first_item_long
            else:
                return first_item_short

        else:
            # Handle the case when the dictionary is empty
            return None

    def rank_funding_info(self):
        for trading_pair, exchanges in self.funding_data.items():
            for exchange, info in exchanges.items():
                key = f"{trading_pair}_{exchange}"
                if info.rate > Decimal('0'):
                    if key not in self.short_opportunities or self.short_opportunities[key].info.rate != info.rate:
                        print(f"S: updating rates for {trading_pair} info.rate={info.rate}")
                        self.short_opportunities[key] = Opportunity(
                            trading_pair, exchange, info, StrategyAction.BUY_SPOT_SHORT_PERP)
                else:
                    if key not in self.long_opportunities or self.long_opportunities[key].info.rate != info.rate:
                        print(f"L: updating rates for {trading_pair} info.rate={info.rate}")
                        self.long_opportunities[key] = Opportunity(
                            trading_pair, exchange, info, StrategyAction.SELL_SPOT_LONG_PERP)

        self.short_opportunities = dict(
            sorted(self.short_opportunities.items(), key=lambda x: x[1].info.rate, reverse=True))
        self.long_opportunities = dict(
            sorted(self.long_opportunities.items(), key=lambda x: x[1].info.rate, reverse=True))

    def get_funding_rate_for_pair(self, exchange: str, pair: str) -> FundingInfo:
        """
            if perpetual price > spot price => funding_rate is positive
            if perpetual price < spot price => funding_rate is negative
        """
        return self.connectors[exchange]._perpetual_trading.get_funding_info(pair)

    def sell_spot_positions(self):
        for connector_name, connector in self.connectors.items():
            if "perpetual" not in connector_name:
                pass

    def close_open_positions(self):
        # Closing positions
        for connector_name, connector in self.connectors.items():
            if "perpetual" in connector_name:
                for trading_pair, position in connector.account_positions.items():
                    self.logger().info(f"closing position {position.position_side}-{trading_pair} @ {connector_name}")
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
            else:
                self.logger().info("Ignore its a spot")

    '''
        Format Status and its Data Frame helper functions
    '''

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

        # Log Funding rates (maybe pull into a screener)
        short_funding_info_df = self.get_funding_info_df(self.short_opportunities)
        lines.extend(
            ["", " Short Opportunities:"] + ["   " + line for line in
                                             short_funding_info_df.to_string(index=False).split("\n")])

        long_funding_info_df = self.get_funding_info_df(self.long_opportunities)
        lines.extend(
            ["", " Long Opportunities:"] + ["   " + line for line in
                                            long_funding_info_df.to_string(index=False).split("\n")])

        # Log open positions
        open_positions_info_df = self.get_open_position_df()
        lines.extend(["", " Position info:"] + ["   " + line for line in
                                                open_positions_info_df.to_string(index=False).split("\n")])

        # Log hedged spot position or just balance

        return "\n".join(lines)

    def get_open_position_df(self) -> pd.DataFrame:
        """
        Return a data frame of all active orders for displaying purpose.
        """
        columns = ["Exchange", "Market", "Position", "Entry", "Amount", "leverage", "uPnL(%)"]
        data = []
        for connector_name, connector in self.connectors.items():
            if "perpetual" in connector_name:
                for name, position in connector._perpetual_trading.account_positions.items():
                    if position is not None:
                        data.append([
                            connector_name,
                            position.trading_pair,
                            position.position_side,
                            float(position.entry_price),
                            float(position.amount),
                            float(position.leverage),
                            float(position.unrealized_pnl)
                        ])
        if not data:
            # self.logger().info("There is no active open position")
            data.append(["NaN", "NaN", "NaN", "NaN", "NaN", "NaN", "NaN"])
            df = pd.DataFrame(data=data, columns=columns)
            return df

        df = pd.DataFrame(data=data, columns=columns)
        df.sort_values(by=["Exchange", "Market", "Position"], inplace=True)
        return df

    def get_premium_collected_df(self) -> pd.DataFrame:
        pass

    @staticmethod
    def get_funding_info_df(opps: Dict[str, Opportunity]) -> pd.DataFrame:
        """
        Returns a data frame for short and long opportunities
        """
        columns: List[str] = ["Exchange", "Asset", "Funding rate(+/-)", "Mark Px", "Idx Px", "next ts"]
        data: List[Any] = []
        for val in opps.values():
            data.append([
                val.exchange,
                val.trading_pair.split("-")[0],
                val.info.rate,
                val.info.mark_price,
                val.info.index_price,
                val.info.next_funding_utc_timestamp
            ])
        return pd.DataFrame(data=data, columns=columns).replace(np.nan, '', regex=True)

    def get_perpetual_market_trading_pair_tuples(self, set_leverage: bool) -> List[MarketTradingPairTuple]:
        """
        Returns a list of MarketTradingPairTuple for all perpetual connectors and trading pairs combination.
        """
        result: List[MarketTradingPairTuple] = []
        for name, connector in self.connectors.items():
            if "perpetual" in name:
                for trading_pair in self.markets[name]:
                    if set_leverage:
                        connector.set_position_mode(PositionMode.HEDGE)
                        connector.set_leverage(trading_pair=trading_pair, leverage=self.leverage)
                        self.logger().info(
                            f"Setting leverage to {self.leverage}x for {self.perp_connector} on {trading_pair}"
                        )
                    result.append(self._market_trading_pair_tuple(name, trading_pair))
        return result
