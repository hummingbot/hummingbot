from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import OrderType, TradeType

s_decimal_NaN = Decimal("nan")


class MockExchange(ExchangeBase):

    def __init__(self):
        super(MockExchange, self).__init__()
        self._buy_price = Decimal(1)
        self._sell_price = Decimal(1)

    @property
    def buy_price(self) -> Decimal:
        return self._buy_price

    @buy_price.setter
    def buy_price(self, price: Decimal):
        self._buy_price = price

    @property
    def sell_price(self) -> Decimal:
        return self._sell_price

    @sell_price.setter
    def sell_price(self, price: Decimal):
        self._sell_price = price

    @property
    def status_dict(self) -> Dict[str, bool]:
        pass

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrderBase]:
        pass

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        pass

    def stop_tracking_order(self, order_id: str):
        pass

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        pass

    @property
    def limit_orders(self) -> List[LimitOrder]:
        pass

    def c_stop_tracking_order(self, order_id):
        pass

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        pass

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET, price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        pass

    def cancel(self, trading_pair: str, client_order_id: str):
        pass

    def get_order_book(self, trading_pair: str) -> OrderBook:
        pass

    def get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                amount: Decimal, price: Decimal = s_decimal_NaN, is_maker: Optional[bool] = None
                ) -> AddedToCostTradeFee:
        pass

    _ready = False

    @property
    def ready(self):
        return self._ready

    @ready.setter
    def ready(self, status: bool):
        self._ready = status

    def get_price(self, trading_pair: str, is_buy_price: bool) -> Decimal:
        return self.buy_price if is_buy_price else self.sell_price

    def update_account_balance(self, asset_balance: Dict[str, Decimal]):
        if not self._account_balances:
            self._account_balances = {}

        for asset, balance in asset_balance.items():
            self._account_balances[asset] = self._account_balances.get(asset, Decimal(0)) + balance

    def update_account_available_balance(self, asset_balance: Dict[str, Decimal]):
        if not self._account_available_balances:
            self._account_available_balances = {}

        for asset, balance in asset_balance.items():
            self._account_available_balances[asset] = self._account_available_balances.get(asset, Decimal(0)) + balance
