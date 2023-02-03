import asyncio
import math
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from bxsolana import Provider
from bxsolana.provider import WsProvider
from bxsolana_trader_proto import GetMarketsResponse, api
from bxsolana_trader_proto.api import (
    GetAccountBalanceResponse,
    GetQuotesResponse,
    GetServerTimeResponse,
    Market,
    OrderStatus,
    Side,
)

from hummingbot.client.hummingbot_application import HummingbotApplication
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
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_book import BloxrouteOpenbookOrderBook
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_data_manager import (
    BloxrouteOpenbookOrderDataManager,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, DeductedFromReturnsTradeFee, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
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
        open_orders_address: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        """
        :param bloxroute_api_key: The bloxRoute Labs authorization header to connect with solana trader api
        :param solana_wallet_private_key: The secret key for a solana wallet
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """

        self.logger().exception("creating blox route exchange")
        self.logger().exception("api key is " + bloxroute_api_key)
        self.logger().exception("pub key is " + solana_wallet_public_key)
        self.logger().exception("private key is " + solana_wallet_private_key)
        self.logger().exception("open orders address is " + open_orders_address)

        self._auth_header = "YmUwMjRkZjYtNGJmMy00MDY0LWE4MzAtNjU4MGM3ODhkM2E4OmY1ZWVhZTgxZjcwMzE5NjQ0ZmM3ZDYwNmIxZjg1YTUz"
        self._sol_wallet_public_key = solana_wallet_public_key
        self._sol_wallet_private_key = solana_wallet_private_key
        self._trading_required = trading_required
        self._hummingbot_to_solana_id = {}
        self._open_orders_address = open_orders_address

        self._server_response = GetServerTimeResponse
        endpoint = "ws://54.161.46.25:1809/ws"
        self._provider_1: Provider = WsProvider(endpoint=endpoint, auth_header=self._auth_header, private_key=self._sol_wallet_private_key)
        self._provider_2: Provider = WsProvider(endpoint=endpoint, auth_header=self._auth_header, private_key=self._sol_wallet_private_key)

        self._trading_pairs = trading_pairs
        self._order_manager: BloxrouteOpenbookOrderDataManager = BloxrouteOpenbookOrderDataManager(
            self._provider_2, self._trading_pairs, self._sol_wallet_public_key
        )
        self._order_book_manager_connected = False
        asyncio.create_task(self._initialize_order_manager())

        super().__init__(client_config_map)
        self.real_time_balance_update = False

    async def _initialize_order_manager(self):
        await self._order_manager.start()
        self._order_book_manager_connected = True

        print("order books initialized!")

    def authenticator(self):
        return BloxrouteOpenbookAuth(
            api_key=self._auth_header, secret_key=self._sol_wallet_private_key, time_provider=self._time_synchronizer
        )

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    async def check_network(self) -> NetworkStatus:
        await self._provider_1.connect()
        await self._order_manager.start()

        try:
            self._server_response: GetServerTimeResponse = await self._provider_1.get_server_time()
            if self._server_response.timestamp:
                return NetworkStatus.CONNECTED
            else:
                return NetworkStatus.NOT_CONNECTED
        except Exception:
            return NetworkStatus.NOT_CONNECTED

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_manager_connected,
            "trading_rule_initialized": len(self._trading_rules) != 0,
        }

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        if self._order_manager.is_ready:
            price, _ = self._order_manager.get_price_with_opportunity_size(trading_pair=trading_pair, is_buy=is_buy)
            return Decimal(price)
        else:
            if not self._order_manager.started:
                asyncio.create_task(self._initialize_order_manager())
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
        raise "not implemented"

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.MARKET_PATH

    @property
    def check_network_request_path(self):
        raise Exception("not implemented")

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return "time" in str(request_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BloxrouteOpenbookAPIOrderBookDataSource(
            provider=self._provider_1, trading_pairs=self._trading_pairs, connector=self
        )

    def get_order_book(self, trading_pair: str) -> OrderBook:
        blxr_ob, timestamp = self._order_manager.get_order_book(trading_pair)
        snapshot_msg: OrderBookMessage = BloxrouteOpenbookOrderBook.snapshot_message_from_exchange(
            msg={
                "orderbook": blxr_ob,
            },
            timestamp=timestamp,
            metadata={"trading_pair": trading_pair},
        )

        ob = BloxrouteOpenbookOrderBook()
        ob.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)

        return ob

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return UserStreamTrackerDataSource()

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
    ) -> TradeFeeBase:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """

        return DeductedFromReturnsTradeFee(percent=Decimal(0))

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

        tokens = trading_pair.split("-")
        base = tokens[0]
        quote = tokens[1]

        # this is temporarily hard coded to a single solana wallet
        base_addr = CONSTANTS.TOKEN_PAIR_TO_WALLET_ADDR[base]
        quote_addr = CONSTANTS.TOKEN_PAIR_TO_WALLET_ADDR[quote]
        payer_address = base_addr if side == api.Side.S_ASK else quote_addr

        blxr_client_order_id = convert_hummingbot_to_blxr_client_order_id(order_id)
        self._hummingbot_to_solana_id[order_id] = blxr_client_order_id

        submit_order_response = await self._provider_1.submit_order(
            owner_address=self._sol_wallet_public_key,
            payer_address=payer_address,
            market=trading_pair,
            side=side,
            types=[type],
            amount=float(amount),
            price=float(price),
            project=OPENBOOK_PROJECT,
            client_order_id=blxr_client_order_id,
            open_orders_address=self._open_orders_address,
            skip_pre_flight=True,
        )

        self.logger().info(f"placed order {submit_order_response} with id {blxr_client_order_id}: {amount} @ {price}")

        return submit_order_response, time.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if order_id not in self._hummingbot_to_solana_id:
            raise Exception("placed order not found")
        blxr_client_order_id = self._hummingbot_to_solana_id[order_id]

        try:
            cancel_order_response = await self._provider_1.submit_cancel_by_client_order_i_d(
                client_order_i_d=blxr_client_order_id,
                market_address=tracked_order.trading_pair,
                owner_address=self._sol_wallet_public_key,
                open_orders_address=self._open_orders_address,
                project=OPENBOOK_PROJECT,
                skip_pre_flight=True,
            )

            self.logger().info(f"cancelled order f{cancel_order_response} with id {blxr_client_order_id}")
            return cancel_order_response != ""
        except Exception as e:
            print(e)
            return False

    async def _format_trading_rules(self, markets_by_name: Dict[str, Market]) -> List[TradingRule]:
        trading_rules = []
        for market_name in markets_by_name:
            market = markets_by_name[market_name]

            tokens = market.market.split("/")
            trading_pair = f"{tokens[0]}-{tokens[1]}"

            quantity_precision = market.base_decimals
            price_precision = market.quote_decimals
            min_order_size = Decimal(str(10**-quantity_precision))
            min_quote_amount = Decimal(str(10**-price_precision))
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
        await self._provider_1.connect()
        account_balance: GetAccountBalanceResponse = await self._provider_1.get_account_balance(
            owner_address=self._sol_wallet_public_key
        )
        for token_info in account_balance.tokens:
            symbol = token_info.symbol
            if symbol == "wSOL":
                symbol = "SOL"
            self._account_balances[symbol] = Decimal(token_info.wallet_amount + token_info.unsettled_amount)
            self._account_available_balances[symbol] = Decimal(token_info.wallet_amount)

    async def _request_order_update(self, order: InFlightOrder) -> Dict[str, Any]:
        raise Exception("request order update not yet implemented")

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        raise Exception("request order fills not yet implemented")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        blxr_client_order_i_d = convert_hummingbot_to_blxr_client_order_id(order.client_order_id)
        await asyncio.sleep(2)
        order_updates = self._order_manager.get_order_status(
            trading_pair=order.trading_pair, client_order_id=blxr_client_order_i_d
        )
        trade_updates = []
        for order_update in order_updates:
            if (
                order_update.order_status == OrderStatus.OS_FILLED
                or order_update.order_status == OrderStatus.OS_PARTIAL_FILL
            ):
                side = order_update.side
                fill_price = Decimal(order_update.fill_price)
                fill_base_amount: Decimal = Decimal(0)
                fill_quote_amount: Decimal = Decimal(0)

                if side == Side.S_ASK:
                    fill_base_amount = Decimal(order_update.quantity_released)
                    fill_quote_amount = Decimal(fill_base_amount) * fill_price
                elif side == Side.S_BID:
                    fill_quote_amount = Decimal(order_update.quantity_released)
                    fill_base_amount = Decimal(fill_quote_amount) * (1 / fill_price)

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                )
                trade_updates.append(
                    TradeUpdate(
                        trade_id=order.client_order_id,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        trading_pair=order.trading_pair,
                        fill_timestamp=order_update.timestamp,
                        fill_price=fill_price,
                        fill_base_amount=fill_base_amount,
                        fill_quote_amount=fill_quote_amount,
                        fee=fee,
                    )
                )

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        blxr_client_order_id = convert_hummingbot_to_blxr_client_order_id(tracked_order.client_order_id)
        order_status_info = self._order_manager.get_order_status(
            trading_pair=tracked_order.trading_pair, client_order_id=blxr_client_order_id
        )

        timestamp = time.time()
        order_status = OrderStatus.OS_UNKNOWN
        if len(order_status_info) != 0:
            timestamp = order_status_info[-1].timestamp
            order_status = order_status_info[-1].order_status

        new_order_status = convert_blxr_to_hummingbot_order_status(order_status)
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=timestamp,
            new_state=new_order_status,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
        )

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

            try:
                mapping[market_name] = trading_pair
            except Exception:
                pass

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
        await self._provider_1.connect()
        markets_response: GetMarketsResponse = await self._provider_1.get_markets()
        markets_by_name = markets_response.markets

        trading_rules_list = await self._format_trading_rules(markets_by_name)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        self._initialize_trading_pair_symbols_from_exchange_info(markets_by_name=markets_by_name)

    async def _initialize_trading_pair_symbol_map(self):
        await self._update_trading_rules()


def convert_hummingbot_to_blxr_client_order_id(client_order_id: str):
    num = _convert_to_number(client_order_id)
    return truncate(num, 7)


def _convert_to_number(s):
    return int.from_bytes(s.encode(), "little")


def truncate(num: int, n: int) -> int:
    num_str = str(num)
    trunc_num_str = num_str[-n:]
    return int(trunc_num_str)


def convert_blxr_to_hummingbot_order_status(order_status: api.OrderStatus) -> OrderState:
    if order_status == api.OrderStatus.OS_OPEN:
        return OrderState.OPEN
    elif order_status == api.OrderStatus.OS_PARTIAL_FILL:
        return OrderState.PARTIALLY_FILLED
    elif order_status == api.OrderStatus.OS_FILLED:
        return OrderState.FILLED
    elif order_status == api.OrderStatus.OS_CANCELLED:
        return OrderState.CANCELED
    else:
        return OrderState.PENDING_CREATE
