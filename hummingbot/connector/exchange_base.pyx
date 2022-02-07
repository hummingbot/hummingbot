from decimal import Decimal
from typing import Dict, List, Optional, Iterator

from hummingbot.connector.budget_checker import BudgetChecker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book_query_result import OrderBookQueryResult, ClientOrderBookQueryResult
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import OrderType, TradeType, PriceType

NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


cdef class ExchangeBase(ConnectorBase):
    """
    ExchangeBase provides common exchange (for both centralized and decentralized) connector functionality and
    interface.
    """

    def __init__(self):
        super().__init__()
        self._order_book_tracker = None
        self._budget_checker = BudgetChecker(exchange=self)

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
        return exchange_trading_pair

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        return hb_trading_pair

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        raise NotImplementedError

    @property
    def limit_orders(self) -> List[LimitOrder]:
        raise NotImplementedError

    @property
    def budget_checker(self) -> BudgetChecker:
        return self._budget_checker

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return (self.get_price(trading_pair, True) + self.get_price(trading_pair, False)) / Decimal("2")

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN, dict kwargs={}):
        return self.buy(trading_pair, amount, order_type, price, **kwargs)

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN, dict kwargs={}):
        return self.sell(trading_pair, amount, order_type, price, **kwargs)

    cdef c_cancel(self, str trading_pair, str client_order_id):
        return self.cancel(trading_pair, client_order_id)

    cdef c_stop_tracking_order(self, str order_id):
        raise NotImplementedError

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price,
                          object is_maker = None):
        return self.get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    cdef OrderBook c_get_order_book(self, str trading_pair):
        return self.get_order_book(trading_pair)

    cdef object c_get_price(self, str trading_pair, bint is_buy):
        """
        :returns: Top bid/ask price for a specific trading pair
        """
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            object top_price
        try:
            top_price = Decimal(order_book.c_get_price(is_buy))
        except EnvironmentError as e:
            self.logger().warning(f"{'Ask' if is_buy else 'Bid'} orderbook for {trading_pair} is empty.")
            return s_decimal_NaN

        return self.c_quantize_order_price(trading_pair, top_price)

    cdef ClientOrderBookQueryResult c_get_vwap_for_volume(self, str trading_pair, bint is_buy, object volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_vwap_for_volume(is_buy, float(volume))
            object query_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.query_volume))
            object result_price = self.c_quantize_order_price(trading_pair, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_price_for_quote_volume(self, str trading_pair, bint is_buy, double volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_price_for_quote_volume(is_buy, float(volume))
            object query_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.query_volume))
            object result_price = self.c_quantize_order_price(trading_pair, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_price_for_volume(self, str trading_pair, bint is_buy, object volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_price_for_volume(is_buy, float(volume))
            object query_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.query_volume))
            object result_price = self.c_quantize_order_price(trading_pair, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_quote_volume_for_base_amount(self, str trading_pair, bint is_buy,
                                                                       object base_amount):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_quote_volume_for_base_amount(is_buy, float(base_amount))
            object query_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.query_volume))
            object result_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          s_decimal_NaN,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_volume_for_price(self, str trading_pair, bint is_buy, object price):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_volume_for_price(is_buy, float(price))
            object query_price = self.c_quantize_order_price(trading_pair, Decimal(result.query_price))
            object result_price = self.c_quantize_order_price(trading_pair, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(query_price,
                                          s_decimal_NaN,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_quote_volume_for_price(self, str trading_pair, bint is_buy, object price):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_volume_for_price(is_buy, float(price))
            object query_price = self.c_quantize_order_price(trading_pair, Decimal(result.query_price))
            object result_price = self.c_quantize_order_price(trading_pair, Decimal(result.result_price))
            object result_volume = self.c_quantize_order_amount(trading_pair, Decimal(result.result_volume))
        return ClientOrderBookQueryResult(query_price,
                                          s_decimal_NaN,
                                          result_price,
                                          result_volume)

    def order_book_bid_entries(self, trading_pair) -> Iterator[ClientOrderBookRow]:
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
        for entry in order_book.bid_entries():
            yield ClientOrderBookRow(self.c_quantize_order_price(trading_pair, Decimal(entry.price)),
                                     self.c_quantize_order_amount(trading_pair, Decimal(entry.amount)),
                                     entry.update_id)

    def order_book_ask_entries(self, trading_pair) -> Iterator[ClientOrderBookRow]:
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
        for entry in order_book.ask_entries():
            yield ClientOrderBookRow(self.c_quantize_order_price(trading_pair, Decimal(entry.price)),
                                     self.c_quantize_order_amount(trading_pair, Decimal(entry.amount)),
                                     entry.update_id)

    def get_vwap_for_volume(self, trading_pair: str, is_buy: bool, volume: Decimal):
        return self.c_get_vwap_for_volume(trading_pair, is_buy, volume)

    def get_price_for_volume(self, trading_pair: str, is_buy: bool, volume: Decimal):
        return self.c_get_price_for_volume(trading_pair, is_buy, volume)

    def get_quote_volume_for_base_amount(self, trading_pair: str, is_buy: bool,
                                         base_amount: Decimal) -> ClientOrderBookQueryResult:
        return self.c_get_quote_volume_for_base_amount(trading_pair, is_buy, base_amount)

    def get_volume_for_price(self, trading_pair: str, is_buy: bool, price: Decimal) -> ClientOrderBookQueryResult:
        return self.c_get_volume_for_price(trading_pair, is_buy, price)

    def get_quote_volume_for_price(self, trading_pair: str, is_buy: bool, price: Decimal) -> ClientOrderBookQueryResult:
        return self.c_get_quote_volume_for_price(trading_pair, is_buy, price)

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        raise NotImplementedError

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        raise NotImplementedError

    def cancel(self, trading_pair: str, client_order_id: str):
        raise NotImplementedError

    def get_order_book(self, trading_pair: str) -> OrderBook:
        raise NotImplementedError

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        raise NotImplementedError

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return self.c_get_order_price_quantum(trading_pair, price)

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return self.c_get_order_size_quantum(trading_pair, order_size)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        return self.c_quantize_order_price(trading_pair, price)

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        return self.c_quantize_order_amount(trading_pair, amount)

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    def get_maker_order_type(self):
        """
        Return a maker order type depending what order types the connector supports.
        """
        if OrderType.LIMIT_MAKER in self.supported_order_types():
            return OrderType.LIMIT_MAKER
        elif OrderType.LIMIT in self.supported_order_types():
            return OrderType.LIMIT
        else:
            raise Exception("There is no maker order type supported by this exchange.")

    def get_taker_order_type(self):
        """
        Return a taker order type depending what order types the connector supports.
        """
        if OrderType.MARKET in self.supported_order_types():
            return OrderType.MARKET
        elif OrderType.LIMIT in self.supported_order_types():
            return OrderType.LIMIT
        else:
            raise Exception("There is no taker order type supported by this exchange.")

    def get_price_by_type(self, trading_pair: str, price_type: PriceType) -> Decimal:
        """
        Gets price by type (BestBid, BestAsk, MidPrice or LastTrade)
        :param trading_pair: The market trading pair
        :param price_type: The price type
        :returns The price
        """
        if price_type is PriceType.BestBid:
            return self.c_get_price(trading_pair, False)
        elif price_type is PriceType.BestAsk:
            return self.c_get_price(trading_pair, True)
        elif price_type is PriceType.MidPrice:
            return (self.c_get_price(trading_pair, True) + self.c_get_price(trading_pair, False)) / Decimal("2")
        elif price_type is PriceType.LastTrade:
            return Decimal(self.c_get_order_book(trading_pair).last_trade_price)

    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        For an exchange type connector, the quote price is volume weighted average price.
        """
        return Decimal(str(self.get_vwap_for_volume(trading_pair, is_buy, amount).result_price))

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        For an exchange type connector, the price required for order submission is the price of the order book for
        required volume.
        """
        return Decimal(str(self.get_price_for_volume(trading_pair, is_buy, amount).result_price))
