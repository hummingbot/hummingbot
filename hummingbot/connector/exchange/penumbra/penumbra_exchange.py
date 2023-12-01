from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.penumbra.penumbra_constants import EXCHANGE_NAME, RATE_LIMITS
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class PenumbraExchange(ExchangePyBase):

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 pclientd_url: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._pclientd_url = pclientd_url

        super().__init__(client_config_map=client_config_map)
        self.type = "penumbra"

    @property
    def name(self) -> str:
        return EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return None

    # Need to implement all abstract methods from ExchangePyBase
    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return RATE_LIMITS

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    # TODO: Implement the below methods

    @property
    def domain(self) -> str:
        return

    @property
    def client_order_id_max_length(self) -> int:
        return

    @property
    def client_order_id_prefix(self) -> str:
        return

    @property
    def trading_rules_request_path(self) -> str:
        return

    @property
    def trading_pairs_request_path(self) -> str:
        return

    @property
    def check_network_request_path(self) -> str:
        return

    def _is_request_exception_related_to_time_synchronizer(
            self, request_exception: Exception) -> bool:
        return

    def _is_order_not_found_during_status_update_error(
            self, status_update_exception: Exception) -> bool:
        return

    def _is_order_not_found_during_cancelation_error(
            self, cancelation_exception: Exception) -> bool:
        return

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        return

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        return

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return

    async def _update_trading_fees(self):
        return

    async def _user_stream_event_listener(self):
        return

    async def _format_trading_rules(
            self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        return

    async def _update_balances(self):
        return

    async def _all_trade_updates_for_order(
            self, order: InFlightOrder) -> List[TradeUpdate]:
        return

    async def _request_order_status(
            self, tracked_order: InFlightOrder) -> OrderUpdate:
        return

    def _initialize_trading_pair_symbols_from_exchange_info(
            self, exchange_info: Dict[str, Any]):
        return

    # !! Ok we need to implement the below methods

    # TODO: Consider if any of the below are actually necessary (as we use proto services)
    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return None

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return None

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return None


# Resources:
# Working torwards https://hummingbot.org/strategies/avellaneda-market-making/
# https://hummingbot.org/developers/strategies/tutorial/#what-youll-learn
# https://www.youtube.com/watch?v=ZbkkGvB-fis
# M1 & M2 Chip Setup https://hummingbot.org/installation/mac/#conda-and-apple-m1m2-chips

# Installation command copypasta

'''

conda activate hummingbot
./install
./compile
./start

'''
