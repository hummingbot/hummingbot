from typing import TYPE_CHECKING, List, Optional, cast

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

from . import cat_constants as CONSTANTS, cat_web_utils as web_utils
from .cat_api_order_book_data_source import CoinbaseAdvancedTradeAPIOrderBookDataSource
from .cat_api_user_stream_data_source import CoinbaseAdvancedTradeAPIUserStreamDataSource
from .cat_auth import CoinbaseAdvancedTradeAuth
from .cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeGetTransactionSummaryResponse as _TransactionSummary,
)

# from .cat_data_types.cat_protocols import (
#     CoinbaseAdvancedTradeWebAssistantsFactoryAdapter,
# )
from .cat_exchange_mixins.cat_accounts_mixin import CoinbaseAdvancedTradeAccountsMixin
from .cat_exchange_mixins.cat_api_calls_mixin import CoinbaseAdvancedTradeAPICallsMixin
from .cat_exchange_mixins.cat_exchange_protocols import CoinbaseAdvancedTradeTradingPairsMixinProtocol
from .cat_exchange_mixins.cat_not_implemented_mixin import CoinbaseAdvancedTradeNotImplementedMixin
from .cat_exchange_mixins.cat_orders_mixin import OrdersMixin
from .cat_exchange_mixins.cat_trading_pairs_rules_mixin import TradingPairsRulesMixin
from .cat_exchange_mixins.cat_websocket_mixin import WebsocketMixin

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class _DataSourceProtocol(CoinbaseAdvancedTradeTradingPairsMixinProtocol):
    _trading_pairs: List[str]
    _web_assistants_factory: WebAssistantsFactory
    _auth: CoinbaseAdvancedTradeAuth
    domain: str


class CoinbaseAdvancedTradeExchange(
    CoinbaseAdvancedTradeNotImplementedMixin,
    TradingPairsRulesMixin,
    CoinbaseAdvancedTradeAccountsMixin,
    WebsocketMixin,
    OrdersMixin,
    CoinbaseAdvancedTradeAPICallsMixin,
    ExchangePyBase,
):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            coinbase_advanced_trade_api_key: str,
            coinbase_advanced_trade_api_secret: str,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True, domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        self.api_key = coinbase_advanced_trade_api_key
        self.secret_key = coinbase_advanced_trade_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map=client_config_map)

    @property
    def authenticator(self):
        return CoinbaseAdvancedTradeAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "coinbase_advanced_trade"
        else:
            return f"coinbase_advanced_trade_{self._domain}"

    @property
    def domain(self):
        return self._domain

    @property
    def time_synchronizer(self) -> TimeSynchronizer:
        # Defined in ExchangePyBase
        return self._time_synchronizer

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # time endpoint does not communicate an error code
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self: _DataSourceProtocol) -> OrderBookTrackerDataSource:
        return CoinbaseAdvancedTradeAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self: _DataSourceProtocol) -> UserStreamTrackerDataSource:
        return CoinbaseAdvancedTradeAPIUserStreamDataSource(
            auth=cast(CoinbaseAdvancedTradeAuth, self._auth),
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        fees: _TransactionSummary = _TransactionSummary(
            **await self._api_request("get", CONSTANTS.TRANSACTIONS_SUMMARY_EP))
        self._trading_fees = fees

    async def _make_network_check_request(self):
        await self._api_get(path_url=CONSTANTS.SERVER_TIME_EP)
