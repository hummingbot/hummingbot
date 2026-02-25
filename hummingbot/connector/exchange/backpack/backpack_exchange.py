"""Backpack exchange connector for Hummingbot."""
from typing import TYPE_CHECKING

from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.connector.exchange.backpack.backpack_constants import (
    DEFAULT_DOMAIN,
    HBOT_ORDER_ID_PREFIX,
    MAX_ORDER_ID_LEN,
)
from hummingbot.connector.exchange.backpack.backpack_utils import (
    convert_order_side,
    convert_order_type,
    convert_time_in_force,
    get_backpack_trading_pair,
    get_hummingbot_trading_pair,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import (
    OrderType,
    TradeType,
)
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class BackpackExchange(ExchangePyBase):
    """
    BackpackExchange connects with Backpack Exchange and provides order book pricing, user account tracking and
    trading functionality.
    """

    API_VERSION = "v1"

    web_utils = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = HummingbotLogger(__name__)
        return s_logger

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        backpack_api_key: str,
        backpack_secret_key: str,
        trading_pairs: list[str] = None,
        trading_required: bool = True,
        domain: str = DEFAULT_DOMAIN,
    ):
        """
        Initializes the BackpackExchange.

        :param client_config_map: The client configuration map
        :param backpack_api_key: The API key for Backpack authentication
        :param backpack_secret_key: The secret key for Backpack authentication
        :param trading_pairs: A list of trading pairs to track
        :param trading_required: Whether trading is required
        :param domain: The domain for the Backpack API (default: "com")
        """
        self._api_key = backpack_api_key
        self._secret_key = backpack_secret_key
        self._domain = domain
        self._trading_required = trading_required
        super().__init__(client_config_map)
        self._real_time_balance_update = False
        self._auth = BackpackAuth(api_key=self._api_key, secret_key=self._secret_key)

    @staticmethod
    def backpack_order_id(client_order_id: str) -> str:
        """
        Converts a Hummingbot client order ID to a Backpack-compatible order ID.

        Backpack order IDs have a maximum length and specific format requirements.
        """
        if len(client_order_id) > MAX_ORDER_ID_LEN - len(HBOT_ORDER_ID_PREFIX):
            client_order_id = client_order_id[:MAX_ORDER_ID_LEN - len(HBOT_ORDER_ID_PREFIX)]
        return f"{HBOT_ORDER_ID_PREFIX}{client_order_id}"

    @property
    def authenticator(self) -> BackpackAuth:
        return self._auth

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "backpack"
        return f"backpack_{self._domain}"

    @property
    def rate_limits_rules(self):
        from hummingbot.connector.exchange.backpack.backpack_constants import RATE_LIMITS
        return RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return "/api/v1/markets"

    @property
    def trading_pairs_request_path(self) -> str:
        return "/api/v1/markets"

    @property
    def check_network_request_path(self) -> str:
        return "/api/v1/ping"

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> list[OrderType]:
        """
        Returns the order types supported by Backpack.
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    async def get_all_pairs_prices(self) -> dict[str, float]:
        """
        Fetches the current prices for all trading pairs.
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        params = {}
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url="/api/v1/tickers", domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id="/api/v1/tickers",
        )
        
        prices = {}
        for ticker in data:
            trading_pair = get_hummingbot_trading_pair(ticker.get("symbol"))
            if trading_pair:
                prices[trading_pair] = float(ticker.get("lastPrice", 0))
        return prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """
        Checks if a request exception is related to time synchronization.
        """
        error_description = str(request_exception)
        return "Timestamp" in error_description or "timestamp" in error_description

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """
        Checks if an order was not found during a status update.
        """
        error_description = str(status_update_exception)
        return "Order not found" in error_description or "order not found" in error_description.lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """
        Checks if an order was not found during cancellation.
        """
        error_description = str(cancelation_exception)
        return "Order not found" in error_description or "order not found" in error_description.lower()

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        from hummingbot.connector.exchange.backpack.backpack_api_order_book_data_source import (
            BackpackAPIOrderBookDataSource,
        )
        return BackpackAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._api_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        from hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source import (
            BackpackAPIUserStreamDataSource,
        )
        return BackpackAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._api_factory,
            domain=self._domain,
        )

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: float, price: float = 0.0, is_maker: bool = False) -> float:
        """
        Calculates the trading fee for an order.
        Backpack uses a maker/taker fee model.
        """
        # Backpack fees: 0.02% maker, 0.05% taker (can vary based on volume)
        fee_percent = 0.0002 if is_maker else 0.0005
        return fee_percent * amount * price if price else fee_percent * amount

    async def _initialize_trading_pair_symbol_map(self):
        """
        Initializes the mapping between Hummingbot trading pairs and Backpack symbols.
        """
        try:
            exchange_info = await self._request_exchange_info()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().exception(f"Error initializing trading pair symbol map: {e}")
            raise

    async def _request_exchange_info(self) -> dict:
        """
        Requests exchange information from Backpack.
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url="/api/v1/markets", domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id="/api/v1/markets",
        )
        return data

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: dict):
        """
        Initializes the trading pair symbol mapping from exchange info.
        """
        mapping = {}
        for market in exchange_info:
            symbol = market.get("symbol")
            if symbol:
                trading_pair = get_hummingbot_trading_pair(symbol)
                if trading_pair:
                    mapping[trading_pair] = symbol
        self._set_trading_pair_symbol_map(mapping)

    async def _update_trading_rules(self):
        """
        Updates the trading rules for all trading pairs.
        """
        exchange_info = await self._request_exchange_info()
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, exchange_info: dict) -> list[TradingRule]:
        """
        Formats the trading rules from exchange information.
        """
        trading_rules = []
        
        for market_info in exchange_info:
            try:
                symbol = market_info.get("symbol")
                if symbol is None:
                    continue
                    
                trading_pair = get_hummingbot_trading_pair(symbol)
                if trading_pair is None:
                    continue

                # Extract trading rules from market info
                min_order_size = float(market_info.get("filters", {}).get("minQuantity", 0))
                max_order_size = float(market_info.get("filters", {}).get("maxQuantity", float("inf")))
                min_price_increment = float(market_info.get("filters", {}).get("tickSize", 0))
                min_base_amount_increment = float(market_info.get("filters", {}).get("stepSize", 0))
                min_notional_size = float(market_info.get("filters", {}).get("minNotional", 0))

                trading_rule = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size,
                    max_order_size=max_order_size,
                    min_price_increment=min_price_increment,
                    min_base_amount_increment=min_base_amount_increment,
                    min_notional_size=min_notional_size,
                )
                trading_rules.append(trading_rule)
            except Exception as e:
                self.logger().error(f"Error parsing trading rule for {market_info.get('symbol')}: {e}")
                
        return trading_rules

    async def _status_polling_loop_fetch_updates(self):
        """
        Fetches updates for orders and balances.
        """
        await self._update_order_fills_from_trades()
        await super()._status_polling_loop_fetch_updates()

    async def _update_balances(self):
        """
        Updates the account balances.
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.private_rest_url(path_url="/api/v1/capital", domain=self._domain),
            method=RESTMethod.GET,
            throttler_limit_id="/api/v1/capital",
            headers=self._auth.header_for_authentication(),
        )
        
        self._account_available_balances.clear()
        self._account_balances.clear()
        
        for balance in data:
            asset = balance.get("asset")
            if asset:
                available = float(balance.get("available", 0))
                locked = float(balance.get("locked", 0))
                self._account_available_balances[asset] = available
                self._account_balances[asset] = available + locked

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: float,
        trade_type: TradeType,
        order_type: OrderType,
        price: float,
        **kwargs,
    ) -> tuple[str, float]:
        """
        Places an order on Backpack.
        
        Returns a tuple of (exchange_order_id, timestamp).
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        api_params = {
            "symbol": symbol,
            "side": convert_order_side(trade_type),
            "orderType": convert_order_type(order_type),
            "quantity": str(amount),
        }
        
        if order_type != OrderType.MARKET:
            api_params["price"] = str(price)
            
        if "time_in_force" in kwargs:
            api_params["timeInForce"] = convert_time_in_force(kwargs["time_in_force"])
            
        if "client_order_id" in kwargs:
            api_params["clientId"] = self.backpack_order_id(kwargs["client_order_id"])

        rest_assistant = await self._api_factory.get_rest_assistant()
        
        # Sign the request
        url = web_utils.private_rest_url(path_url="/api/v1/order", domain=self._domain)
        signed_request = self._auth.add_auth_to_params(
            params=api_params,
            url=url,
            method="POST",
        )
        
        data = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=signed_request,
            throttler_limit_id="/api/v1/order",
            headers=self._auth.header_for_authentication(),
        )
        
        exchange_order_id = str(data.get("id"))
        timestamp = float(data.get("createdAt", 0)) / 1000  # Convert ms to seconds
        
        return exchange_order_id, timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancels an order on Backpack.
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        
        api_params = {
            "symbol": symbol,
        }
        
        # Try to cancel by exchange order ID first, then by client order ID
        if tracked_order.exchange_order_id:
            api_params["orderId"] = tracked_order.exchange_order_id
        else:
            api_params["clientId"] = self.backpack_order_id(tracked_order.client_order_id)

        rest_assistant = await self._api_factory.get_rest_assistant()
        
        url = web_utils.private_rest_url(path_url="/api/v1/order", domain=self._domain)
        signed_request = self._auth.add_auth_to_params(
            params=api_params,
            url=url,
            method="DELETE",
        )
        
        await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.DELETE,
            params=signed_request,
            throttler_limit_id="/api/v1/order",
            headers=self._auth.header_for_authentication(),
        )

    async def _get_all_fills(self, start_time: float = None, end_time: float = None) -> list[dict]:
        """
        Gets all fill history.
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        params = {}
        if start_time:
            params["startTime"] = int(start_time * 1000)
        if end_time:
            params["endTime"] = int(end_time * 1000)
            
        rest_assistant = await self._api_factory.get_rest_assistant()
        
        url = web_utils.private_rest_url(path_url="/api/v1/fills", domain=self._domain)
        signed_params = self._auth.add_auth_to_params(
            params=params,
            url=url,
            method="GET",
        )
        
        data = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params=signed_params,
            throttler_limit_id="/api/v1/fills",
            headers=self._auth.header_for_authentication(),
        )
        
        return data if isinstance(data, list) else []

    async def _get_order_status(self, exchange_order_id: str, trading_pair: str) -> dict:
        """
        Gets the status of an order.
        """
        from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
        
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        
        params = {
            "symbol": symbol,
            "orderId": exchange_order_id,
        }
        
        rest_assistant = await self._api_factory.get_rest_assistant()
        
        url = web_utils.private_rest_url(path_url="/api/v1/order", domain=self._domain)
        signed_params = self._auth.add_auth_to_params(
            params=params,
            url=url,
            method="GET",
        )
        
        data = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            params=signed_params,
            throttler_limit_id="/api/v1/order",
            headers=self._auth.header_for_authentication(),
        )
        
        return data

    async def _update_order_fills_from_trades(self):
        """
        Updates order fills from trade history.
        """
        # Implementation for updating fills from trades
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> list[dict]:
        """
        Gets all trade updates for a specific order.
        """
        # Implementation for getting trade updates
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderState:
        """
        Requests the current status of an order from the exchange.
        """
        order_status = await self._get_order_status(
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
        )
        
        status = order_status.get("status")
        return self._parse_order_status(status)

    def _parse_order_status(self, status: str) -> OrderState:
        """
        Parses the order status from Backpack to Hummingbot OrderState.
        """
        from hummingbot.connector.exchange.backpack.backpack_constants import ORDER_STATE
        return ORDER_STATE.get(status, OrderState.PENDING_CREATE)

    def _get_trading_pair_from_market_info(self, market_info: dict) -> str:
        """
        Extracts the trading pair from market info.
        """
        symbol = market_info.get("symbol")
        return get_hummingbot_trading_pair(symbol) if symbol else None

    def _get_markets_info_from_exchange_info(self, exchange_info: dict) -> list[dict]:
        """
        Extracts market info from exchange info.
        """
        return exchange_info if isinstance(exchange_info, list) else []
