from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.coinswitchx import (
    coinswitchx_constants as CONSTANTS,
    coinswitchx_utils,
    coinswitchx_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinswitchx.coinswitchx_auth import CoinswitchxAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinswitchxExchange(ExchangePyBase):

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 coinswitchx_api_key: str,
                 coinswitchx_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN
                 ):
        self.api_key = coinswitchx_api_key
        self.secret_key = coinswitchx_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return "coinswitchx"

    @property
    def authenticator(self):
        return CoinswitchxAuth(
            api_key = self.api_key,
            secret_key = self.secret_key,
            time_provider=self._time_synchronizer
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        pass

    @property
    def trading_pairs_request_path(self) -> str:
        pass

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        pass

    @property
    def is_trading_required(self) -> bool:
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        pass

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        pass

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        pass

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        pass

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        pass

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        pass

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        pass

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        pass

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           ) -> Tuple[str, float]:
        pass

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        pass

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        pass

    def supported_order_types(self) -> List[OrderType]:
        pass

    async def _user_stream_event_listener(self):
        pass

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        balances = await self._api_get(
            path_url = CONSTANTS.GET_BALANCE_PATH_URL,
            is_auth_required = True
        )

        available = balances.get("Available")
        locked = balances.get("Locked")
        assets = available.keys()

        for asset in assets:
            asset_name = asset.upper()
            free_balance = coinswitchx_utils.decimal_val_or_none(available.get(asset_name))
            total_balance = free_balance + coinswitchx_utils.decimal_val_or_none(locked.get(asset_name))
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]
