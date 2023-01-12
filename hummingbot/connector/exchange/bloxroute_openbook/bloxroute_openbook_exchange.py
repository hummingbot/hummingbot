import asyncio
import os
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from bxsolana import Provider
from bxsolana.provider import GrpcProvider, WsProvider
from bxsolana.provider.constants import TESTNET_API_GRPC_HOST, TESTNET_API_GRPC_PORT
from bxsolana_trader_proto import GetMarketsResponse, api
from bxsolana_trader_proto.api import (
    GetAccountBalanceResponse,
    GetQuotesResponse,
    GetServerTimeResponse,
    Market,
    TokenBalance,
)

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.bloxroute_openbook import (
    bloxroute_openbook_constants as CONSTANTS,
    bloxroute_openbook_web_utils as web_utils,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_api_order_book_data_source import (
    BloxrouteOpenbookAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_auth import BloxrouteOpenbookAuth
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import OPENBOOK_PROJECT
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_orderbook_manager import (
    BloxrouteOpenbookOrderbookManager,
)

# from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_utils import (
#     OrderTypeToBlxrOrderType,
#     TradeTypeToSide,
# )
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class BloxrouteOpenbookExchange(ExchangePyBase):
    """
    BloxrouteOpenbookExchange connects with BloxRoute Labs Solana Trader API provides order book pricing, user account tracking and
    trading functionality.
    """

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        bloxroute_api_key: str,
        solana_wallet_public_key: str,
        solana_wallet_private_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        """
        :param auth_header: The bloxRoute Labs authorization header to connect with solana trader api
        :param private_key: The secret key for a solana wallet
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """

        self.logger().exception("creating blox route exchange")
        self.logger().exception("api key is " + bloxroute_api_key)
        self.logger().exception("pub key is " + solana_wallet_public_key)
        self.logger().exception("private key is " + solana_wallet_private_key)

        self._auth_header = bloxroute_api_key
        self._sol_wallet_public_key = solana_wallet_public_key
        self._sol_wallet_private_key = solana_wallet_private_key
        self._trading_required = trading_required

        self._server_response = GetServerTimeResponse

        self._provider_1: Provider = WsProvider(auth_header=bloxroute_api_key, private_key=solana_wallet_private_key)
        self._provider_2: Provider = WsProvider(auth_header=bloxroute_api_key, private_key=solana_wallet_private_key)
        asyncio.create_task(self.connect())

        self._trading_pairs = trading_pairs
        self._order_book_manager: BloxrouteOpenbookOrderbookManager = BloxrouteOpenbookOrderbookManager(
            self._provider_2, self._trading_pairs
        )
        self._order_book_manager_connected = False
        asyncio.create_task(self.initialize_order_books())

        super().__init__(client_config_map)
        self.real_time_balance_update = False

    async def connect(self):
        await self._provider_1.connect()
        await self._provider_2.connect()

        print("connected!")

    async def initialize_order_books(self):
        await self._order_book_manager.start()
        self._order_book_manager_connected = True

        print("order books initialized!")

    def authenticator(self):
        return BloxrouteOpenbookAuth(
            api_key=self._auth_header, secret_key=self._sol_wallet_private_key, time_provider=self._time_synchronizer
        )

    @property
    def name(self) -> str:
        return "bloxroute-openbook"

    async def check_network(self) -> NetworkStatus:
        self._server_response: GetServerTimeResponse = await self._provider_1.get_server_time()
        if self._server_response.timestamp:
            return NetworkStatus.CONNECTED
        else:
            return NetworkStatus.NOT_CONNECTED

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": True,
            "trading_rule_initialized": True,
        }

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        if self._order_book_manager.is_ready:
            price, _ = self._order_book_manager.get_price_with_opportunity_size(trading_pair=trading_pair,
                                                                                is_buy=is_buy)
            return Decimal(price)
        else:
            if not self._order_book_manager.started:
                asyncio.create_task(self.initialize_order_books())
            return Decimal(0)

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
        return CONSTANTS.MARKET_PATH

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.MARKET_PATH

    @property
    def check_network_request_path(self):
        pass

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        raise Exception("not yet implemented")

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        raise Exception("not yet implemented")

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        raise Exception("not yet implemented")

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BloxrouteOpenbookAPIOrderBookDataSource(
            provider=self._provider_1, trading_pairs=self._trading_pairs, connector=self
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        raise NotImplementedError

    def _is_user_stream_initialized(self):
        return True

    def _create_user_stream_tracker(self):
        return None

    def _create_user_stream_tracker_task(self):
        return None

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> AddedToCostTradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        raise Exception("get fee not yet implemented")

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

        side = api.Side.S_BID if trade_type == TradeType.BUY else api.Side.S_ASK
        type = api.OrderType.OT_LIMIT if order_type == OrderType.LIMIT else api.OrderType.OT_MARKET

        submit_order_response = await self._provider_1.submit_order(
            owner_address=self._sol_wallet_public_key,
            payer_address=self._sol_wallet_public_key,
            market=trading_pair,
            side=side,
            types=[type],
            amount=float(amount),
            price=float(price),
            project=OPENBOOK_PROJECT,
            skip_pre_flight=True,
        )

        self.logger().info(f"placed order f{submit_order_response}")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        side = api.Side.S_BID if tracked_order.trade_type == TradeType.BUY else api.Side.S_ASK

        cancel_order_response = await self._provider_1.submit_cancel_order(
            order_i_d=order_id,
            side=side,
            market_address=tracked_order.trading_pair,
            owner_address=self._sol_wallet_public_key,
            project=OPENBOOK_PROJECT,
            skip_pre_flight=True,
        )

        self.logger().info(f"cancelled order f{cancel_order_response}")

    async def _format_trading_rules(self, markets_by_name: Dict[str, Market]) -> List[TradingRule]:
        trading_rules = []
        for market_name in markets_by_name:
            market = markets_by_name[market_name]

            tokens = market.market.split("/")
            trading_pair = f"{tokens[0]}-{tokens[1]}"

            quantity_precision = market.base_decimals
            price_precision = market.quote_decimals
            min_order_size = Decimal(str(10 ** -quantity_precision))
            min_quote_amount = Decimal(str(10 ** -price_precision))
            trading_rules.append(
                TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size,
                    min_order_value=min_order_size * min_quote_amount,
                    max_price_significant_digits=Decimal(str(price_precision)),
                    min_base_amount_increment=min_order_size,
                    min_quote_amount_increment=min_quote_amount,
                    min_price_increment=min_quote_amount,
                )
            )

        return trading_rules

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        """
        Returns a price step, a minimum price increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, price: Decimal):
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_base_amount_increment

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        # implementation is not required for bloxroute openbook at this time 1/10/2023
        pass

    async def _update_balances(self):
        account_balance: GetAccountBalanceResponse = await self._provider_1.get_account_balance()
        for token_info in account_balance.tokens:
            self._account_balances[token_info.symbol] = token_info.wallet_amount + token_info.unsettled_amount
            self._account_available_balances[token_info.symbol] = token_info.wallet_amount

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
        pass

    def _initialize_trading_pair_symbols_from_exchange_info(self, markets_by_name: Dict[str, Market]):
        mapping = bidict()

        for market_name in markets_by_name:
            # format is 1SP/USDC-P_OPENBOOK

            token_pair = market_name.split("-")
            tokens = token_pair[0].split("/")
            base = tokens[0]
            quote = tokens[1]
            trading_pair = f"{base}/{quote}"

            mapping[market_name] = trading_pair

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        seperator = ""
        if "-" in trading_pair:
            seperator = "-"
        elif "/" in trading_pair:
            seperator = "/"
        else:
            raise Exception("trading pair has no `-` or `/` seperator")
        split_token = trading_pair.split(seperator)
        in_token = split_token[0]
        out_token = split_token[1]

        quotes_response: GetQuotesResponse = await self._provider_1.get_quotes(
            in_token=in_token, out_token=out_token, in_amount=1, slippage=0.05, limit=1, projects=[OPENBOOK_PROJECT]
        )
        quotes = quotes_response.quotes[-1]
        routes = quotes.routes[-1]
        return routes.out_amount  # this is the price

    async def _update_trading_rules(self):
        markets_response: GetMarketsResponse = await self._provider_1.get_markets()
        markets_by_name = markets_response.markets

        trading_rules_list = await self._format_trading_rules(markets_by_name)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        self._initialize_trading_pair_symbols_from_exchange_info(markets_by_name=markets_by_name)
