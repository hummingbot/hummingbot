import asyncio
from decimal import Decimal
from typing import Dict, List, Iterator, Mapping, Optional, TYPE_CHECKING

from bidict import bidict

from hummingbot.connector.budget_checker import BudgetChecker
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_query_result import ClientOrderBookQueryResult, OrderBookQueryResult
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.utils.async_utils import safe_gather

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_float_NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


cdef class ExchangeBase(ConnectorBase):
    """
    ExchangeBase provides common exchange (for both centralized and decentralized) connector functionality and
    interface.
    """

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map)
        self._order_book_tracker = None
        self._budget_checker = BudgetChecker(exchange=self)
        self._trading_pair_symbol_map: Optional[Mapping[str, str]] = None
        self._mapping_initialization_lock = asyncio.Lock()

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

    @property
    def order_book_tracker(self) -> Optional[OrderBookTracker]:
        return self._order_book_tracker

    async def trading_pair_symbol_map(self):
        if not self.trading_pair_symbol_map_ready():
            async with self._mapping_initialization_lock:
                if not self.trading_pair_symbol_map_ready():
                    await self._initialize_trading_pair_symbol_map()
        current_map = self._trading_pair_symbol_map or bidict()
        return current_map

    def trading_pair_symbol_map_ready(self):
        """
        Checks if the mapping from exchange symbols to client trading pairs has been initialized

        :return: True if the mapping has been initialized, False otherwise
        """
        return self._trading_pair_symbol_map is not None and len(self._trading_pair_symbol_map) > 0

    async def all_trading_pairs(self) -> List[str]:
        """
        List of all trading pairs supported by the connector

        :return: List of trading pair symbols in the Hummingbot format
        """
        mapping = await self.trading_pair_symbol_map()
        return list(mapping.values())

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        """
        Used to translate a trading pair from the client notation to the exchange notation

        :param trading_pair: trading pair in client notation

        :return: trading pair in exchange notation
        """
        symbol_map = await self.trading_pair_symbol_map()
        return symbol_map.inverse[trading_pair]

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str,) -> str:
        """
        Used to translate a trading pair from the exchange notation to the client notation

        :param symbol: trading pair in exchange notation

        :return: trading pair in client notation
        """
        symbol_map = await self.trading_pair_symbol_map()
        return symbol_map[symbol]

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value for each trading pair passed as
        parameter

        :param trading_pairs: list of trading pairs to get the prices for

        :return: Dictionary of associations between token pair and its latest price
        """
        tasks = [self._get_last_traded_price(trading_pair=trading_pair) for trading_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

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
            top_price = Decimal(str(order_book.c_get_price(is_buy)))
        except EnvironmentError as e:
            self.logger().warning(f"{'Ask' if is_buy else 'Bid'} orderbook for {trading_pair} is empty.")
            return s_decimal_NaN
        return self.c_quantize_order_price(trading_pair, top_price)

    cdef ClientOrderBookQueryResult c_get_vwap_for_volume(self, str trading_pair, bint is_buy, object volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_vwap_for_volume(is_buy, float(volume))
            object query_volume = Decimal(str(result.query_volume))
            object result_price = Decimal(str(result.result_price))
            object result_volume = Decimal(str(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_price_for_quote_volume(self, str trading_pair, bint is_buy, double volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_price_for_quote_volume(is_buy, float(volume))
            object query_volume = Decimal(str(result.query_volume))
            object result_price = Decimal(str(result.result_price))
            object result_volume = Decimal(str(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_price_for_volume(self, str trading_pair, bint is_buy, object volume):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_price_for_volume(is_buy, float(volume))
            object query_volume = Decimal(str(result.query_volume))
            object result_price = Decimal(str(result.result_price))
            object result_volume = Decimal(str(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_quote_volume_for_base_amount(self, str trading_pair, bint is_buy,
                                                                       object base_amount):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_quote_volume_for_base_amount(is_buy, float(base_amount))
            object query_volume = Decimal(str(result.query_volume))
            object result_volume = Decimal(str(result.result_volume))
        return ClientOrderBookQueryResult(s_decimal_NaN,
                                          query_volume,
                                          s_decimal_NaN,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_volume_for_price(self, str trading_pair, bint is_buy, object price):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_volume_for_price(is_buy, float(price))
            object query_price = Decimal(str(result.query_price))
            object result_price = Decimal(str(result.result_price))
            object result_volume = Decimal(str(result.result_volume))
        return ClientOrderBookQueryResult(query_price,
                                          s_decimal_NaN,
                                          result_price,
                                          result_volume)

    cdef ClientOrderBookQueryResult c_get_quote_volume_for_price(self, str trading_pair, bint is_buy, object price):
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
            OrderBookQueryResult result = order_book.c_get_volume_for_price(is_buy, float(price))
            object query_price = Decimal(str(result.query_price))
            object result_price = Decimal(str(result.result_price))
            object result_volume = Decimal(str(result.result_volume))
        return ClientOrderBookQueryResult(query_price,
                                          s_decimal_NaN,
                                          result_price,
                                          result_volume)

    def order_book_bid_entries(self, trading_pair) -> Iterator[ClientOrderBookRow]:
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
        for entry in order_book.bid_entries():
            yield ClientOrderBookRow(Decimal(str(entry.price)),
                                     Decimal(str(entry.amount)),
                                     entry.update_id)

    def order_book_ask_entries(self, trading_pair) -> Iterator[ClientOrderBookRow]:
        cdef:
            OrderBook order_book = self.c_get_order_book(trading_pair)
        for entry in order_book.ask_entries():
            yield ClientOrderBookRow(Decimal(str(entry.price)),
                                     Decimal(str(entry.amount)),
                                     entry.update_id)

    def get_vwap_for_volume(self, trading_pair: str, is_buy: bool, volume: Decimal):
        return self.c_get_vwap_for_volume(trading_pair, is_buy, volume)

    def get_price_for_quote_volume(self, trading_pair: str, is_buy: bool, volume: Decimal):
        return self.c_get_price_for_quote_volume(trading_pair, is_buy, volume)

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

    async def _initialize_trading_pair_symbol_map(self):
        raise NotImplementedError

    def _set_trading_pair_symbol_map(self, trading_pair_and_symbol_map: Optional[Mapping[str, str]]):
        """
        Method added to allow the pure Python subclasses to set the value of the map
        """
        self._trading_pair_symbol_map = trading_pair_and_symbol_map

    def _set_order_book_tracker(self, order_book_tracker: Optional[OrderBookTracker]):
        """
        Method added to allow the pure Python subclasses to store the tracker in the instance variable
        """
        self._order_book_tracker = order_book_tracker

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        raise NotImplementedError
