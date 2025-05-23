import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.logger import HummingbotLogger
from hummingbot.model.trade_fill import TradeFill

s_decimal_0 = Decimal("0")
s_decimal_nan = Decimal("NaN")


@dataclass
class PerformanceMetrics:
    _logger = None

    num_buys: int = 0
    num_sells: int = 0
    num_trades: int = 0

    b_vol_base: Decimal = s_decimal_0
    s_vol_base: Decimal = s_decimal_0
    tot_vol_base: Decimal = s_decimal_0

    b_vol_quote: Decimal = s_decimal_0
    s_vol_quote: Decimal = s_decimal_0
    tot_vol_quote: Decimal = s_decimal_0

    avg_b_price: Decimal = s_decimal_0
    avg_s_price: Decimal = s_decimal_0
    avg_tot_price: Decimal = s_decimal_0

    start_base_bal: Decimal = s_decimal_0
    start_quote_bal: Decimal = s_decimal_0
    cur_base_bal: Decimal = s_decimal_0
    cur_quote_bal: Decimal = s_decimal_0
    start_price: Decimal = s_decimal_0
    cur_price: Decimal = s_decimal_0
    start_base_ratio_pct: Decimal = s_decimal_0
    cur_base_ratio_pct: Decimal = s_decimal_0

    hold_value: Decimal = s_decimal_0
    cur_value: Decimal = s_decimal_0
    trade_pnl: Decimal = s_decimal_0

    fee_in_quote: Decimal = s_decimal_0
    total_pnl: Decimal = s_decimal_0
    return_pct: Decimal = s_decimal_0

    def __init__(self):
        # fees is a dictionary of token and total fee amount paid in that token.
        self.fees: Dict[str, Decimal] = defaultdict(lambda: s_decimal_0)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    async def create(cls,
                     trading_pair: str,
                     trades: List[Any],
                     current_balances: Dict[str, Decimal]) -> 'PerformanceMetrics':
        performance = PerformanceMetrics()
        await performance._initialize_metrics(trading_pair, trades, current_balances)
        return performance

    @staticmethod
    def position_order(open: list, close: list) -> Tuple[Any, Any]:
        """
        Pair open position order with close position orders
        :param open: a list of orders that may have an open position order
        :param close: a list of orders that may have an close position order
        :return: A tuple containing a pair of an open order with a close position order
        """
        result = None

        try:
            first_with_open_position = next((order for order in open if order.position == "OPEN"))
            first_with_close_position = next((order for order in close if order.position == "CLOSE"))
            open.remove(first_with_open_position)
            close.remove(first_with_close_position)
            result = (first_with_open_position, first_with_close_position)
        except StopIteration:
            pass

        return result

    @staticmethod
    def aggregate_orders(orders: list) -> list:
        grouped_orders = {}
        for order in orders:
            group = grouped_orders.get(order.order_id, [])
            group.append(order)
            grouped_orders[order.order_id] = group

        aggregated_orders = []
        for group in grouped_orders.values():
            aggregated_prices = 0
            aggregated_amounts = 0
            for order in group:
                aggregated_prices += order.price
                aggregated_amounts += order.amount
            aggregated = group[0]
            aggregated.price = aggregated_prices / len(group)
            aggregated.amount = aggregated_amounts
            aggregated_orders.append(aggregated)

        return aggregated_orders

    @staticmethod
    def aggregate_position_order(buys: list, sells: list) -> Tuple[list, list]:
        """
        Aggregate the amount field for orders with multiple fills
        :param buys: a list of buy orders
        :param sells: a list of sell orders
        :return: 2 lists containing aggregated amounts for buy and sell orders.
        """
        aggregated_buys = PerformanceMetrics.aggregate_orders(buys)
        aggregated_sells = PerformanceMetrics.aggregate_orders(sells)

        return aggregated_buys, aggregated_sells

    @staticmethod
    def derivative_pnl(long: list, short: list) -> List[Decimal]:
        # It is assumed that the amount and leverage for both open and close orders are the same.
        """
        Calculates PnL for a close position
        :param long: a list containing pairs of open and closed long position orders
        :param short: a list containing pairs of open and closed short position orders
        :return: A list containing PnL for each closed positions
        """
        pnls = []
        for lg in long:
            pnls.append((lg[1].price - lg[0].price) * lg[1].amount)
        for st in short:
            pnls.append((st[0].price - st[1].price) * st[1].amount)
        return pnls

    @staticmethod
    def smart_round(value: Decimal, precision: Optional[int] = None) -> Decimal:
        if value is None or value.is_nan():
            return value
        if precision is not None:
            precision = 1 / (10 ** precision)
            return Decimal(str(value)).quantize(Decimal(str(precision)))
        step = Decimal("1")
        if Decimal("10000") > abs(value) > Decimal("100"):
            step = Decimal("0.1")
        elif Decimal("100") > abs(value) > Decimal("1"):
            step = Decimal("0.01")
        elif Decimal("1") > abs(value) > Decimal("0.01"):
            step = Decimal("0.0001")
        elif Decimal("0.01") > abs(value) > Decimal("0.0001"):
            step = Decimal("0.00001")
        elif Decimal("0.0001") > abs(value) > s_decimal_0:
            step = Decimal("0.00000001")
        return (value // step) * step

    @staticmethod
    def divide(value, divisor):
        value = Decimal(str(value))
        divisor = Decimal(str(divisor))
        if divisor == s_decimal_0:
            return s_decimal_0
        return value / divisor

    def _is_trade_fill(self, trade):
        return isinstance(trade, TradeFill)

    def _are_derivatives(self, trades: List[Any]) -> bool:
        return (
            trades
            and self._is_trade_fill(trades[0])
            and PositionAction.NIL.value not in [t.position for t in trades]
        )

    def _preprocess_trades_and_group_by_type(self, trades: List[Any]) -> Tuple[List[Any], List[Any]]:
        buys = []
        sells = []
        for trade in trades:
            if trade.trade_type.upper() == TradeType.BUY.name.upper():
                buys.append(trade)
                self.b_vol_base += Decimal(str(trade.amount))
                self.b_vol_quote += Decimal(str(trade.amount)) * Decimal(str(trade.price)) * Decimal("-1")
            elif trade.trade_type.upper() == TradeType.SELL.name.upper():
                sells.append(trade)
                self.s_vol_base += Decimal(str(trade.amount)) * Decimal("-1")
                self.s_vol_quote += Decimal(str(trade.amount)) * Decimal(str(trade.price))

            self.s_vol_quote += self._process_deducted_fees_impact_in_quote_vol(trade)

        self.tot_vol_base = self.b_vol_base + self.s_vol_base
        self.tot_vol_quote = self.b_vol_quote + self.s_vol_quote

        self.avg_b_price = self.divide(self.b_vol_quote, self.b_vol_base)
        self.avg_s_price = self.divide(self.s_vol_quote, self.s_vol_base)
        self.avg_tot_price = self.divide(abs(self.b_vol_quote) + abs(self.s_vol_quote),
                                         abs(self.b_vol_base) + abs(self.s_vol_base))
        self.avg_b_price = abs(self.avg_b_price)
        self.avg_s_price = abs(self.avg_s_price)

        return buys, sells

    def _process_deducted_fees_impact_in_quote_vol(self, trade):
        fee_percent = None
        fee_type = ""
        impact = s_decimal_0
        if self._is_trade_fill(trade):
            if trade.trade_fee.get("percent") is not None:
                fee_percent = Decimal(trade.trade_fee.get("percent"))
                fee_type = trade.trade_fee.get("fee_type")
        else:  # assume this is Trade object
            if trade.trade_fee.percent is not None:
                fee_percent = Decimal(trade.trade_fee.percent)
                fee_type = trade.trade_fee.type_descriptor_for_json()
        if (fee_percent is not None) and (fee_type == DeductedFromReturnsTradeFee.type_descriptor_for_json()):
            impact = Decimal(str(trade.amount)) * Decimal(str(trade.price)) * fee_percent * Decimal("-1")
        return impact

    async def _calculate_fees(self, quote: str, trades: List[Any]):
        for trade in trades:
            fee_percent = None
            trade_price = None
            trade_amount = None
            if self._is_trade_fill(trade):
                if trade.trade_fee.get("percent") is not None:
                    trade_price = Decimal(str(trade.price))
                    trade_amount = Decimal(str(trade.amount))
                    fee_percent = Decimal(str(trade.trade_fee["percent"]))
                flat_fees = [TokenAmount(token=flat_fee["token"], amount=Decimal(flat_fee["amount"]))
                             for flat_fee in trade.trade_fee.get("flat_fees", [])]
            else:  # assume this is Trade object
                if trade.trade_fee.percent is not None:
                    trade_price = Decimal(trade.price)
                    trade_amount = Decimal(trade.amount)
                    fee_percent = Decimal(trade.trade_fee.percent)
                flat_fees = trade.trade_fee.flat_fees

            if fee_percent is not None:
                self.fees[quote] += trade_price * trade_amount * fee_percent
            for flat_fee in flat_fees:
                self.fees[flat_fee.token] += flat_fee.amount

        for fee_token, fee_amount in self.fees.items():
            if fee_token == quote:
                self.fee_in_quote += fee_amount
            else:
                rate_pair: str = combine_to_hb_trading_pair(fee_token, quote)
                last_price = await RateOracle.get_instance().stored_or_live_rate(rate_pair)
                if last_price is not None:
                    self.fee_in_quote += fee_amount * last_price
                else:
                    self.logger().warning(
                        f"Could not find exchange rate for {rate_pair} "
                        f"using {RateOracle.get_instance()}. PNL value will be inconsistent."
                    )

    def _calculate_trade_pnl(self, buys: list, sells: list):
        self.trade_pnl = self.cur_value - self.hold_value

        # Handle trade_pnl differently for derivatives
        if self._are_derivatives(buys) or self._are_derivatives(sells):
            buys_copy, sells_copy = self.aggregate_position_order(buys.copy(), sells.copy())
            long = []
            short = []

            while True:
                lng = self.position_order(buys_copy, sells_copy)
                if lng is not None:
                    long.append(lng)

                sht = self.position_order(sells_copy, buys_copy)
                if sht is not None:
                    short.append(sht)
                if lng is None and sht is None:
                    break

            self.trade_pnl = Decimal(str(sum(self.derivative_pnl(long, short))))

    async def _initialize_metrics(self,
                                  trading_pair: str,
                                  trades: List[Any],
                                  current_balances: Dict[str, Decimal]):
        """
        Calculates PnL, fees, Return % and etc...
        :param trading_pair: the trading market to get performance metrics
        :param trades: the list of TradeFill or Trade object
        :param current_balances: current user account balance
        """

        base, quote = split_hb_trading_pair(trading_pair)
        buys, sells = self._preprocess_trades_and_group_by_type(trades)

        self.num_buys = len(buys)
        self.num_sells = len(sells)
        self.num_trades = self.num_buys + self.num_sells

        self.cur_base_bal = current_balances.get(base, s_decimal_0)
        self.cur_quote_bal = current_balances.get(quote, s_decimal_0)
        self.start_base_bal = self.cur_base_bal - self.tot_vol_base
        self.start_quote_bal = self.cur_quote_bal - self.tot_vol_quote

        self.start_price = Decimal(str(trades[0].price))
        self.cur_price = await RateOracle.get_instance().stored_or_live_rate(trading_pair)
        if self.cur_price is None:
            self.cur_price = Decimal(str(trades[-1].price))
        self.start_base_ratio_pct = self.divide(self.start_base_bal * self.start_price,
                                                (self.start_base_bal * self.start_price) + self.start_quote_bal)
        self.cur_base_ratio_pct = self.divide(self.cur_base_bal * self.cur_price,
                                              (self.cur_base_bal * self.cur_price) + self.cur_quote_bal)

        self.hold_value = (self.start_base_bal * self.cur_price) + self.start_quote_bal
        self.cur_value = (self.cur_base_bal * self.cur_price) + self.cur_quote_bal
        self._calculate_trade_pnl(buys, sells)

        await self._calculate_fees(quote, trades)

        self.total_pnl = self.trade_pnl - self.fee_in_quote
        self.return_pct = self.divide(self.total_pnl, self.hold_value)
