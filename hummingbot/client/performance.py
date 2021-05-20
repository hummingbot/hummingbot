from decimal import Decimal
from dataclasses import dataclass
from typing import (
    Dict,
    Optional,
    List,
    Any
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.core.utils.market_price import get_last_price

s_decimal_0 = Decimal("0")
s_decimal_nan = Decimal("NaN")


@dataclass
class PerformanceMetrics:
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
        self.fees: Dict[str, Decimal] = {}


def position_order(open: list, close: list):
    """
    Pair open position order with close position orders
    :param open: a list of orders that may have an open position order
    :param close: a list of orders that may have an close position order
    :return: A tuple containing a pair of an open order with a close position order
    """
    for o in open:
        for c in close:
            if o.position == "OPEN" and c.position == "CLOSE":
                open.remove(o)
                close.remove(c)
                return (o, c)
    return None


def aggregate_position_order(buys: list, sells: list):
    """
    Aggregate the amount field for orders with multiple fills
    :param buys: a list of buy orders
    :param sells: a list of sell orders
    :return: 2 lists containing aggregated amounts for buy and sell orders.
    """
    aggregated_buys = []
    aggregated_sells = []
    for buy in buys:
        if buy.order_id not in [ag.order_id for ag in aggregated_buys]:
            aggregate_price = [b.price for b in buys if b.order_id == buy.order_id]
            aggregate_amount = [b.amount for b in buys if b.order_id == buy.order_id]
            buy.price = sum(aggregate_price) / len(aggregate_price)
            buy.amount = sum(aggregate_amount)
            aggregated_buys.append(buy)

    for sell in sells:
        if sell.order_id not in [ag.order_id for ag in aggregated_sells]:
            aggregate_price = [s.price for s in sells if s.order_id == sell.order_id]
            aggregate_amount = [s.amount for s in sells if s.order_id == sell.order_id]
            sell.price = sum(aggregate_price) / len(aggregate_price)
            sell.amount = sum(aggregate_amount)
            aggregated_sells.append(sell)

    return aggregated_buys, aggregated_sells


def derivative_pnl(long: list, short: list):
    # It is assumed that the amount and leverage for both open and close orders are thesame.
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


async def calculate_performance_metrics(exchange: str,
                                        trading_pair: str,
                                        trades: List[Any],
                                        current_balances: Dict[str, Decimal]) -> PerformanceMetrics:
    """
    Calculates PnL, fees, Return % and etc...
    :param exchange: the exchange or connector name
    :param trading_pair: the trading market to get performance metrics
    :param trades: the list of TradeFill or Trade object
    :param current_balances: current user account balance
    :return: A PerformanceMetrics object
    """

    def divide(value, divisor):
        value = Decimal(str(value))
        divisor = Decimal(str(divisor))
        if divisor == s_decimal_0:
            return s_decimal_0
        return value / divisor

    base, quote = trading_pair.split("-")
    perf = PerformanceMetrics()
    buys = [t for t in trades if t.trade_type.upper() == "BUY"]
    sells = [t for t in trades if t.trade_type.upper() == "SELL"]
    derivative = False
    if trades and type(trades[0]) == TradeFill and "NILL" not in [t.position for t in trades]:
        derivative = True
    perf.num_buys = len(buys)
    perf.num_sells = len(sells)
    perf.num_trades = perf.num_buys + perf.num_sells

    perf.b_vol_base = Decimal(str(sum(b.amount for b in buys)))
    perf.s_vol_base = Decimal(str(sum(s.amount for s in sells))) * Decimal("-1")
    perf.tot_vol_base = perf.b_vol_base + perf.s_vol_base

    perf.b_vol_quote = Decimal(str(sum(b.amount * b.price for b in buys))) * Decimal("-1")
    perf.s_vol_quote = Decimal(str(sum(s.amount * s.price for s in sells)))
    perf.tot_vol_quote = perf.b_vol_quote + perf.s_vol_quote

    perf.avg_b_price = divide(perf.b_vol_quote, perf.b_vol_base)
    perf.avg_s_price = divide(perf.s_vol_quote, perf.s_vol_base)
    perf.avg_tot_price = divide(abs(perf.b_vol_quote) + abs(perf.s_vol_quote),
                                abs(perf.b_vol_base) + abs(perf.s_vol_base))
    perf.avg_b_price = abs(perf.avg_b_price)
    perf.avg_s_price = abs(perf.avg_s_price)

    perf.cur_base_bal = current_balances.get(base, 0)
    perf.cur_quote_bal = current_balances.get(quote, 0)
    perf.start_base_bal = perf.cur_base_bal - perf.tot_vol_base
    perf.start_quote_bal = perf.cur_quote_bal - perf.tot_vol_quote

    perf.start_price = Decimal(str(trades[0].price))
    perf.cur_price = await get_last_price(exchange.replace("_PaperTrade", ""), trading_pair)
    if perf.cur_price is None:
        perf.cur_price = Decimal(str(trades[-1].price))
    perf.start_base_ratio_pct = divide(perf.start_base_bal * perf.start_price,
                                       (perf.start_base_bal * perf.start_price) + perf.start_quote_bal)
    perf.cur_base_ratio_pct = divide(perf.cur_base_bal * perf.cur_price,
                                     (perf.cur_base_bal * perf.cur_price) + perf.cur_quote_bal)

    perf.hold_value = (perf.start_base_bal * perf.cur_price) + perf.start_quote_bal
    perf.cur_value = (perf.cur_base_bal * perf.cur_price) + perf.cur_quote_bal
    perf.trade_pnl = perf.cur_value - perf.hold_value

    # Handle trade_pnl differently for derivatives
    if derivative:
        buys_copy, sells_copy = aggregate_position_order(buys.copy(), sells.copy())
        long = []
        short = []

        while True:
            lng = position_order(buys_copy, sells_copy)
            if lng is not None:
                long.append(lng)

            sht = position_order(sells_copy, buys_copy)
            if sht is not None:
                short.append(sht)
            if lng is None and sht is None:
                break

        perf.trade_pnl = Decimal(str(sum(derivative_pnl(long, short))))

    for trade in trades:
        if type(trade) is TradeFill:
            if trade.trade_fee.get("percent") is not None and trade.trade_fee["percent"] > 0:
                if quote not in perf.fees:
                    perf.fees[quote] = s_decimal_0
                perf.fees[quote] += Decimal(trade.price * trade.amount * trade.trade_fee["percent"])
            for flat_fee in trade.trade_fee.get("flat_fees", []):
                if flat_fee["asset"] not in perf.fees:
                    perf.fees[flat_fee["asset"]] = s_decimal_0
                perf.fees[flat_fee["asset"]] += Decimal(flat_fee["amount"])
        else:  # assume this is Trade object
            if trade.trade_fee.percent > 0:
                if quote not in perf.fees:
                    perf.fees[quote] = s_decimal_0
                perf.fees[quote] += (trade.price * trade.order_amount) * trade.trade_fee.percent
            for flat_fee in trade.trade_fee.flat_fees:
                if flat_fee[0] not in perf.fees:
                    perf.fees[flat_fee[0]] = s_decimal_0
                perf.fees[flat_fee[0]] += flat_fee[1]

    for fee_token, fee_amount in perf.fees.items():
        if fee_token == quote:
            perf.fee_in_quote += fee_amount
        else:
            last_price = await get_last_price(exchange, f"{fee_token}-{quote}")
            if last_price is not None:
                perf.fee_in_quote += fee_amount * last_price

    perf.total_pnl = perf.trade_pnl - perf.fee_in_quote
    perf.return_pct = divide(perf.total_pnl, perf.hold_value)

    return perf


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
