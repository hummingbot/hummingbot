import asyncio
import math
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from bxsolana import provider

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.bloxroute_openbook import (
    bloxroute_openbook_constants as CONSTANTS,
    bloxroute_openbook_utils,
    bloxroute_openbook_web_utils as web_utils,
)

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_auth import BloxrouteOpenbookAuth
# from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_utils import (
#     OrderTypeToBlxrOrderType,
#     TradeTypeToSide,
# )
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


# class TradingPair():
#     def __init__(self, baseToken: str, quoteToken: str):
#         self.baseToken = baseToken
#         self.quoteToken = quoteToken
#
#     @classmethod
#     def fromString(self, trading_pair: str) -> 'TradingPair':
#         tokens = trading_pair.split("-")
#         if len(tokens) != 2:
#             raise Exception("trading pair had more than three tokens")
#         return TradingPair(baseToken=tokens[0], quoteToken=tokens[1])

class BloxrouteOpenbookExchange(ExchangePyBase):
    """
    BloxrouteOpenbookExchange connects with BloxRoute Labs Solana Trader API provides order book pricing, user account tracking and
    trading functionality.
    """
    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    UPDATE_TRADE_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 bloxroute_api_key: str,
                 solana_wallet_public_key: str,
                 solana_wallet_private_key: str,
                 # trading_pairs_to_payer_address: Optional[Dict[str, str]] = None,
                 # trading_required: bool = True,
                 ):
        """
        :param auth_header: The bloxRoute Labs authorization header to connect with solana trader api
        :param private_key: The secret key for a solana wallet
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """

        self.logger().exception("creating blox route exchange")
        self.logger().exception("api key is" + bloxroute_api_key)
        self.logger().exception("pub key is" + solana_wallet_public_key)
        self.logger().exception("private key is" + solana_wallet_private_key)

        self._auth_header: str = bloxroute_api_key
        self._sol_wallet_public_key = solana_wallet_public_key
        self._sol_wallet_private_key = solana_wallet_private_key
        self._provider = provider
        # self._trading_required = trading_required
        # self._trading_pairs_to_payer_address = trading_pairs_to_payer_address

        super().__init__(client_config_map)
        self.real_time_balance_update = False # TODO add functionality for this

    @property
    def authenticator(self):
        return BloxrouteOpenbookAuth(
            auth_header=self._auth_header
        )

    @property
    def name(self) -> str:
        return "bloxroute_openbook"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN
    @property

    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.GET_TRADING_RULES_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.GET_TRADING_RULES_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.CHECK_NETWORK_PATH_URL

    @property
    def trading_pairs(self):
        raise Exception("not yet implemented")

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        raise Exception("not yet implemented")

    @property
    def is_trading_required(self) -> bool:
        raise Exception("not yet implemented")

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        raise Exception("not yet implemented")

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        raise Exception("not yet implemented")

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        raise Exception("not yet implemented")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        raise Exception("not yet implemented")

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        raise Exception("not yet implemented")

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        raise Exception("get fee not yet implemented")

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:

        raise Exception("place order not yet implemented")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        raise Exception("place cancel not yet implemented")

    async def _format_trading_rules(self, symbols_details: Dict[str, Any]) -> List[TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param symbols_details: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "code": 1000,
            "trace":"886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                    {
                        "symbol":"GXC_BTC",
                         "symbol_id":1024,
                         "base_currency":"GXC",
                         "quote_currency":"BTC",
                         "quote_increment":"1.00000000",
                         "base_min_size":"1.00000000",
                         "base_max_size":"10000000.00000000",
                         "price_min_precision":6,
                         "price_max_precision":8,
                         "expiration":"NA",
                         "min_buy_amount":"0.00010000",
                         "min_sell_amount":"0.00010000"
                    },
                    ...
                ]
            }
        }
        """
        raise Exception("format trading rules not yet implemented")

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        raise Exception("update trading fees not yet implemented")

    async def _update_balances(self):
       raise Exception("update balances not yet implemented")

    async def _request_order_update(self, order: InFlightOrder) -> Dict[str, Any]:
        raise Exception("request order update not yet implmented")

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        raise Exception("request order fills not yet impgit lemented")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise Exception("all trade updates for order not yet implemented")

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        raise Exception("request order status not yet implemented")

    def _create_order_fill_updates(self, order: InFlightOrder, fill_update: Dict[str, Any]) -> List[TradeUpdate]:
        raise Exception("create order fill updates not yet implemented")

    def _create_order_update(self, order: InFlightOrder, order_update: Dict[str, Any]) -> OrderUpdate:
        raise Exception("create order update not yet implemented")

    async def _user_stream_event_listener(self):
        raise Exception("user stream event listener not yet implemented")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise Exception("initialize trading pair symbols from exchange info not yet implemented")

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        raise Exception("get last traded price not yet implemented")