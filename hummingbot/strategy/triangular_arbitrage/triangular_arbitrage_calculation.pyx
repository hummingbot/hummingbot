# distutils: language=c++

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.event.events import TradeType, OrderType, TradeFee
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.strategy.triangular_arbitrage.model.arbitrage cimport (
    Node,
    Edge,
    TradeDirection,
    TriangularArbitrage,
    trade_direction_to_str
)
from hummingbot.strategy.triangular_arbitrage.model.opportunity cimport (ModelOrder, Opportunity)
from hummingbot.strategy.triangular_arbitrage.model.model_book cimport ModelBook
from hummingbot.strategy.triangular_arbitrage.optimizer.optimizer cimport Optimizer
from hummingbot.strategy.triangular_arbitrage.optimizer.optimizer import _BBB, _BBS, _BSB, _BSS, _SBB, _SBS, _SSB, _SSS
from hummingbot.strategy.triangular_arbitrage.optimizer.order_book_preprocessor import OrderBookPreprocessor
from typing import List, Optional
from decimal import Decimal
import numpy as np
import logging

s_tac_logger = None
s_decimal_0 = Decimal(0.)
s_decimal_1 = Decimal(1.)

np.set_printoptions(formatter={'float': '{: 0.6f}'.format}, edgeitems=3, linewidth=120)

s_trade_types_to_str = {
    _BBB: "BBB",
    _BBS: "BBS",
    _BSB: "BSB",
    _BSS: "BSS",
    _SBB: "SBB",
    _SBS: "SBS",
    _SSB: "SSB",
    _SSS: "SSS"
}

