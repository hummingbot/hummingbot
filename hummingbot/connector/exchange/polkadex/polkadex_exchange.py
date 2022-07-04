from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class PolkadexExchange(ExchangePyBase):
    @property
    def authenticator(self):
        return None

    @property
    def domain(self):
        return None

    @property
    def client_order_id_max_length(self):
        return None

    @property
    def client_order_id_prefix(self):
        return None

    @property
    def trading_rules_request_path(self):
        return None

    @property
    def trading_pairs_request_path(self):
        return None

    @property
    def check_network_request_path(self):
        return None

    @property
    def is_trading_required(self) -> bool:
        return True

    def __init__(self, endpoint: str, api_key: str, trading_pairs: Optional[List[str]] = None):
        self.endpoint = endpoint
        self.api_key = api_key
        self._trading_pairs = trading_pairs
        self._last_trades_poll_binance_timestamp = 1.0
        super().__init__()

    @property
    def rate_limits_rules(self):
        return None


    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    def name(self):
        return "polkadex"

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
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

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
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

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        pass

    def c_stop_tracking_order(self, order_id):
        pass

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        pass
