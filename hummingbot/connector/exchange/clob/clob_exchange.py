from decimal import Decimal
from typing import Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class CLOBExchange(ExchangePyBase):
    @property
    def authenticator(self):
        pass

    @property
    def rate_limits_rules(self):
        pass

    @property
    def domain(self):
        pass

    @property
    def client_order_id_max_length(self):
        pass

    @property
    def client_order_id_prefix(self):
        pass

    @property
    def trading_rules_request_path(self):
        pass

    @property
    def check_network_request_path(self):
        pass

    def supported_order_types(self):
        pass

    def name(self):
        pass

    async def _place_cancel(self):
        pass

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal) -> Tuple[str, float]:
        pass

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: Decimal, price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        pass

    async def _update_trading_fees(self):
        pass

    def _user_stream_event_listener(self):
        pass

    def _format_trading_rules(self):
        pass

    def _update_order_status(self):
        pass

    def _update_balances(self):
        pass

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        pass

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        pass

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        pass

    def c_stop_tracking_order(self, order_id):
        pass
