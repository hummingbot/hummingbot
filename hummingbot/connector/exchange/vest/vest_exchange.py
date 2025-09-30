import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.vest import vest_constants as CONSTANTS, vest_utils, vest_web_utils as web_utils
from hummingbot.connector.exchange.vest.vest_api_order_book_data_source import VestAPIOrderBookDataSource
from hummingbot.connector.exchange.vest.vest_api_user_stream_data_source import VestAPIUserStreamDataSource
from hummingbot.connector.exchange.vest.vest_auth import VestAuth
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
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class VestExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 vest_api_key: str,
                 vest_primary_address: str,
                 vest_signing_address: str,
                 vest_private_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 vest_environment: str = "prod"):
        self.vest_api_key = vest_api_key
        self.vest_primary_address = vest_primary_address
        self.vest_signing_address = vest_signing_address
        self.vest_private_key = vest_private_key
        self.vest_environment = vest_environment
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map)

    @property
    def authenticator(self):
        return VestAuth(
            api_key=self.vest_api_key,
            primary_address=self.vest_primary_address,
            signing_address=self.vest_signing_address,
            private_key=self.vest_private_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "vest"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return CONSTANTS.get_vest_base_url(self.vest_environment)

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.CLIENT_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.VEST_EXCHANGE_INFO_PATH

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.VEST_EXCHANGE_INFO_PATH

    @property
    def check_network_request_path(self):
        return CONSTANTS.VEST_EXCHANGE_INFO_PATH

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = 'timestamp' in error_description.lower()
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        error_description = str(status_update_exception)
        return "not found" in error_description.lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        error_description = str(cancelation_exception)
        return "not found" in error_description.lower()

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
            environment=self.vest_environment)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return VestAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return VestAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:

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
        try:
            self.logger().info("VEST: Requesting exchange info for symbol mapping...")
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
            )
            self.logger().info(f"VEST: Received exchange info with {len(exchange_info.get('symbols', []))} symbols")
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().error(f"VEST: Error requesting exchange info: {e}", exc_info=True)
            # Create a fallback mapping if exchange info fails
            self._create_fallback_symbol_mapping()

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        symbols_count = 0

        for symbol_data in filter(vest_utils.is_exchange_information_valid, exchange_info.get("symbols", [])):
            symbols_count += 1
            # For Vest Markets, symbols are like BTC-PERP, ETH-USD-PERP
            symbol = symbol_data["symbol"]

            # Handle VEST's symbol format
            if "base" in symbol_data and "quote" in symbol_data:
                # Use API provided base/quote if available
                base_asset = symbol_data["base"]
                quote_asset = symbol_data["quote"]
            else:
                # Parse symbol manually for PERP and other formats
                base_asset, quote_asset = self._parse_vest_symbol(symbol)

            hb_trading_pair = combine_to_hb_trading_pair(base=base_asset, quote=quote_asset)
            mapping[symbol] = hb_trading_pair

            self.logger().info(f"VEST symbol mapping: {symbol} -> {hb_trading_pair} (base: {base_asset}, quote: {quote_asset})")

        self.logger().info(f"VEST initialized {len(mapping)} trading pairs from {symbols_count} valid symbols")
        self._set_trading_pair_symbol_map(mapping)

    def _create_fallback_symbol_mapping(self):
        """
        Create a fallback symbol mapping for common VEST trading pairs
        when exchange info request fails.
        Based on actual VEST API symbols.
        """
        self.logger().warning("VEST: Creating fallback symbol mapping")
        fallback_symbols = {
            # Major crypto PERP contracts (actual VEST symbols)
            "BTC-PERP": "BTC-USDC",   # BTC perpetual -> BTC-USDC in HB
            "ETH-PERP": "ETH-USDC",   # ETH perpetual -> ETH-USDC in HB
            "SOL-PERP": "SOL-USDC",   # SOL perpetual -> SOL-USDC in HB
            "AVAX-PERP": "AVAX-USDC",  # AVAX perpetual -> AVAX-USDC in HB
            "XRP-PERP": "XRP-USDC",   # XRP perpetual -> XRP-USDC in HB
            "AAVE-PERP": "AAVE-USDC",  # AAVE perpetual -> AAVE-USDC in HB

            # Common stock/forex PERP contracts
            "AMZN-USD-PERP": "AMZN-USDC",
            "GOOGL-USD-PERP": "GOOGL-USDC",
            "TSLA-USD-PERP": "TSLA-USDC",
            "EUR-USD-PERP": "EUR-USDC",
            "JPM-USD-PERP": "JPM-USDC",
        }

        mapping = bidict(fallback_symbols)
        self.logger().info(f"VEST fallback mapping created with {len(mapping)} pairs")
        self._set_trading_pair_symbol_map(mapping)

    def _parse_vest_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        Parse VEST symbol format to extract base and quote assets.

        Examples:
        - BTC-PERP -> (BTC, USDC)  # VEST uses USDC settlement for PERP
        - ETH-PERP -> (ETH, USDC)
        - SOL-PERP -> (SOL, USDC)
        - ETH-USD-PERP -> (ETH, USDC)
        """
        if symbol.endswith("-PERP"):
            # Handle perpetual contracts - VEST uses USDC settlement
            base_part = symbol[:-5]  # Remove "-PERP"
            if "-" in base_part:
                # Handle cases like "ETH-USD-PERP" or "AMZN-USD-PERP"
                parts = base_part.split("-")
                if len(parts) == 2:
                    # For stock/forex: "AMZN-USD-PERP" -> (AMZN, USDC)
                    # For crypto: "BTC-USD-PERP" -> (BTC, USDC)
                    return parts[0], "USDC"
                else:
                    return parts[0], "USDC"  # Default to USDC for complex cases
            else:
                # Handle cases like "BTC-PERP", "SOL-PERP"
                return base_part, "USDC"  # VEST uses USDC settlement
        else:
            # Handle non-PERP pairs (rare in VEST, mostly PERP contracts)
            if "-" in symbol:
                parts = symbol.split("-")
                if len(parts) == 2:
                    return parts[0], parts[1]
                else:
                    # Handle complex cases, assume USDC settlement
                    return parts[0], "USDC"
            else:
                # Fallback for unexpected formats - assume USDC
                return symbol, "USDC"

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:

        data = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "isBuy": trade_type == TradeType.BUY,
            "size": str(amount),
            "orderType": CONSTANTS.ORDER_TYPE_MAP[order_type],
            "time": int(self.current_timestamp * 1000),  # Convert to milliseconds
            "nonce": int(self.current_timestamp * 1000000),  # Microsecond precision nonce
        }

        if order_type.is_limit_type():
            data["limitPrice"] = str(price)
            if order_type == OrderType.LIMIT_MAKER:
                data["timeInForce"] = "GTC"  # Good Till Cancel for post-only
        # Market orders don't need limitPrice

        exchange_order_id = await self._api_request(
            path_url=CONSTANTS.VEST_ORDERS_PATH,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.VEST_ORDERS_PATH,
        )

        if "id" not in exchange_order_id:
            raise IOError(f"Error submitting order {order_id}: {exchange_order_id}")
        return str(exchange_order_id["id"]), self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        This implementation specific function is called by _cancel, and returns True if successful
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()

        data = {
            "order": {
                "time": int(self.current_timestamp * 1000),  # Convert to milliseconds
                "nonce": int(self.current_timestamp * 1000000),  # Microsecond precision nonce
                "id": exchange_order_id
            }
        }

        cancel_result = await self._api_request(
            path_url=f"{CONSTANTS.VEST_ORDERS_PATH}/cancel",
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
        )

        return "id" in cancel_result or "not found" in str(cancel_result).lower()

    async def get_last_traded_prices(self, trading_pairs: List[str] = None) -> Dict[str, float]:
        result = {}
        try:
            tickers = await self._api_get(
                path_url=CONSTANTS.VEST_TICKER_PATH,
            )
            for ticker in tickers.get("tickers", []):
                symbol = ticker["symbol"]
                if symbol in self._trading_pair_symbol_map:
                    hb_trading_pair = self._trading_pair_symbol_map[symbol]
                    if trading_pairs is None or hb_trading_pair in trading_pairs:
                        result[hb_trading_pair] = float(ticker.get("markPrice", 0))
        except Exception:
            self.logger().error("Error fetching last traded prices", exc_info=True)
        return result

    async def _update_trading_fees(self):
        """
        Update trading fees. For now, use default fees from vest_utils.
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for stream_message in self._iter_user_event_queue():
            try:
                await self._process_user_stream_event(stream_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)

    async def _process_user_stream_event(self, stream_message: Dict[str, Any]):
        """
        Process user stream events for orders and trades
        """
        event_type = stream_message.get("e")

        if event_type == "executionReport":
            await self._process_order_update(stream_message)
        elif event_type == "outboundAccountPosition":
            await self._process_balance_update(stream_message)

    async def _process_order_update(self, order_data: Dict[str, Any]):
        """
        Process order update from user stream
        """
        client_order_id = order_data.get("c")
        if client_order_id in self._order_tracker.active_orders:
            tracked_order = self._order_tracker.active_orders[client_order_id]

            new_state = CONSTANTS.ORDER_STATE.get(order_data.get("X"), OrderState.OPEN)

            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
                client_order_id=client_order_id,
                exchange_order_id=order_data.get("i"),
            )
            self._order_tracker.process_order_update(order_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            trading_pair_id = await self.exchange_symbol_associated_to_pair(order.trading_pair)

            all_fills = await self._api_get(
                path_url=CONSTANTS.VEST_ORDERS_PATH,
                params={
                    "orderId": exchange_order_id,
                    "symbol": trading_pair_id
                },
                is_auth_required=True
            )

            for fill in all_fills.get("fills", []):
                trade_update = TradeUpdate(
                    trade_id=fill["tradeId"],
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=TokenAmount(amount=Decimal(fill["commission"]), token=fill["commissionAsset"]),
                    fill_base_amount=Decimal(fill["qty"]),
                    fill_quote_amount=Decimal(fill["price"]) * Decimal(fill["qty"]),
                    fill_price=Decimal(fill["price"]),
                    fill_timestamp=int(fill["time"]),
                )
                trade_updates.append(trade_update)
        except Exception:
            self.logger().error(f"Error fetching trade updates for order {order.client_order_id}", exc_info=True)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()

            order_status_list = await self._api_get(
                path_url=CONSTANTS.VEST_ORDERS_PATH,
                params={
                    "id": exchange_order_id,
                    "time": int(self.current_timestamp * 1000)  # Required time parameter
                },
                is_auth_required=True
            )

            # Response is a list, get the first order
            if order_status_list and len(order_status_list) > 0:
                order_status = order_status_list[0]
                new_state = CONSTANTS.ORDER_STATE.get(order_status.get("status"), OrderState.OPEN)
            else:
                new_state = OrderState.FAILED

            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
            )

        except Exception as ex:
            self.logger().error(f"Error fetching order status for {tracked_order.client_order_id}: {ex}", exc_info=True)
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=tracked_order.current_state,
            )

        return order_update

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Format the raw exchange info into TradingRule objects.
        """
        trading_rules = []

        for symbol_info in exchange_info_dict.get("symbols", []):
            try:
                if vest_utils.is_exchange_information_valid(exchange_info=symbol_info):
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                        symbol=symbol_info["symbol"]
                    )

                    # Extract trading rules from symbol info based on Vest API structure
                    size_decimals = int(symbol_info.get("sizeDecimals", 4))
                    price_decimals = int(symbol_info.get("priceDecimals", 2))

                    # Minimum order size is 1e(-sizeDecimals)
                    min_order_size = Decimal(10) ** (-size_decimals)
                    # Price increment is 1e(-priceDecimals)
                    min_price_increment = Decimal(10) ** (-price_decimals)
                    # Base amount increment same as min order size
                    min_base_amount_increment = min_order_size
                    # Default minimum notional size
                    min_notional_size = Decimal("1")

                    trading_rules.append(
                        TradingRule(
                            trading_pair=trading_pair,
                            min_order_size=min_order_size,
                            min_price_increment=min_price_increment,
                            min_base_amount_increment=min_base_amount_increment,
                            min_notional_size=min_notional_size,
                        )
                    )
            except Exception:
                self.logger().exception(f"Error parsing trading pair rule {symbol_info}. Skipping.")

        return trading_rules

    async def _update_balances(self):
        try:
            account_info = await self._api_get(
                path_url=CONSTANTS.VEST_ACCOUNT_PATH,
                is_auth_required=True
            )

            balances = {}
            for balance_entry in account_info.get("balances", []):
                asset = balance_entry["asset"]
                total = Decimal(balance_entry["total"])
                locked = Decimal(balance_entry["locked"])
                available = total - locked
                balances[asset] = {
                    "total": total,
                    "available": available
                }

            self._account_balances = balances

        except Exception:
            self.logger().error("Error updating account balances", exc_info=True)
            raise
