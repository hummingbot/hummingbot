from decimal import Decimal
import pandas as pd
from typing import (
    Dict,
    List,
)

from hummingbot.core.data_type.cancellation_result import CancellationResult
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

NaN = float("nan")


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
        self.event_reporter = EventReporter(event_source=self.__class__.__name__)
        self.event_logger = EventLogger(event_source=self.name)
        for event_tag in self.MARKET_EVENTS:
            self.c_add_listener(event_tag.value, self.event_reporter)
            self.c_add_listener(event_tag.value, self.event_logger)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {}

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def event_logs(self) -> List[any]:
        return self.event_logger.event_log

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    def limit_orders(self) -> List[LimitOrder]:
        raise NotImplementedError

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        :return: data frame with symbol as index, and at least the following columns --
                 ["baseAsset", "quoteAsset", "volume", "USDVolume"]
        """
        raise NotImplementedError

    def get_balance(self, currency: str) -> float:
        return self.c_get_balance(currency)

    def get_all_balances(self) -> Dict[str, float]:
        raise NotImplementedError

    def get_price(self, symbol: str, is_buy: bool) -> float:
        return self.c_get_price(symbol, is_buy)

    def withdraw(self, address: str, currency: str, amount: float) -> str:
        return self.c_withdraw(address, currency, amount)

    def deposit(self, from_wallet: WalletBase, currency: str, amount: float) -> str:
        return self.c_deposit(from_wallet, currency, amount)

    def get_order_book(self, symbol: str) -> OrderBook:
        return self.c_get_order_book(symbol)

    def buy(self, symbol: str, amount: float, order_type = OrderType.MARKET, price: float = 0.0, **kwargs) -> str:
        return self.c_buy(symbol, amount, order_type, price, kwargs)

    def sell(self, symbol: str, amount: float, order_type = OrderType.MARKET, price: float = 0.0, **kwargs) -> str:
        return self.c_sell(symbol, amount, order_type, price, kwargs)

    def cancel(self, symbol: str, client_order_id: str):
        return self.c_cancel(symbol, client_order_id)

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        raise NotImplementedError

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: float,
                price: float = NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_price_quantum(self, symbol: str, price: float) -> Decimal:
        return self.c_get_order_price_quantum(symbol, price)

    def get_order_size_quantum(self, symbol: str, order_size: float) -> Decimal:
        return self.c_get_order_size_quantum(symbol, order_size)

    def quantize_order_price(self, symbol: str, price: float) -> Decimal:
        return self.c_quantize_order_price(symbol, price)

    def quantize_order_amount(self, symbol: str, amount: float) -> Decimal:
        return self.c_quantize_order_amount(symbol, amount)

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0, dict kwargs = {}):
        raise NotImplementedError

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0, dict kwargs = {}):
        raise NotImplementedError

    cdef c_cancel(self, str symbol, str client_order_id):
        raise NotImplementedError

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          double amount,
                          double price):
        raise NotImplementedError

    cdef double c_get_balance(self, str currency) except? -1:
        raise NotImplementedError

    cdef str c_withdraw(self, str address, str currency, double amount):
        raise NotImplementedError

    cdef str c_deposit(self, WalletBase from_wallet, str currency, double amount):
        raise NotImplementedError

    cdef OrderBook c_get_order_book(self, str symbol):
        raise NotImplementedError

    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        raise NotImplementedError

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        raise NotImplementedError

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        raise NotImplementedError

    cdef object c_quantize_order_price(self, str symbol, double price):
        price_quantum = self.c_get_order_price_quantum(symbol, price)
        return round(Decimal(price) / price_quantum) * price_quantum

    cdef object c_quantize_order_amount(self, str symbol, double amount):
        order_size_quantum = self.c_get_order_size_quantum(symbol, amount)
        return (Decimal(amount) // order_size_quantum) * order_size_quantum
