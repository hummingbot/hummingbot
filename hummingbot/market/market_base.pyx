from decimal import Decimal
import pandas as pd
from typing import (
    Dict,
    List,
    Tuple,
    Optional,
    Iterator)

from hummingbot.client.config.global_config_map import (
    global_config_map,
)
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.order_book_query_result import (
    OrderBookQueryResult,
    ClientOrderBookQueryResult
)
from hummingbot.core.data_type.order_book_row import (
    ClientOrderBookRow
)
from hummingbot.core.event.events import (
    MarketEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkIterator
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from .deposit_info import DepositInfo
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.core.utils.estimate_fee import estimate_fee

NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)

cdef class MarketBase(NetworkIterator):
    MARKET_EVENTS = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderExpired
    ]

    def __init__(self):
        super().__init__()
        self._event_reporter = EventReporter(event_source=self.name)
        self._event_logger = EventLogger(event_source=self.name)
        for event_tag in self.MARKET_EVENTS:
            self.c_add_listener(event_tag.value, self._event_reporter)
            self.c_add_listener(event_tag.value, self._event_logger)

        self._account_balances = {}  # Dict[asset_name:str, Decimal]
        self._account_available_balances = {}  # Dict[asset_name:str, Decimal]
        self._asset_limit = {}  # Dict[asset_name: str, Decimal]
        self._real_time_balance_update = True
        self._order_book_tracker = None

    @staticmethod
    def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
        try:
            return tuple(trading_pair.split('-'))
        # Exceptions are logged as warnings in Trading pair fetcher class
        except Exception:
            return None

    def in_flight_asset_balances(self, in_flight_orders: Dict[str, InFlightOrderBase]) -> Dict[str, Decimal]:
        """
        Calculates the individual asset balances used in in_flight_orders
        For BUY order, this is the quote asset balance locked in the order
        For SELL order, this is the base asset balance locked in the order
        """
        asset_balances = {}
        if in_flight_orders is None:
            return asset_balances
        for order in [o for o in in_flight_orders.values() if not (o.is_done or o.is_failure or o.is_cancelled)]:
            if order.trade_type is TradeType.BUY:
                order_value = Decimal(order.amount * order.price)
                outstanding_value = order_value - order.executed_amount_quote
                if order.quote_asset not in asset_balances:
                    asset_balances[order.quote_asset] = s_decimal_0
                fee = estimate_fee(self.name, True)
                outstanding_value *= (Decimal(1) + fee.percent)
                asset_balances[order.quote_asset] += outstanding_value
            else:
                outstanding_value = order.amount - order.executed_amount_base
                if order.base_asset not in asset_balances:
                    asset_balances[order.base_asset] = s_decimal_0
                asset_balances[order.base_asset] += outstanding_value
        return asset_balances

    def order_filled_balances(self, starting_timestamp = 0):
        """
        Calculates the individual asset balances as a result of order being filled
        For BUY filled order, the quote balance goes down while the base balance goes up, and for SELL order, it's the
        opposite. This does not account for fee.
        """
        order_filled_events = list(filter(lambda e: isinstance(e, OrderFilledEvent), self.event_logs))
        order_filled_events = [o for o in order_filled_events if o.timestamp > starting_timestamp]
        balances = {}
        for event in order_filled_events:
            hb_trading_pair = self.convert_from_exchange_trading_pair(event.trading_pair)
            base, quote = hb_trading_pair.split("-")[0], hb_trading_pair.split("-")[1]
            if event.trade_type is TradeType.BUY:
                quote_value = Decimal("-1") * event.price * event.amount
                base_value = event.amount
            else:
                quote_value = event.price * event.amount
                base_value = Decimal("-1") * event.amount
            if base not in balances:
                balances[base] = s_decimal_0
            if quote not in balances:
                balances[quote] = s_decimal_0
            balances[base] += base_value
            balances[quote] += quote_value
        return balances

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
        return exchange_trading_pair

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        return hb_trading_pair

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {}

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def event_logs(self) -> List[any]:
        return self._event_logger.event_log

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    def limit_orders(self) -> List[LimitOrder]:
        raise NotImplementedError

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrderBase]:
        raise NotImplementedError

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {}

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return (self.get_price(trading_pair, True) + self.get_price(trading_pair, False)) / Decimal("2")

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restores the tracking states from a previously saved state.

        :param saved_states: Previously saved tracking states from `tracking_states` property.
        """
        pass

    def get_exchange_limit_config(self, market: str) -> Dict[str, object]:
        """
        Retrieves the Balance Limits for the specified market.
        """
        all_ex_limit = global_config_map["balance_asset_limit"].value
        if all_ex_limit is None:
            return {}
        exchange_limits = all_ex_limit.get(market, {})
        return exchange_limits if exchange_limits is not None else {}

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        :return: data frame with trading_pair as index, and at least the following columns --
                 ["baseAsset", "quoteAsset", "volume", "USDVolume"]
        """
        raise NotImplementedError

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        raise NotImplementedError

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        raise NotImplementedError

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN, dict kwargs={}):
        raise NotImplementedError

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN, dict kwargs={}):
        raise NotImplementedError

    cdef c_cancel(self, str trading_pair, str client_order_id):
        raise NotImplementedError

    cdef c_stop_tracking_order(self, str order_id):
        raise NotImplementedError

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        raise NotImplementedError

    def get_all_balances(self) -> Dict[str, Decimal]:
        """
        *required
        :return: Dict[asset_name: asst_balance]: Balances of all assets being traded
        """
        return self._account_balances.copy()

    cdef object c_get_balance(self, str currency):
        """
        :returns: Total balance for a specific asset
        """
        return self._account_balances.get(currency, s_decimal_0)

    def apply_balance_limit(self, currency: str, available_balance: Decimal, limit: Decimal) -> Decimal:
        """
        Apply budget limit on an available balance, the limit is calculated as followings:
        - Minus balance used in outstanding orders (in flight orders), if the budget is 1 ETH and the bot has already
          used 0.5 ETH to put a maker buy order, the budget is now 0.5
        - Plus balance accredited from filled orders (since the bot started), if the budget is 1 ETH and the bot has
          bought LINK (for 0.5 ETH), the ETH budget is now 0.5. However if later on the bot has sold LINK (for 0.5 ETH)
          the budget is now 1 ETH
        """
        in_flight_balance = self.in_flight_asset_balances(self.in_flight_orders).get(currency, s_decimal_0)
        limit -= in_flight_balance
        filled_balance = self.order_filled_balances().get(currency, s_decimal_0)
        limit += filled_balance
        asset_limit = max(limit, s_decimal_0)
        return min(available_balance, asset_limit)

    def apply_balance_update_since_snapshot(self, currency: str, available_balance: Decimal):
        """
        Applies available balance update as followings
        :param currency: the token symbol
        :param available_balance: the current available_balance, this is also the snap balance taken since last
        _update_balances()
        :returns the real available that accounts for changes in in flight orders and filled orders
        """
        snapshot_bal = self.in_flight_asset_balances(self._in_flight_orders_snapshot).get(currency, s_decimal_0)
        in_flight_bal = self.in_flight_asset_balances(self.in_flight_orders).get(currency, s_decimal_0)
        orders_filled_bal = self.order_filled_balances(self._in_flight_orders_snapshot_timestamp).get(currency,
                                                                                                      s_decimal_0)
        actual_available = available_balance + snapshot_bal - in_flight_bal + orders_filled_bal
        return actual_available

    cdef object c_get_available_balance(self, str currency):
        """
        If there is a budget limit set on the balance
        :returns: Balance available for trading for a specific asset
        """
        available_balance = self._account_available_balances.get(currency, s_decimal_0)
        if not self._real_time_balance_update:
            available_balance = self.apply_balance_update_since_snapshot(currency, available_balance)
        exchange_limits = self.get_exchange_limit_config(self.name)
        if currency in exchange_limits:
            asset_limit = Decimal(str(exchange_limits[currency]))
            available_balance = self.apply_balance_limit(currency, available_balance, asset_limit)
        return available_balance

    cdef str c_withdraw(self, str address, str currency, object amount):
        raise NotImplementedError

    cdef OrderBook c_get_order_book(self, str trading_pair):
        raise NotImplementedError

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        raise NotImplementedError

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        raise NotImplementedError

    cdef object c_quantize_order_price(self, str trading_pair, object price):
        if price.is_nan():
            return price
        price_quantum = self.c_get_order_price_quantum(trading_pair, price)
        return round(price / price_quantum) * price_quantum

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_NaN):
        order_size_quantum = self.c_get_order_size_quantum(trading_pair, amount)
        return (amount // order_size_quantum) * order_size_quantum

    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>

    # <editor-fold desc="+ Decimal interface to OrderBook">
    # ----------------------------------------------------------------------------------------------------------
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
            self.logger().warning(f"{'Ask' if is_buy else 'Buy'} orderbook for {trading_pair} is empty.")
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

    cdef ClientOrderBookQueryResult c_get_quote_volume_for_base_amount(self, str trading_pair, bint is_buy, object base_amount):
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
    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>

    # <editor-fold desc="+ Wrapper for cython functions">
    # ----------------------------------------------------------------------------------------------------------
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

    def get_balance(self, currency: str) -> Decimal:
        return self.c_get_balance(currency)

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_available_balance(self, currency: str) -> Decimal:
        return self.c_get_available_balance(currency)

    def withdraw(self, address: str, currency: str, amount: Decimal) -> str:
        return self.c_withdraw(address, currency, amount)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

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
        if OrderType.LIMIT_MAKER in self.supported_order_types():
            return OrderType.LIMIT_MAKER
        elif OrderType.LIMIT in self.supported_order_types():
            return OrderType.LIMIT
        else:
            raise Exception("There is no maker order type supported by this exchange.")

    def get_taker_order_type(self):
        if OrderType.MARKET in self.supported_order_types():
            return OrderType.MARKET
        elif OrderType.LIMIT in self.supported_order_types():
            return OrderType.LIMIT
        else:
            raise Exception("There is no taker order type supported by this exchange.")
    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>
