from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Union

import numpy as np
import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    RangePositionClosedEvent,
    SellOrderCompletedEvent,
)
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
    exchange_id: str


@dataclass
class Position:
    trading_pair: str
    exchange: str
    position_side: PositionSide
    amount: Decimal
    price: Decimal
    exchange_id: str


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
    dry_run: bool = False
    inflight_strategy_position_and_order: Dict[str, Union[Position, SpotOrder]] = {}
    inflight_trading_pair = ""
    perp_connector = "binance_perpetual_testnet"
    spot_connector = "kucoin_paper_trade"
    # spot_connector = "kucoin"
    trading_pairs_set = {"ETH-USDT", "XRP-USDT", "CRV-USDT",
                         "DOGE-USDT", "UNI-USDT", "BCH-USDT",
                         "EOS-USDT", "LTC-USDT", "LINK-USDT",
                         "ALGO-USDT", "BNB-USDT", "ZRX-USDT"}

    funding_data = {}

    long_opportunities = {}
    short_opportunities = {}

    # trading_pairs_list = ["ETH-USDT", "XRP-USDT", "CRV-USDT", "DOGE-USDT", "UNI-USDT", "PEPE-USDT"]
    perp_trading_pairs: List
    leverage = 5
    markets = {
        spot_connector: trading_pairs_set,
        perp_connector: trading_pairs_set
    }

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.perp_trading_pairs = self.get_perpetual_market_trading_pair_tuples()
        self.set_leverage()

    '''
        Implement events from async clocks
    '''

    def set_leverage(self):
        for trading_pair in self.perp_trading_pairs:
            self.connectors[self.perp_connector].set_position_mode(PositionMode.HEDGE)
            self.connectors[self.perp_connector].set_leverage(trading_pair=trading_pair, leverage=self.leverage)
            self.logger().info(
                f"Setting leverage to {self.leverage}x for {self.perp_connector} on {trading_pair}"
            )

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
                    self.action(op)

            self.STRATEGY_INFLIGHT = True
            self.monitor_funding_rates()

    def monitor_funding_rates(self):
        op = self.get_best_opportunity()
        if op.trading_pair != self.inflight_trading_pair:
            self.logger().info(f"Recieved a new top contender {op.trading_pair} - Evaluating...")
            rate_diff = op.info.rate - self.get_funding_rate_for_pair(self.perp_connector,
                                                                      self.inflight_trading_pair).rate

            rate_diff_percent = np.abs(rate_diff / op.info.rate) * Decimal('100')

            # Check if the rate difference is greater than 2%
            if rate_diff_percent > Decimal('2'):
                # Perform your action here
                # For example:
                print("Rate difference is greater than 2%")
            else:
                print("Rate difference is not greater than 2%")

            self.notify_hb_app_with_timestamp(
                f"NEW: going to open short {op.trading_pair} @ {op.exchange} - rate {op.info.rate}")
            self.close_open_positions()
            self.revert_spot_positions()
            # Reset inflight map
            self.inflight_strategy_position_and_order = {}
            self.action(op)

    def action(self, op: Opportunity):
        if op.action == StrategyAction.BUY_SPOT_SHORT_PERP:
            conversion_rate = RateOracle.get_instance().get_pair_rate(op.trading_pair)
            amount = Decimal(100) / conversion_rate
            amount_perp = Decimal(100) / conversion_rate
            price = self.connectors[self.spot_connector].get_mid_price(op.trading_pair)
            # buy spot

            spot_order_id = self.buy(
                self.spot_connector,
                op.trading_pair,
                amount,
                OrderType.MARKET,
                self.connectors[self.spot_connector].get_mid_price(op.trading_pair)
            )
            self.logger().info(f"order id -> {spot_order_id}")
            perp_id = self.place_perp_order(op.trading_pair, amount_perp)

            self.inflight_strategy_position_and_order[f"perpetual-{op.trading_pair}"] = Position(
                op.trading_pair,
                self.perp_connector,
                PositionSide.SHORT,
                amount_perp,
                price,
                perp_id
            )
            self.inflight_strategy_position_and_order[f"spot-{op.trading_pair}"] = SpotOrder(
                op.trading_pair,
                self.spot_connector,
                True,
                amount,
                price,
                spot_order_id
            )
            self.inflight_trading_pair = op.trading_pair

        # elif op.action == StrategyAction.SELL_SPOT_LONG_PERP:
        #     self.logger().info("Check if I have asset")
        #     pass

    def on_stop(self):
        self.close_open_positions()
        self.revert_spot_positions()
        self.inflight_trading_pair = ""
        self.inflight_strategy_position_and_order = {}
        self.STRATEGY_INFLIGHT = False

    def place_perp_order(self, trading_pair: str, amount: Decimal) -> str:
        # What is the difference between PositionMode oneway and hedge
        if not self.dry_run:
            perp_order_id = self.sell(
                self.perp_connector,
                trading_pair,
                amount,
                OrderType.MARKET,
                self.connectors[self.spot_connector].get_mid_price(trading_pair),
                PositionAction.OPEN
            )
            self.logger().info(f"open short perpetual -> {perp_order_id}")
        else:
            perp_order_id = 13337
            self.logger().info(f"DRY-RUN    open short perpetual -> {perp_order_id}")

        return perp_order_id

    '''
        Various getters
    '''

    def get_best_opportunity(self) -> Opportunity | None:
        first_item_short: Opportunity = next(iter(self.short_opportunities.values()), Decimal('0'))
        first_item_long: Opportunity = next(iter(self.long_opportunities.values()), Decimal('0'))

        if (first_item_short is not None or
                first_item_long is not None):
            long_op_rate = abs(first_item_long.info.rate) if first_item_long != Decimal('0') else Decimal('0')
            short_op_rate = first_item_short.info.rate if first_item_short != Decimal('0') else Decimal('0')
            if long_op_rate > short_op_rate:
                return first_item_long
            else:
                return first_item_short
        else:
            return None

    def rank_funding_info(self):
        for trading_pair, exchanges in self.funding_data.items():
            for exchange, info in exchanges.items():
                key = f"{trading_pair}_{exchange}"
                if info.rate > Decimal('0'):
                    if key not in self.short_opportunities or self.short_opportunities[key].info.rate != info.rate:
                        self.short_opportunities[key] = Opportunity(
                            trading_pair, exchange, info, StrategyAction.BUY_SPOT_SHORT_PERP)
                else:
                    if key not in self.long_opportunities or self.long_opportunities[key].info.rate != info.rate:
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

    def revert_spot_positions(self):
        if f"spot-{self.inflight_trading_pair}" in self.inflight_strategy_position_and_order:
            order = self.inflight_strategy_position_and_order[f"spot-{self.inflight_trading_pair}"]
            sell_order_id = self.sell(
                order.exchange,
                order.trading_pair,
                order.amount,
                OrderType.MARKET,
                order.price
            )
            self.logger().info(f"reverting spot position {sell_order_id}")

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

    def get_perpetual_market_trading_pair_tuples(self) -> List[MarketTradingPairTuple]:
        """
        Returns a list of MarketTradingPairTuple for all perpetual connectors and trading pairs combination.
        """
        result: List[MarketTradingPairTuple] = []
        for name, connector in self.connectors.items():
            if "perpetual" in name:
                for trading_pair in self.markets[name]:
                    result.append(self._market_trading_pair_tuple(name, trading_pair))
        return result

    '''
        Events handling
    '''

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        """
        Method called when the connector notifies a buy order has been completed (fully filled)
        """
        self.logger().info(f"The buy order {event.order_id} has been completed")

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        """
        Method called when the connector notifies a sell order has been completed (fully filled)
        """
        self.logger().info(f"The sell order {event.order_id} has been completed")

    def did_fail_order(self, event: MarketOrderFailureEvent):
        """
        Method called when the connector notifies an order has failed
        """
        self.logger().info(f"The order {event.order_id} failed")
        # self.close_open_positions()

    def did_close_position(self, closed_position_event: RangePositionClosedEvent):
        self.logger().info(
            f"Closing position {closed_position_event.token_0}-{closed_position_event.token_1}. {closed_position_event.token_id} --- fee {closed_position_event.claimed_fee_0} or {closed_position_event.claimed_fee_1}")
