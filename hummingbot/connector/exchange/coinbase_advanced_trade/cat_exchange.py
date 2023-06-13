from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, Iterable, List, Optional, Set, cast

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS, cat_web_utils as web_utils
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_api_order_book_data_source import (
    CoinbaseAdvancedTradeAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_api_user_stream_data_source import (
    CoinbaseAdvancedTradeAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_auth import CoinbaseAdvancedTradeAuth
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeGetTransactionSummaryResponse as _TransactionSummary,
)

# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_protocols import (
#     CoinbaseAdvancedTradeWebAssistantsFactoryAdapter,
# )
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_accounts_mixin import AccountsMixin
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_orders_mixin import OrdersMixin
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_trading_pairs_rules_mixin import (
    TradingPairsRulesMixin,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_websocket_mixin import WebsocketMixin
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class _UtilitiesSuperCalls:
    """
    This class is used to separate the methods inherited from ExchangePyBase
    in an attempt to reduce the size of the class definition.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def current_timestamp(self) -> float:
        # Defined in TimeIterator
        return super().current_timestamp

    async def _sleep(self, sleep: float):
        # Defined in ExchangePyBase
        await super()._sleep(sleep)

    def logger(self) -> HummingbotLogger:
        # Defined in ExchangePyBase
        return super().logger()


class _APICallsSuperCalls:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # @cat_api_call_http_error_handler
    async def api_post(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await super()._api_post(*args, **kwargs)

    # @cat_api_call_http_error_handler
    async def api_delete(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await super()._api_delete(*args, **kwargs)

    # @cat_api_call_http_error_handler
    async def api_get(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await super()._api_get(*args, **kwargs)


class CoinbaseAdvancedTradeExchange(
    TradingPairsRulesMixin,
    AccountsMixin,
    WebsocketMixin,
    OrdersMixin,
    _APICallsSuperCalls,
    _UtilitiesSuperCalls,
    ExchangePyBase,
):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self, client_config_map: "ClientConfigAdapter", coinbase_advanced_trade_api_key: str,
                 coinbase_advanced_trade_api_secret: str, trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True, domain: str = CONSTANTS.DEFAULT_DOMAIN):
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
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def time_synchronizer(self) -> TimeSynchronizer:
        # Defined in ExchangePyBase
        return self._time_synchronizer

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def order_tracker(self) -> ClientOrderTracker:
        # Defined in ExchangePyBase
        return self._order_tracker

    @property
    def exchange_order_ids(self) -> ClientOrderTracker:
        # Defined in ExchangePyBase
        return self._exchange_order_ids

    def iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        return self._iter_user_event_queue()

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    def get_balances_keys(self) -> Set[str]:
        return self._account_balances.keys()

    def remove_balances(self, assets: Iterable[str]):
        for asset in assets:
            self._account_balances.pop(asset, None)
            self._account_available_balances.pop(asset, None)

    def update_balance(self, asset: str, balance: Decimal):
        self._account_balances[asset] = balance

    def update_available_balance(self, asset: str, balance: Decimal):
        self._account_available_balances[asset] = balance

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def last_poll_timestamp(self) -> float:
        # Defined in ExchangePyBase
        return self._last_poll_timestamp

    @property
    def trading_rules_request_path(self):
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    @property
    def trading_pairs_request_path(self):
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    @property
    def check_network_request_path(self):
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # time endpoint does not communicate an error code
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CoinbaseAdvancedTradeAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
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