cdef class TriangularArbitrageCalculator():
    """ This is the class that consolidates the info from the orderbooks and the user's wallets
        to determine the feasability of an arbitrage it receives from the arbitrage triangle
        When a tractible arb is available, this class will tell the main strategy class
        via a function called update_opportunity """

    """ Base value for the target_node currency start value when computing profitability """
    _TEST_TARGET_CURRENCY_AMOUNT = Decimal(100.)
    """ Include transaction fee in profit check """
    _INCLUDE_FEE = True

    @classmethod
    def logger(cls):
        global s_tac_logger
        if s_tac_logger is None:
            s_tac_logger = logging.getLogger(__name__)
        return s_tac_logger

    def __init__(self,
                 target_node: str,
                 left_node: str,
                 right_node: str,
                 primary_market: str,
                 secondary_market: str,
                 tertiary_market: str,
                 primary_trading_pair: str,
                 secondary_trading_pair: str,
                 tertiary_trading_pair: str,
                 min_profitability: Decimal,
                 fee_override: Decimal,
                 arbitrage_ccw: TriangularArbitrage = None,
                 arbitrage_cw: TriangularArbitrage = None,
                 preprocessor: OrderBookPreprocessor = None,
                 ):
        self._name = "triangular arbitrage calculator"
        self._target_node = target_node
        self._left_node = left_node
        self._right_node = right_node
        self._primary_market = primary_market
        self._secondary_market = secondary_market
        self._tertiary_market = tertiary_market
        self._primary_trading_pair = primary_trading_pair
        self._secondary_trading_pair = secondary_trading_pair
        self._tertiary_trading_pair = tertiary_trading_pair
        self._min_profitability = min_profitability
        self._ccw_arb = arbitrage_ccw
        self._cw_arb = arbitrage_cw
        self._optimizer = Optimizer()
        self._preprocessor: OrderBookPreprocessor = preprocessor
        self._fees = fee_override

    cdef object c_check_profit(self, TriangularArbitrage arb, list market_pairs):
        start_val = self._TEST_TARGET_CURRENCY_AMOUNT
        final_val = s_decimal_0
        if arb.direction == TradeDirection.CClockwise:
            edge = arb.left_edge
            left_val = start_val/edge.price if edge.trade_type == TradeType.BUY else start_val*edge.price
            if self._INCLUDE_FEE:
                if edge.fee <= s_decimal_0:
                    edge.fee = market_pairs[edge.market_id].market.get_fee(
                        market_pairs[edge.market_id].base_asset, market_pairs[edge.market_id].quote_asset,
                        OrderType.LIMIT, edge.trade_type, edge.price, start_val).percent
                left_val *= s_decimal_1 - edge.fee
            edge = arb.cross_edge
            cross_val = left_val/edge.price if edge.trade_type == TradeType.BUY else left_val*edge.price
            if self._INCLUDE_FEE:
                if edge.fee <= s_decimal_0:
                    edge.fee = market_pairs[edge.market_id].market.get_fee(
                        market_pairs[edge.market_id].base_asset, market_pairs[edge.market_id].quote_asset,
                        OrderType.LIMIT, edge.trade_type, edge.price, left_val).percent
                cross_val *= (s_decimal_1 - edge.fee)
            edge = arb.right_edge
            right_val = cross_val/edge.price if edge.trade_type == TradeType.BUY else cross_val*edge.price
            if self._INCLUDE_FEE:
                if edge.fee <= s_decimal_0:
                    edge.fee = market_pairs[edge.market_id].market.get_fee(
                        market_pairs[edge.market_id].base_asset, market_pairs[edge.market_id].quote_asset,
                        OrderType.LIMIT, edge.trade_type, edge.price, cross_val).percent
                right_val *= (s_decimal_1 - edge.fee)

            profit = Decimal((right_val - start_val)/start_val)
        else:
            edge = arb.right_edge
            right_val = start_val/edge.price if edge.trade_type == TradeType.BUY else start_val*edge.price
            if self._INCLUDE_FEE:
                if edge.fee <= s_decimal_0:
                    edge.fee = market_pairs[edge.market_id].market.get_fee(
                        market_pairs[edge.market_id].base_asset, market_pairs[edge.market_id].quote_asset,
                        OrderType.LIMIT, edge.trade_type, edge.price, start_val).percent
                right_val *= (s_decimal_1 - edge.fee)
            edge = arb.cross_edge
            cross_val = right_val/edge.price if edge.trade_type == TradeType.BUY else right_val*edge.price
            if self._INCLUDE_FEE:
                if edge.fee <= s_decimal_0:
                    edge.fee = market_pairs[edge.market_id].market.get_fee(
                        market_pairs[edge.market_id].base_asset, market_pairs[edge.market_id].quote_asset,
                        OrderType.LIMIT, edge.trade_type, edge.price, right_val).percent
                cross_val *= (s_decimal_1 - edge.fee)
            edge = arb.left_edge
            left_val = cross_val/edge.price if edge.trade_type == TradeType.BUY else cross_val*edge.price
            if self._INCLUDE_FEE:
                if edge.fee <= s_decimal_0:
                    edge.fee = market_pairs[edge.market_id].market.get_fee(
                        market_pairs[edge.market_id].base_asset, market_pairs[edge.market_id].quote_asset,
                        OrderType.LIMIT, edge.trade_type, edge.price, cross_val).percent
                left_val *= (s_decimal_1 - edge.fee)

            profit = Decimal((left_val - start_val)/start_val)

        return profit

    def get_model_orders(self,
                         pri_book_rows: np.ndarray,
                         sec_book_rows: np.ndarray,
                         ter_book_rows: np.ndarray,
                         optimized_amounts: np.ndarray,
                         trade_direction: TradeDirection,
                         trade_types: tuple,
                         trading_pairs: tuple
                         ) -> Optional[Opportunity]:
        """ Generate orders from price and amount arrays
        """
        opportunity = None
        try:
            # first leg
            market_id = 0 if trade_direction == TradeDirection.CClockwise else 2

            amount_1 = Decimal('0')
            price_1 = Decimal('0')
            for i in range(0, len(pri_book_rows)):
                current_amount = optimized_amounts[i]
                if current_amount > 0:
                    amount_1 += Decimal(str(current_amount))
                    price_1 = Decimal(str(pri_book_rows[i].price))

            pri_order = ModelOrder(market_id=market_id, trading_pair=trading_pairs[0], trade_type=trade_types[0],
                                   price=price_1, amount=amount_1)

            # second leg
            amount_2 = Decimal('0')
            price_2 = Decimal('0')
            displacement = len(pri_book_rows)
            for i in range(0, len(sec_book_rows)):
                current_amount = optimized_amounts[i + displacement]
                if current_amount > 0:
                    amount_2 += Decimal(str(current_amount))
                    price_2 = Decimal(str(sec_book_rows[i].price))
            sec_order = ModelOrder(market_id=1, trading_pair=trading_pairs[1], trade_type=trade_types[1],
                                   price=price_2, amount=amount_2)

            # third leg
            market_id = 2 if trade_direction == TradeDirection.CClockwise else 0
            amount_3 = Decimal('0')
            price_3 = Decimal('0')
            displacement = len(pri_book_rows) + len(sec_book_rows)
            for i in range(0, len(ter_book_rows)):
                current_amount = optimized_amounts[i + displacement]
                if current_amount > 0:
                    amount_3 += Decimal(str(current_amount))
                    price_3 = Decimal(str(ter_book_rows[i].price))
            ter_order = ModelOrder(market_id=market_id, trading_pair=trading_pairs[2], trade_type=trade_types[2],
                                   price=price_3, amount=amount_3)

            if any([price_1 == Decimal('0'), price_2 == Decimal('0'), price_3 == Decimal('0')]):
                opportunity = Opportunity(orders=[pri_order, sec_order, ter_order], direction=trade_direction, execute=False)
            else:
                opportunity = Opportunity(orders=[pri_order, sec_order, ter_order], direction=trade_direction, execute=True)

            self.logger().info(f"get_model_orders opportunity:\n{opportunity}")
        except Exception as e:
            self.logger().info(f"get_model_orders error: {e}")

        return opportunity

    def get_order_list(self,
                       first_mkt_info: MarketTradingPairTuple,
                       second_mkt_info: MarketTradingPairTuple,
                       third_mkt_info: MarketTradingPairTuple,
                       first_mkt_bal: Decimal,
                       second_mkt_bal: Decimal,
                       third_mkt_bal: Decimal,
                       trade_direction: TradeDirection,
                       optimize: bool = True
                       ) -> Optional[Opportunity]:
        """ Generate opportunity order list, will return a fallback order list using initial order sizes if
            optimize is enabled and did not yield optimized amounts
        """

        opportunity = None
        trade_types = self._ccw_arb.trade_types if trade_direction == TradeDirection.CClockwise else self._cw_arb.trade_types
        trading_pairs = self._ccw_arb.trading_pairs if trade_direction == TradeDirection.CClockwise else self._cw_arb.trading_pairs

        first_model_book = ModelBook(list(first_mkt_info.order_book_bid_entries()), list(first_mkt_info.order_book_ask_entries()))
        second_model_book = ModelBook(list(second_mkt_info.order_book_bid_entries()), list(second_mkt_info.order_book_ask_entries()))
        third_model_book = ModelBook(list(third_mkt_info.order_book_bid_entries()), list(third_mkt_info.order_book_ask_entries()))

        # TODO this is an expedient for low balances. Find a better solution
        wallets = [first_mkt_bal * Decimal('0.99'), second_mkt_bal * Decimal('0.99'), third_mkt_bal * Decimal('0.99')]

        if trade_direction == TradeDirection.CClockwise:
            (first_order_list, second_order_list, third_order_list) = self._preprocessor.preprocess_cclockwise(
                first_model_book,
                second_model_book,
                third_model_book,
                wallets,
                self._fees
            )
        else:
            (first_order_list, second_order_list, third_order_list) = self._preprocessor.preprocess_clockwise(
                first_model_book,
                second_model_book,
                third_model_book,
                wallets,
                self._fees
            )

        try:
            optimized_order_amounts, opt_val = self._optimizer.optimize(
                s_trade_types_to_str[trade_types],
                first_order_list, second_order_list, third_order_list,
                self._fees)
            orig_amount = sum([float(order.amount) for order in first_order_list])
            gain = opt_val / orig_amount

            if optimized_order_amounts is not None and (gain > float(self._min_profitability)):
                opportunity = self.get_model_orders(first_order_list, second_order_list, third_order_list,
                                                    optimized_order_amounts, trade_direction, trade_types, trading_pairs)
            else:
                return None
        except Exception as e:
            self.logger().error(f"get_order_list direction: {trade_direction} error: {e}")

        return opportunity

    cdef object c_calculate_arbitrage(self, list market_pairs):
        """ Calculate implied cross rate in counter clockwise direction
            but checks profit on both directions.
            By convention: pri_mkt = left_edge_mkt, sec_mkt = cross_edge_mkt, and ter_mkt = right_edge_mkt
        """
        opportunity = [None]
        pri_mkt_info: MarketTradingPairTuple = market_pairs[0]
        sec_mkt_info: MarketTradingPairTuple = market_pairs[1]
        ter_mkt_info: MarketTradingPairTuple = market_pairs[2]

        # Balances as limits
        pri_mkt_bal_base = pri_mkt_info.market.get_available_balance(pri_mkt_info.base_asset)
        pri_mkt_bal_quote = pri_mkt_info.market.get_available_balance(pri_mkt_info.quote_asset)
        sec_mkt_bal_base = sec_mkt_info.market.get_available_balance(sec_mkt_info.base_asset)
        sec_mkt_bal_quote = sec_mkt_info.market.get_available_balance(sec_mkt_info.quote_asset)
        ter_mkt_bal_base = ter_mkt_info.market.get_available_balance(ter_mkt_info.base_asset)
        ter_mkt_bal_quote = ter_mkt_info.market.get_available_balance(ter_mkt_info.quote_asset)

        # Prices
        pri_best_bid_price = pri_mkt_info.get_price(is_buy=True)
        pri_best_ask_price = pri_mkt_info.get_price(is_buy=False)
        sec_best_bid_price = sec_mkt_info.get_price(is_buy=True)
        sec_best_ask_price = sec_mkt_info.get_price(is_buy=False)
        ter_best_bid_price = ter_mkt_info.get_price(is_buy=True)
        ter_best_ask_price = ter_mkt_info.get_price(is_buy=False)

        """ Check if any arbitrage is present """
        implied_cross_rate_bid, arbitrage, a_b, c_a = s_decimal_0, s_decimal_0, s_decimal_0, s_decimal_0
        if self._ccw_arb.cross_edge.trade_type == TradeType.SELL:
            """
                    a
                    ^
                  /   \
                 /     \
               a/b     c/a
              sell     sell
              /            \
             /              \
            b----b/c SELL---->c

            (b/c)_bid = (1/(a/b)_ask * (1/(c/a)_ask

            Trade sequence cases:
            1. Sell -> SELL -> Sell
                (1/(a/b)_ask) * (1/(c/a)_ask
            2, Buy -> SELL -> Sell
                (b/a)_bid * (1/(c/a)_ask
            3. Sell -> SELL -> Buy
                (1/(a/b)_ask) * (a/c)_bid
            4. Buy -> SELL -> Buy
                (b/a)_bid * (a/c)_bid
            """
            if self._ccw_arb.left_edge.trade_type == TradeType.SELL:
                a_b = s_decimal_1/pri_best_ask_price
            else:
                a_b = pri_best_bid_price

            if self._ccw_arb.right_edge.trade_type == TradeType.SELL:
                c_a = s_decimal_1/ter_best_ask_price
            else:
                c_a = ter_best_bid_price

        else:  # cross edge trade type is BUY
            """
                    a
                    ^
                  /   \
                 /     \
               a/b     c/a
              sell     sell
              /            \
             /              \
            b----c/b BUY---->c

            (c/b)_bid = (a/b)_bid * (c/a)_bid

            Trade sequence cases:
            1. Sell -> BUY -> Sell
                (a/b)_bid * (c/a)_bid
            2. Buy -> BUY -> Sell
                (1./(b/a)_ask) * (c/a)_bid
            3. Sell -> BUY -> Buy
                (a/b)_bid * (1/(a/c)_ask)
            4. Buy -> BUY -> Buy
                (1/(b/a)_ask) * (1/(a/c)_ask)
            """
            if self._ccw_arb.left_edge.trade_type == TradeType.SELL:
                a_b = pri_best_bid_price
            else:
                a_b = s_decimal_1/pri_best_ask_price

            if self._ccw_arb.right_edge.trade_type == TradeType.SELL:
                c_a = ter_best_bid_price
            else:
                c_a = s_decimal_1/ter_best_ask_price

        implied_cross_rate_bid = a_b * c_a
        arbitrage = (sec_best_bid_price - implied_cross_rate_bid)/sec_best_bid_price

        """ Check arbitrage if profitable in either trade directions """
        ccw_profit, cw_profit = s_decimal_0, s_decimal_0
        if arbitrage != s_decimal_0:
            edge = self._ccw_arb.left_edge
            edge.price = pri_best_ask_price if edge.trade_type == TradeType.BUY else pri_best_bid_price

            edge = self._ccw_arb.cross_edge
            edge.price = sec_best_ask_price if edge.trade_type == TradeType.BUY else sec_best_bid_price

            edge = self._ccw_arb.right_edge
            edge.price = ter_best_ask_price if edge.trade_type == TradeType.BUY else ter_best_bid_price

            ccw_profit = self.c_check_profit(self._ccw_arb, market_pairs)

            # if ccw_profit <= s_decimal_0:
            edge = self._cw_arb.right_edge
            edge.price = ter_best_ask_price if edge.trade_type == TradeType.BUY else ter_best_bid_price

            edge = self._cw_arb.cross_edge
            edge.price = sec_best_ask_price if edge.trade_type == TradeType.BUY else sec_best_bid_price

            edge =self._cw_arb.left_edge
            edge.price = pri_best_ask_price if edge.trade_type == TradeType.BUY else pri_best_bid_price

            cw_profit = self.c_check_profit(self._cw_arb, market_pairs)

        """ Select which direction to trade """
        if ccw_profit > s_decimal_0 and ccw_profit > cw_profit:
            # execute = True if ccw_profit > self._min_profitability else False
            execute = False
            first_mkt_bal = pri_mkt_bal_base if self._ccw_arb.left_edge.trade_type == TradeType.SELL else pri_mkt_bal_quote
            second_mkt_bal = sec_mkt_bal_base if self._ccw_arb.cross_edge.trade_type == TradeType.SELL else sec_mkt_bal_quote
            third_mkt_bal = ter_mkt_bal_base if self._ccw_arb.right_edge.trade_type == TradeType.SELL else ter_mkt_bal_quote

            opportunity = [self.get_order_list(
                pri_mkt_info, sec_mkt_info, ter_mkt_info,
                first_mkt_bal, second_mkt_bal, third_mkt_bal,
                TradeDirection.CClockwise, optimize=True)]
        elif cw_profit > s_decimal_0 and cw_profit > ccw_profit:
            # execute = True if cw_profit > self._min_profitability else False
            execute = False
            first_mkt_bal = ter_mkt_bal_quote if self._ccw_arb.right_edge.trade_type == TradeType.SELL else pri_mkt_bal_base
            second_mkt_bal = sec_mkt_bal_quote if self._ccw_arb.cross_edge.trade_type == TradeType.SELL else sec_mkt_bal_base
            third_mkt_bal = pri_mkt_bal_quote if self._ccw_arb.left_edge.trade_type == TradeType.SELL else ter_mkt_bal_base

            opportunity = [self.get_order_list(
                ter_mkt_info, sec_mkt_info, pri_mkt_info,
                first_mkt_bal, second_mkt_bal, third_mkt_bal,
                TradeDirection.Clockwise, optimize=True)]
        if opportunity == [None]:
            pri_order = ModelOrder(market_id=0, trading_pair=self._ccw_arb.left_edge.trading_pair,
                                   trade_type=self._ccw_arb.left_edge.trade_type, price=self._ccw_arb.left_edge.price, amount=Decimal('0'))
            sec_order = ModelOrder(market_id=0, trading_pair=self._ccw_arb.cross_edge.trading_pair,
                                   trade_type=self._ccw_arb.cross_edge.trade_type, price=self._ccw_arb.cross_edge.price, amount=Decimal('0'))
            ter_order = ModelOrder(market_id=0, trading_pair=self._ccw_arb.right_edge.trading_pair,
                                   trade_type=self._ccw_arb.right_edge.trade_type, price=self._ccw_arb.right_edge.price, amount=Decimal('0'))

            opportunity_1 = Opportunity(orders=[pri_order, sec_order, ter_order], direction=TradeDirection.CClockwise, execute=False)

            pri_order = ModelOrder(market_id=0, trading_pair=self._cw_arb.right_edge.trading_pair,
                                   trade_type=self._cw_arb.right_edge.trade_type, price=self._cw_arb.right_edge.price, amount=Decimal('0'))
            sec_order = ModelOrder(market_id=0, trading_pair=self._cw_arb.cross_edge.trading_pair,
                                   trade_type=self._cw_arb.cross_edge.trade_type, price=self._cw_arb.cross_edge.price, amount=Decimal('0'))
            ter_order = ModelOrder(market_id=0, trading_pair=self._cw_arb.left_edge.trading_pair,
                                   trade_type=self._cw_arb.left_edge.trade_type, price=self._cw_arb.left_edge.price, amount=Decimal('0'))

            opportunity_2 = Opportunity(orders=[pri_order, sec_order, ter_order], direction=TradeDirection.Clockwise, execute=False)

            # For the purpose of status update
            opportunity = [opportunity_1, opportunity_2]

        return opportunity

    def update_opportunity(self, market_pairs: List[MarketTradingPairTuple]):
        opportunity = None
        try:
            opportunity = self.c_calculate_arbitrage(market_pairs)
        except Exception as e:
            self.logger().warn(f"update_opportunity error: {e}")

        return opportunity
