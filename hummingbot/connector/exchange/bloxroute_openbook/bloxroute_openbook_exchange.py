import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict
from bxsolana.transaction import load_private_key, signing
from bxsolana_trader_proto import GetMarketsResponse, api

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.bloxroute_openbook import (
    bloxroute_openbook_constants as constants,
    bloxroute_openbook_web_utils as web_utils,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_api_order_book_data_source import (
    BloxrouteOpenbookAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import (
    MAINNET_PROVIDER_ENDPOINT,
    TESTNET_PROVIDER_ENDPOINT,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_book import BloxrouteOpenbookOrderBook
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_data_manager import (
    BloxrouteOpenbookOrderDataManager,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_provider import BloxrouteOpenbookProvider
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_utils import (
    convert_blxr_order_status,
    convert_hbot_client_order_id,
    convert_hbot_order_type,
    convert_hbot_trade_type,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class BloxrouteOpenbookExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        bloxroute_auth_header: str,
        solana_wallet_private_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        """
        :param bloxroute_auth_header: The bloXroute Labs authorization header to connect with the Solana Trader API
        :param solana_wallet_private_key: The secret key for your Solana wallet
        :param trading_pairs: The market trading pairs used for a strategy
        :param trading_required: Whether actual trading is needed
        """
        self.logger().info("Creating bloXroute exchange")

        self._trading_required = trading_required
        self._auth_header = bloxroute_auth_header
        self._sol_wallet_private_key = solana_wallet_private_key

        self._key_pair = load_private_key(self._sol_wallet_private_key)
        self._sol_wallet_public_key = str(self._key_pair.public_key)

        self._order_id_mapper: Dict[str, int] = {}  # maps Hummingbot to bloXroute order id
        self._open_orders_address_mapper: Dict[str, str] = {}  # maps trading pair to open orders address

        self._testnet_provider = BloxrouteOpenbookProvider(
            endpoint=TESTNET_PROVIDER_ENDPOINT, auth_header=self._auth_header, private_key=self._sol_wallet_private_key
        )
        self._mainnet_provider = BloxrouteOpenbookProvider(
            endpoint=MAINNET_PROVIDER_ENDPOINT,
            auth_header="YmUwMjRkZjYtNGJmMy00MDY0LWE4MzAtNjU4MGM3ODhkM2E4OmY1ZWVhZTgxZjcwMzE5NjQ0ZmM3ZDYwNmIxZjg1YTUz",
            private_key=self._sol_wallet_private_key,
        )

        self._token_accounts: Dict[str, str] = {}

        self._trading_pairs = trading_pairs
        asyncio.create_task(self._initialize_token_accounts())

        self._order_manager: BloxrouteOpenbookOrderDataManager = BloxrouteOpenbookOrderDataManager(
            self._mainnet_provider, self._trading_pairs, self._sol_wallet_public_key
        )
        asyncio.create_task(self._initialize_order_manager())

        super().__init__(client_config_map)

    async def _initialize_token_accounts(self):
        await self._testnet_provider.wait_connect()

        token_accounts_response = await self._testnet_provider.get_token_accounts(
            owner_address=self._sol_wallet_public_key
        )
        token_account_dict = {token.symbol: token.token_account for token in token_accounts_response.accounts}
        for trading_pair in self._trading_pairs:
            tokens = trading_pair.split("-")
            if len(tokens) != 2:
                raise Exception(f"trading pair {trading_pair} does not contain `-` seperator")

            found = True
            for token in tokens:
                if token not in self._token_accounts:
                    if token not in token_account_dict:
                        found = False
                        break
                    self._token_accounts[token] = token_account_dict[token]
            if not found:
                raise Exception(f"could not find token accounts for trading pair {trading_pair}")

    async def _initialize_order_manager(self):
        await self._testnet_provider.wait_connect()
        await self._order_manager.start()
        await self._order_manager.ready()

    @property
    def name(self) -> str:
        return constants.EXCHANGE_NAME

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "provider_connected": self._testnet_provider.connected,
            "order_manager_initialized": self._order_manager.is_ready,
            "account_balance": not self.is_trading_required or len(self._account_balances) > 0,
            "trading_rules_initialized": len(self._trading_rules) != 0,
            "token_accounts_initialized": len(self._token_accounts) != 0,
        }

    @property
    def rate_limits_rules(self):
        return []

    @property
    def domain(self):
        return ""

    @property
    def client_order_id_max_length(self):
        return constants.CLIENT_ORDER_ID_MAX_LENGTH

    @property
    def client_order_id_prefix(self):
        return ""

    @property
    def trading_rules_request_path(self):
        raise "not implemented"

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def trading_pairs_request_path(self) -> str:
        return ""

    @property
    def check_network_request_path(self) -> str:
        return ""

    def _api_request(
        self,
        path_url,
        overwrite_url: Optional[str] = None,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def authenticator(self):
        return AuthBase()

    async def check_network(self) -> NetworkStatus:
        await self._testnet_provider.wait_connect()
        await self._order_manager.ready()

        try:
            server_response: api.GetServerTimeResponse = await self._testnet_provider.get_server_time()
            if server_response.timestamp:
                return NetworkStatus.CONNECTED
            else:
                return NetworkStatus.NOT_CONNECTED
        except Exception:
            return NetworkStatus.NOT_CONNECTED

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        if self._order_manager.is_ready:
            price, _ = self._order_manager.get_price_with_opportunity_size(trading_pair=trading_pair, is_buy=is_buy)
            return Decimal(price)
        else:
            return Decimal(0)

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT]

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        pass

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return "time" in str(request_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return WebAssistantsFactory(throttler=AsyncThrottler([]))

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BloxrouteOpenbookAPIOrderBookDataSource(
            provider=self._testnet_provider, trading_pairs=self._trading_pairs, connector=self
        )

    def get_order_book(self, trading_pair: str) -> OrderBook:
        blxr_ob, timestamp = self._order_manager.get_order_book(trading_pair)

        ob = BloxrouteOpenbookOrderBook()
        ob.apply_orderbook_snapshot(blxr_ob, timestamp)

        return ob

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return UserStreamTrackerDataSource()

    def _is_user_stream_initialized(self):
        return True

    def _create_user_stream_tracker(self):
        return None

    def _create_user_stream_tracker_task(self):
        return None

    async def _user_stream_event_listener(self):
        pass

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
        blxr_order_type = convert_hbot_order_type(order_type)
        blxr_side = convert_hbot_trade_type(trade_type)

        tokens = trading_pair.split("-")
        base = tokens[0]
        quote = tokens[1]

        payer_address = self._payer_address(base, quote, blxr_side)
        open_orders_address = self._open_orders_address_mapper.get(trading_pair, "")

        blxr_client_order_id = convert_hbot_client_order_id(order_id)
        self._order_id_mapper[order_id] = blxr_client_order_id

        await self._testnet_provider.wait_connect()
        post_order_response = await self._testnet_provider.post_order(
            owner_address=self._sol_wallet_public_key,
            payer_address=payer_address,
            market=trading_pair,
            side=blxr_side,
            type=[blxr_order_type],
            amount=float(amount),
            price=float(price),
            open_orders_address=open_orders_address,
            client_order_i_d=blxr_client_order_id,
            project=constants.SPOT_ORDERBOOK_PROJECT,
        )

        signed_tx = signing.sign_tx_with_private_key(post_order_response.transaction.content, self._key_pair)
        post_submit_response = await self._testnet_provider.post_submit(
            transaction=api.TransactionMessage(content=signed_tx),
            skip_pre_flight=True,
        )

        if open_orders_address == "":
            self._open_orders_address_mapper[trading_pair] = post_order_response.open_orders_address

        return post_submit_response.signature, time.time()

    def _payer_address(self, base, quote, blxr_side):
        if blxr_side == api.Side.S_ASK:
            return self._token_accounts[base]
        return self._token_accounts[quote]

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        blxr_client_order_id = convert_hbot_client_order_id(order_id)
        if tracked_order.trading_pair not in self._open_orders_address_mapper:
            raise Exception("have to place an order before cancelling it")
        open_orders_address = self._open_orders_address_mapper[tracked_order.trading_pair]

        await self._testnet_provider.wait_connect()
        try:
            await self._testnet_provider.submit_cancel_by_client_order_i_d(
                owner_address=self._sol_wallet_public_key,
                market_address=tracked_order.trading_pair,
                open_orders_address=open_orders_address,
                client_order_i_d=blxr_client_order_id,
                project=constants.SPOT_ORDERBOOK_PROJECT,
                skip_pre_flight=True,
            )
        except Exception:
            return False

        return True

    async def _format_trading_rules(self, markets_by_name: Dict[str, api.Market]) -> List[TradingRule]:
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

    async def _update_balances(self):
        await self._testnet_provider.wait_connect()
        account_balance = await self._testnet_provider.get_account_balance(owner_address=self._sol_wallet_public_key)
        for token_info in account_balance.tokens:
            symbol = token_info.symbol
            if symbol == "wSOL":
                symbol = "SOL"
            self._account_balances[symbol] = Decimal(token_info.settled_amount + token_info.unsettled_amount)
            self._account_available_balances[symbol] = Decimal(token_info.settled_amount)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        blxr_client_order_i_d = convert_hbot_client_order_id(order.client_order_id)
        order_updates = self._order_manager.get_order_statuses(
            trading_pair=order.trading_pair, client_order_id=blxr_client_order_i_d
        )
        trade_updates = []
        for order_update in order_updates:
            if (
                order_update.order_status == api.OrderStatus.OS_FILLED
                or order_update.order_status == api.OrderStatus.OS_PARTIAL_FILL
            ):
                side = order_update.side
                fill_price = Decimal(order_update.fill_price)
                fill_base_amount: Decimal = Decimal(0)
                fill_quote_amount: Decimal = Decimal(0)

                if side == api.Side.S_ASK:
                    fill_base_amount = Decimal(order_update.quantity_released)
                    fill_quote_amount = Decimal(fill_base_amount) * fill_price
                elif side == api.Side.S_BID:
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
        blxr_client_order_id = convert_hbot_client_order_id(tracked_order.client_order_id)
        order_status_info = self._order_manager.get_order_statuses(
            trading_pair=tracked_order.trading_pair, client_order_id=blxr_client_order_id
        )

        timestamp = 0
        order_status = api.OrderStatus.OS_UNKNOWN
        if len(order_status_info) != 0:
            timestamp = order_status_info[-1].timestamp
            order_status = order_status_info[-1].order_status

        new_order_status = convert_blxr_order_status(order_status)
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=timestamp,
            new_state=new_order_status,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, markets_by_name: Dict[str, api.Market]):
        mapping = bidict()

        for market_name in markets_by_name:
            # format is 1SP/USDC-P_OPENBOOK

            token_pair = market_name.split("-")
            tokens = token_pair[0].split("/")
            base = tokens[0]
            quote = tokens[1]
            trading_pair = f"{base}-{quote}"

            try:
                mapping[market_name] = trading_pair
            except Exception:
                pass

        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        price, _ = self._order_manager.get_price_with_opportunity_size(trading_pair=trading_pair, is_buy=False)
        return price

    async def _update_trading_rules(self):
        await self._testnet_provider.wait_connect()
        markets_response: GetMarketsResponse = await self._testnet_provider.get_markets()
        markets_by_name = markets_response.markets

        trading_rules_list = await self._format_trading_rules(markets_by_name)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

        self._initialize_trading_pair_symbols_from_exchange_info(markets_by_name=markets_by_name)

    async def _initialize_trading_pair_symbol_map(self):
        await self._update_trading_rules()

    async def _update_trading_fees(self):
        pass
