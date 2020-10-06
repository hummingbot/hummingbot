import logging
from decimal import Decimal

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderType,
)
from hummingbot.connector.connector_base import ConnectorBase
s_logger = None
s_decimal_NaN = Decimal("nan")


class BalancerConnector(ConnectorBase):
    """
    BalancerConnector connects with balancer gateway APIs and provides pricing, user account tracking and trading
    functionality.
    """
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self):
        super().__init__()

    @property
    def name(self):
        return "balancer"

    def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        if is_buy:
            return self._buy_prices[trading_pair]
        else:
            return self._sell_prices[trading_pair]

    def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        return self.get_quote_price(trading_pair, is_buy, amount)

    def set_balance(self, token, balance):
        self._account_balances[token] = Decimal(str(balance))
        self._account_available_balances[token] = Decimal(str(balance))

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal):
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal):
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal):
        side = "buy" if is_buy else "sell"
        order_id = f"{side}-{trading_pair}-{get_tracking_nonce()}"
        event_tag = MarketEvent.BuyOrderCreated if is_buy else MarketEvent.SellOrderCreated
        event_class = BuyOrderCreatedEvent if is_buy else SellOrderCreatedEvent
        self.trigger_event(event_tag, event_class(self.current_timestamp, OrderType.LIMIT, trading_pair,
                                                  amount, price, order_id))
        return order_id

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("0.01")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("0.01")

    def ready(self):
        return True

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED
