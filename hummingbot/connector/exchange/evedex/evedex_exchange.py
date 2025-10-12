import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.evedex import (
    evedex_constants as CONSTANTS,
    evedex_utils,
    evedex_web_utils as web_utils,
)
from hummingbot.connector.exchange.evedex.evedex_api_order_book_data_source import EvedexAPIOrderBookDataSource
from hummingbot.connector.exchange.evedex.evedex_api_user_stream_data_source import EvedexAPIUserStreamDataSource
from hummingbot.connector.exchange.evedex.evedex_auth import EvedexAuth
from hummingbot.connector.exchange_base import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class EvedexExchange(ExchangePyBase):
    """
    Main connector class for EVEDEX exchange.
    Implements all trading and account management functionality.
    """

    web_utils = web_utils

    def __init__(self,
                 evedex_api_key: str,
                 evedex_secret_key: str,
                 evedex_access_token: str,
                 evedex_chain_id: str,
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        """
        Initialize the EVEDEX exchange connector.

        :param evedex_api_key: API key for authentication
        :param evedex_secret_key: Secret key for signing requests
        :param balance_asset_limit: optional balance limits per asset
        :param rate_limits_share_pct: percentage of rate limits to use
        :param trading_pairs: list of trading pairs to track
        :param trading_required: whether trading is required
        """
        self.evedex_api_key = evedex_api_key
        self.evedex_secret_key = evedex_secret_key
        self.evedex_access_token = evedex_access_token
        self._chain_id = evedex_chain_id
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def authenticator(self):
        """Returns the authenticator for this exchange."""
        return EvedexAuth(
            api_key=self.evedex_api_key,
            secret_key=self.evedex_secret_key,
            access_token=self.evedex_access_token,
            time_provider=self._time_synchronizer
        )

    @property
    def name(self) -> str:
        """Returns the name of the exchange."""
        return "evedex"

    @property
    def rate_limits_rules(self):
        """Returns the rate limit rules for this exchange."""
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        """Returns the domain for this exchange."""
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self):
        """Returns the maximum length for client order IDs."""
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        """Returns the prefix for client order IDs."""
        return CONSTANTS.CLIENT_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        """Returns the API path for fetching trading rules."""
        return CONSTANTS.INSTRUMENTS_PATH

    @property
    def trading_pairs_request_path(self):
        """Returns the API path for fetching trading pairs."""
        return CONSTANTS.INSTRUMENTS_PATH

    @property
    def check_network_request_path(self):
        """Returns the API path for checking network connectivity."""
        return CONSTANTS.SERVER_TIME_PATH

    @property
    def trading_pairs(self):
        """Returns the list of trading pairs."""
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Returns whether cancel requests are synchronous."""
        return True

    @property
    def is_trading_required(self) -> bool:
        """Returns whether trading is required."""
        return self._trading_required

    def supported_order_types(self):
        """Returns the list of supported order types."""
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        """
        Checks if a request exception is related to time synchronization issues.

        :param request_exception: the exception to check
        :return: True if time synchronization related, False otherwise
        """
        error_description = str(request_exception)
        is_time_synchronizer_related = (
            "timestamp" in error_description.lower() or
            "recvWindow" in error_description or
            "Request timestamp" in error_description
        )
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """
        Checks if the exception indicates an order was not found.

        :param status_update_exception: the exception to check
        :return: True if order not found, False otherwise
        """
        error_description = str(status_update_exception).lower()
        return (
            "order does not exist" in error_description or
            "order not found" in error_description or
            "unknown order" in error_description
        )

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """
        Checks if the exception indicates an order was not found during cancellation.

        :param cancelation_exception: the exception to check
        :return: True if order not found, False otherwise
        """
        error_description = str(cancelation_exception).lower()
        return (
            "order does not exist" in error_description or
            "order not found" in error_description or
            "unknown order" in error_description
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Creates and returns a web assistants factory."""
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
            domain=self.domain
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """Creates and returns an order book data source."""
        return EvedexAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """Creates and returns a user stream data source."""
        return EvedexAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        """
        Calculates the fee for a trade.

        :param base_currency: base currency
        :param quote_currency: quote currency
        :param order_type: order type
        :param order_side: order side (BUY/SELL)
        :param amount: order amount
        :param price: order price
        :param is_maker: whether this is a maker order
        :return: calculated trade fee
        """
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _initialize_trading_pair_symbol_map(self):
        """Initialize the trading pair to exchange symbol mapping."""
        try:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
            )
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """
        Initialize trading pair symbols from exchange info response.

        :param exchange_info: the exchange info response
        """
        mapping = bidict()

        symbols = exchange_info if isinstance(exchange_info, list) else exchange_info.get("data", [])

        for symbol_data in filter(evedex_utils.is_exchange_information_valid, symbols):
            exchange_symbol = symbol_data.get("id") or symbol_data.get("name")
            base_info = (symbol_data.get("from") or {}).get("symbol")
            quote_info = (symbol_data.get("to") or {}).get("symbol")

            if exchange_symbol and base_info and quote_info:
                mapping[exchange_symbol] = combine_to_hb_trading_pair(base=base_info.upper(), quote=quote_info.upper())

        self._set_trading_pair_symbol_map(mapping)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        """
        Places an order on the exchange.

        :param order_id: client order ID
        :param trading_pair: trading pair
        :param amount: order amount
        :param trade_type: BUY or SELL
        :param order_type: order type (LIMIT, MARKET, etc.)
        :param price: order price
        :return: tuple of (exchange order ID, timestamp)
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        order_data = {
            "symbol": symbol,
            "side": CONSTANTS.SIDE_BUY if trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL,
            "type": CONSTANTS.ORDER_TYPE_MAP[order_type],
            "quantity": str(amount),
            "newClientOrderId": order_id,
        }

        # Add price for limit orders
        if order_type.is_limit_type():
            order_data["price"] = str(price)
            order_data["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

        # Add post-only flag for limit maker orders
        if order_type == OrderType.LIMIT_MAKER:
            order_data["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH,
            data=order_data,
            is_auth_required=True,
        )

        exchange_order_id = str(order_result.get("orderId", ""))
        timestamp = float(order_result.get("transactTime", order_result.get("timestamp", self._time() * 1000))) * 1e-3

        return exchange_order_id, timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancels an order on the exchange.

        :param order_id: client order ID
        :param tracked_order: the tracked order object
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        cancel_data = {
            "symbol": symbol,
            "origClientOrderId": order_id,
        }

        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH,
            data=cancel_data,
            is_auth_required=True,
        )

        if cancel_result.get("status") == "CANCELED":
            return True

        return False

    async def _update_trading_rules(self):
        """Updates trading rules for all trading pairs."""
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Formats exchange info into trading rules.

        :param exchange_info_dict: exchange info response
        :return: list of trading rules
        """
        trading_rules: List[TradingRule] = []
        symbols = exchange_info_dict if isinstance(exchange_info_dict, list) else exchange_info_dict.get("data", [])

        for rule in filter(evedex_utils.is_exchange_information_valid, symbols):
            try:
                exchange_symbol = rule.get("id") or rule.get("name")
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=exchange_symbol)

                quantity_increment_raw = rule.get("quantityIncrement") or "1"
                min_quantity_raw = rule.get("minQuantity") or "0"
                max_quantity_raw = rule.get("maxQuantity") or "0"

                quantity_increment = Decimal(str(quantity_increment_raw))
                min_quantity = Decimal(str(min_quantity_raw))
                max_quantity = Decimal(str(max_quantity_raw))

                quote_precision = (rule.get("to") or {}).get("precision")
                price_step = Decimal("1") / (Decimal("10") ** quote_precision) if quote_precision is not None else Decimal("0.0001")

                min_price_raw = rule.get("minPrice") or "0"
                min_price = Decimal(str(min_price_raw))
                min_notional = min_price * min_quantity

                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_quantity,
                        max_order_size=max_quantity,
                        min_price_increment=price_step,
                        min_base_amount_increment=quantity_increment,
                        min_notional_size=min_notional,
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing trading rule for {exchange_symbol}")

        return trading_rules

    async def _update_balances(self):
        """Updates account balances from the exchange."""
        account_info = await self._api_get(
            path_url=CONSTANTS.BALANCE_PATH,
            is_auth_required=True,
        )

        # Handle different possible response formats
        balances = account_info.get("balances", account_info.get("data", []))

        self._account_balances.clear()
        self._account_available_balances.clear()

        for balance_entry in balances:
            asset = balance_entry.get("asset", balance_entry.get("currency", ""))
            total_balance = Decimal(balance_entry.get("free", "0")) + Decimal(balance_entry.get("locked", "0"))
            available_balance = Decimal(balance_entry.get("free", "0"))

            self._account_balances[asset] = total_balance
            self._account_available_balances[asset] = available_balance

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Requests the status of an order from the exchange.

        :param tracked_order: the order to check
        :return: OrderUpdate with current status
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        order_status_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH,
            params={
                "symbol": symbol,
                "origClientOrderId": tracked_order.client_order_id,
            },
            is_auth_required=True,
        )

        return self._create_order_update_from_order_status_data(order_status_data, tracked_order)

    def _create_order_update_from_order_status_data(
            self,
            order_status_data: Dict[str, Any],
            tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Creates an OrderUpdate from order status data.

        :param order_status_data: order status response
        :param tracked_order: the tracked order
        :return: OrderUpdate object
        """
        exchange_order_id = str(order_status_data.get("orderId", ""))
        new_state = CONSTANTS.ORDER_STATE.get(order_status_data.get("status"), OrderState.OPEN)

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(order_status_data.get("updateTime", self._time() * 1000)) * 1e-3,
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
        )

        return order_update

    async def _user_stream_event_listener(self):
        """Listens to user stream events and processes them."""
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e", event_message.get("event", ""))

                if "order" in event_type.lower() or event_message.get("eventType") == "executionReport":
                    await self._process_order_event(event_message)
                elif "account" in event_type.lower() or "outboundAccountPosition" in event_type:
                    await self._process_account_event(event_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener")

    async def _process_order_event(self, order_event: Dict[str, Any]):
        """
        Processes an order update event from the user stream.

        :param order_event: the order event data
        """
        client_order_id = order_event.get("c", order_event.get("clientOrderId", ""))
        tracked_order = self._order_tracker.fetch_order(client_order_id=client_order_id)

        if tracked_order is not None:
            order_update = self._create_order_update_from_order_event(order_event, tracked_order)
            self._order_tracker.process_order_update(order_update)

    def _create_order_update_from_order_event(
            self,
            order_event: Dict[str, Any],
            tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Creates an OrderUpdate from an order event.

        :param order_event: the order event data
        :param tracked_order: the tracked order
        :return: OrderUpdate object
        """
        exchange_order_id = str(order_event.get("i", order_event.get("orderId", "")))
        new_state = CONSTANTS.ORDER_STATE.get(order_event.get("X", order_event.get("orderStatus")), OrderState.OPEN)

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(order_event.get("T", order_event.get("timestamp", self._time() * 1000))) * 1e-3,
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
        )

        return order_update

    async def _process_account_event(self, account_event: Dict[str, Any]):
        """
        Processes an account update event from the user stream.

        :param account_event: the account event data
        """
        # Trigger balance update
        balances = account_event.get("B", account_event.get("balances", []))

        for balance_entry in balances:
            asset = balance_entry.get("a", balance_entry.get("asset", ""))
            total_balance = Decimal(balance_entry.get("f", "0")) + Decimal(balance_entry.get("l", "0"))
            available_balance = Decimal(balance_entry.get("f", "0"))

            self._account_balances[asset] = total_balance
            self._account_available_balances[asset] = available_balance

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Fetches all trade updates for a specific order.

        :param order: the order to fetch trades for
        :return: list of TradeUpdate objects
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)

        trades_data = await self._api_get(
            path_url=CONSTANTS.MY_TRADES_PATH,
            params={
                "symbol": symbol,
                "orderId": order.exchange_order_id,
            },
            is_auth_required=True,
        )

        trade_updates = []

        for trade in trades_data:
            trade_update = TradeUpdate(
                trade_id=str(trade.get("id", "")),
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                fill_timestamp=float(trade.get("time", self._time() * 1000)) * 1e-3,
                fill_price=Decimal(trade.get("price", "0")),
                fill_base_amount=Decimal(trade.get("qty", "0")),
                fill_quote_amount=Decimal(trade.get("quoteQty", "0")),
                fee=TokenAmount(
                    amount=Decimal(trade.get("commission", "0")),
                    token=trade.get("commissionAsset", "")
                ),
            )
            trade_updates.append(trade_update)

        return trade_updates

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Gets the last traded price for a trading pair.

        :param trading_pair: the trading pair
        :return: last traded price
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        ticker_data = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_PATH,
            params={"symbol": symbol}
        )

        return float(ticker_data.get("lastPrice", ticker_data.get("price", 0)))

    async def _update_trading_fees(self):
        """
        Updates trading fees from the exchange.
        EVEDEX uses fixed fee structure, so this is a no-op.
        Fees are configured in evedex_utils.py DEFAULT_FEES.
        """
        pass
