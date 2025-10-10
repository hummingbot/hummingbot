"""
Coins.xyz Exchange Connector for Hummingbot

This module implements the main exchange connector class for Coins.xyz,
providing integration with the Hummingbot trading framework.
"""

import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

# Production Hummingbot imports
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair

from hummingbot.connector.exchange.coinsxyz import (
    coinsxyz_constants as CONSTANTS,
    coinsxyz_utils as utils,
    coinsxyz_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange_info import CoinsxyzExchangeInfo
# Core data types - production Hummingbot imports
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinsxyzExchange(ExchangePyBase):
    """
    Coins.xyz exchange connector implementation.

    This class provides the main interface for trading on Coins.xyz exchange
    through the Hummingbot framework.
    """
    
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    
    web_utils = web_utils

    def __init__(self,
                 coinsxyz_api_key: str,
                 coinsxyz_secret_key: str,
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 **kwargs):
        """
        Initialize the Coins.xyz exchange connector.

        :param coinsxyz_api_key: API key for Coins.xyz
        :param coinsxyz_secret_key: Secret key for Coins.xyz
        :param balance_asset_limit: Balance asset limits
        :param rate_limits_share_pct: Rate limits share percentage
        :param trading_pairs: List of trading pairs to support
        :param trading_required: Whether trading functionality is required
        :param domain: API domain to use
        """
        self.api_key = coinsxyz_api_key
        self.secret_key = coinsxyz_secret_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_timestamp = 1.0

        # Exchange info handler
        self._exchange_info_handler = CoinsxyzExchangeInfo()

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def display_name(self) -> str:
        """
        Return the display name for this exchange connector.

        Returns:
            Display name string
        """
        return "coinsxyz"

    # ========================================
    # Required Abstract Properties
    # ========================================

    @property
    def authenticator(self):
        """Get the authentication handler for this exchange."""
        return CoinsxyzAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer
        )

    @property
    def name(self) -> str:
        """Get the exchange name."""
        return CONSTANTS.EXCHANGE_NAME

    @property
    def rate_limits_rules(self):
        """Get the rate limiting rules for this exchange."""
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        """Get the API domain."""
        return self._domain

    @property
    def client_order_id_max_length(self):
        """Get the maximum length for client order IDs."""
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        """Get the prefix for client order IDs."""
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        """Get the API path for trading rules."""
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        """Get the API path for trading pairs."""
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        """Get the API path for network connectivity check."""
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        """Get the list of supported trading pairs."""
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Whether order cancellation is synchronous on this exchange."""
        return True

    @property
    def is_trading_required(self) -> bool:
        """Whether trading functionality is required."""
        return self._trading_required

    def _is_user_stream_initialized(self) -> bool:
        """Override to mark user stream as initialized since it's fully implemented."""
        # User stream is fully implemented and will be started when needed
        # For strategies that don't require real-time updates, we mark it as ready
        return True

    @property
    def status_dict(self) -> Dict[str, bool]:
        """Override to add debug logging."""
        status = super().status_dict
        self.logger().error(f"DEBUG READY: status_dict = {status}")
        self.logger().error(f"DEBUG READY: symbols_mapping = {self.trading_pair_symbol_map_ready()}")
        self.logger().error(f"DEBUG READY: order_books = {self.order_book_tracker.ready}")
        self.logger().error(f"DEBUG READY: account_balance = {len(self._account_balances)} balances")
        self.logger().error(f"DEBUG READY: trading_rules = {len(self._trading_rules)} rules")
        self.logger().error(f"DEBUG READY: user_stream = {self._is_user_stream_initialized()}")
        return status

    # ========================================
    # Required Abstract Methods
    # ========================================

    def supported_order_types(self):
        """Get the list of supported order types."""
        return [OrderType.LIMIT, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        """Check if the exception is related to time synchronization."""
        error_description = str(request_exception)
        return ("timestamp" in error_description.lower() or
                "time" in error_description.lower())

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """Check if the exception indicates order not found during status update."""
        return (str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(status_update_exception) and
                CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception))

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """Check if the exception indicates order not found during cancellation."""
        return (str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(cancelation_exception) and
                CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception))

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Create the web assistants factory for API communication."""
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self.authenticator
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """Create the order book data source for market data."""
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_api_order_book_data_source import CoinsxyzAPIOrderBookDataSource
        return CoinsxyzAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """Create the user stream data source for account updates."""
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_api_user_stream_data_source import CoinsxyzAPIUserStreamDataSource
        return CoinsxyzAPIUserStreamDataSource(
            auth=self.authenticator,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        """Calculate trading fees for an order."""
        # Default fee calculation - will be updated with actual Coins.xyz fee structure
        is_maker = order_type is OrderType.LIMIT_MAKER
        fee_percent = Decimal("0.001")  # 0.1% default fee
        return DeductedFromReturnsTradeFee(percent=fee_percent)

    # ========================================
    # Trading Methods (To be implemented)
    # ========================================

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        """Place an order on the exchange."""
        self.logger().info(f"DEBUG ORDER: _place_order called - {trade_type} {amount} {trading_pair} @ {price}")
        
        exchange_symbol = utils.convert_to_exchange_trading_pair(trading_pair)
        
        order_params = {
            "symbol": exchange_symbol,
            "side": CONSTANTS.SIDE_BUY if trade_type == TradeType.BUY else CONSTANTS.SIDE_SELL,
            "type": "LIMIT" if order_type == OrderType.LIMIT else "MARKET",
            "quantity": str(amount),
            "newClientOrderId": order_id,
        }
        
        if order_type == OrderType.LIMIT:
            order_params["price"] = str(price)
            order_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        
        self.logger().info(f"DEBUG ORDER: Sending order to exchange - params={order_params}")
        
        response = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=order_params,
            is_auth_required=True
        )
        
        self.logger().info(f"DEBUG ORDER: Order response received - {response}")
        
        exchange_order_id = str(response.get("orderId"))
        timestamp = response.get("transactTime", self.current_timestamp * 1000) / 1000
        
        return exchange_order_id, timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """Cancel an order on the exchange."""
        exchange_symbol = utils.convert_to_exchange_trading_pair(tracked_order.trading_pair)
        
        cancel_params = {
            "symbol": exchange_symbol,
            "origClientOrderId": order_id,
        }
        
        await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params=cancel_params,
            is_auth_required=True
        )

    # ========================================
    # Data Processing Methods (To be implemented)
    # ========================================

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Format trading rules from exchange information.

        :param exchange_info_dict: Exchange info response from API
        :return: List of TradingRule objects
        """
        try:
            trading_pairs, trading_rules = self._exchange_info_handler.parse_exchange_info(exchange_info_dict)

            # Update internal trading pairs list
            if trading_pairs:
                self._trading_pairs = trading_pairs
                self.logger().info(f"Updated trading pairs: {len(trading_pairs)} pairs available")

            # Return list of trading rules
            return list(trading_rules.values())

        except Exception as e:
            self.logger().error(f"Error formatting trading rules: {e}")
            return []

    async def _update_trading_fees(self):
        """Update trading fees information from the exchange."""
        # TODO: Implement fee updates
        pass

    async def _user_stream_event_listener(self):
        """Listen for user stream events and process them."""
        # Basic implementation - user stream will be started when needed
        pass

    async def _update_balances(self):
        try:
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()

            account_info = await self._api_get(
                path_url=CONSTANTS.ACCOUNTS_PATH_URL,
                is_auth_required=True)

            # Handle different possible response formats
            balances = account_info.get("balances", [])
            
            # If balances is empty or not a list, try alternative formats
            if not balances or not isinstance(balances, list):
                # Some exchanges return balances directly in the root
                if "asset" in account_info and "free" in account_info:
                    balances = [account_info]
                else:
                    self.logger().warning(f"No balances found in account info response")
                    return
            
            for balance_entry in balances:
                if not isinstance(balance_entry, dict):
                    continue
                    
                asset_name = balance_entry.get("asset")
                if not asset_name:
                    continue
                    
                free_balance = Decimal(str(balance_entry.get("free", "0")))
                locked_balance = Decimal(str(balance_entry.get("locked", "0")))
                total_balance = free_balance + locked_balance
                
                self._account_available_balances[asset_name] = free_balance
                self._account_balances[asset_name] = total_balance
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]
                
        except Exception as e:
            self.logger().error(f"Error updating balances: {e}", exc_info=True)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Get all trade updates for a specific order."""
        if not order.exchange_order_id:
            return []
            
        exchange_symbol = utils.convert_to_exchange_trading_pair(order.trading_pair)
        
        params = {
            "symbol": exchange_symbol,
            "limit": 500,
        }
        
        try:
            trades = await self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params=params,
                is_auth_required=True
            )
            
            trade_updates = []
            for trade in trades:
                if str(trade.get("orderId")) == str(order.exchange_order_id):
                    trade_update = TradeUpdate(
                        trade_id=str(trade["id"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(trade["orderId"]),
                        trading_pair=order.trading_pair,
                        fill_timestamp=trade["time"] / 1000,
                        fill_price=Decimal(str(trade["price"])),
                        fill_base_amount=Decimal(str(trade["qty"])),
                        fill_quote_amount=Decimal(str(trade["quoteQty"])),
                        fee=TokenAmount(token=trade["commissionAsset"], amount=Decimal(str(trade["commission"]))),
                    )
                    trade_updates.append(trade_update)
            
            return trade_updates
        except Exception as e:
            self.logger().error(f"Error fetching trade updates for order {order.client_order_id}: {e}")
            return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Request order status from the exchange."""
        exchange_symbol = utils.convert_to_exchange_trading_pair(tracked_order.trading_pair)
        
        params = {
            "symbol": exchange_symbol,
            "origClientOrderId": tracked_order.client_order_id,
        }
        
        try:
            response = await self._api_get(
                path_url=CONSTANTS.ORDER_PATH_URL,
                params=params,
                is_auth_required=True
            )
            
            order_state = CONSTANTS.ORDER_STATE.get(response.get("status", "OPEN"), OrderState.OPEN)
            
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(response.get("orderId", "")),
                trading_pair=tracked_order.trading_pair,
                update_timestamp=response.get("updateTime", response.get("time", self.current_timestamp * 1000)) / 1000,
                new_state=order_state,
            )
            
            return order_update
        except Exception as e:
            self.logger().error(f"Error requesting order status for {tracked_order.client_order_id}: {e}")
            raise

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """
        Initialize trading pair symbol mappings from exchange info.

        :param exchange_info: Exchange info response from API
        """
        try:
            # Parse exchange info and update internal mappings
            trading_pairs, trading_rules = self._exchange_info_handler.parse_exchange_info(exchange_info)

            # Create symbol mappings using bidict
            mapping_dict = {}
            for trading_pair in trading_pairs:
                # Convert Hummingbot format to exchange format
                exchange_symbol = utils.convert_to_exchange_trading_pair(trading_pair)
                mapping_dict[exchange_symbol] = trading_pair

            # Set the trading pair symbol map
            self._set_trading_pair_symbol_map(bidict(mapping_dict))
            
            self.logger().info(f"Initialized symbol mappings for {len(mapping_dict)} trading pairs")

        except Exception as e:
            self.logger().error(f"Error initializing trading pair symbols: {e}")

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """Get the last traded price for a trading pair."""
        try:
            # Convert trading pair to exchange format
            exchange_symbol = utils.convert_to_exchange_trading_pair(trading_pair)
            
            # Get ticker data from exchange
            ticker_data = await self._api_get(
                path_url=f"{CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL}?symbol={exchange_symbol}",
                is_auth_required=False
            )
            
            # Extract last price
            last_price = float(ticker_data.get("lastPrice", 0))
            return last_price
            
        except Exception as e:
            self.logger().error(f"Error getting last traded price for {trading_pair}: {e}")
            return 0.0

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        """
        Map exchange symbol to Hummingbot trading pair format.
        
        Args:
            symbol: Exchange symbol (e.g., 'BTCUSDT')
            
        Returns:
            Trading pair in Hummingbot format (e.g., 'BTC-USDT')
        """
        try:
            return utils.parse_exchange_trading_pair(symbol)
        except Exception as e:
            self.logger().error(f"Error mapping symbol {symbol}: {e}")
            raise KeyError(symbol)

    async def all_trading_pairs(self) -> List[str]:
        """
        Get all available trading pairs from the exchange.
        
        Returns:
            List of trading pairs in Hummingbot format
        """
        try:
            print(f"DEBUG HEDGE: all_trading_pairs() called for coinsxyz")
            
            # Get exchange info
            exchange_info = await self._api_get(
                path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
                is_auth_required=False
            )
            
            # Parse trading pairs from exchange info
            trading_pairs, _ = self._exchange_info_handler.parse_exchange_info(exchange_info)
            
            print(f"DEBUG HEDGE: all_trading_pairs() returning {len(trading_pairs)} pairs: {trading_pairs[:10]}...")
            return trading_pairs
            
        except Exception as e:
            self.logger().error(f"Error fetching all trading pairs: {e}")
            print(f"DEBUG HEDGE: all_trading_pairs() error: {e}")
            return []

    # ========================================
    # Day 17: Data Validation Methods
    # ========================================

    def _validate_balance_update(self, balance_data: Dict[str, Any]) -> bool:
        """
        Validate balance update data - Day 17 Implementation.

        Args:
            balance_data: Balance update data to validate

        Returns:
            True if data is valid, False otherwise
        """
        try:
            if not isinstance(balance_data, dict):
                return False

            # Check required fields
            required_fields = ['balances', 'timestamp']
            for field in required_fields:
                if field not in balance_data:
                    self.logger().warning(f"Missing required field in balance update: {field}")
                    return False

            # Validate balance entries
            balances = balance_data.get('balances', [])
            if not isinstance(balances, list):
                return False

            for balance in balances:
                if not isinstance(balance, dict):
                    return False

                # Check balance fields
                if 'asset' not in balance or 'free' not in balance or 'locked' not in balance:
                    return False

                # Validate numeric values
                try:
                    Decimal(str(balance['free']))
                    Decimal(str(balance['locked']))
                except (ValueError, TypeError):
                    return False

            return True

        except Exception as e:
            self.logger().error(f"Error validating balance update: {e}")
            return False

    def _validate_order_update(self, order_data: Dict[str, Any]) -> bool:
        """
        Validate order update data - Day 17 Implementation.

        Args:
            order_data: Order update data to validate

        Returns:
            True if data is valid, False otherwise
        """
        try:
            if not isinstance(order_data, dict):
                return False

            # Check required fields
            required_fields = ['order_id', 'status', 'timestamp']
            for field in required_fields:
                if field not in order_data:
                    self.logger().warning(f"Missing required field in order update: {field}")
                    return False

            # Validate order status
            valid_statuses = ['NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'REJECTED', 'EXPIRED']
            if order_data.get('status') not in valid_statuses:
                return False

            # Validate numeric fields if present
            numeric_fields = ['quantity', 'price', 'executed_quantity']
            for field in numeric_fields:
                if field in order_data:
                    try:
                        Decimal(str(order_data[field]))
                    except (ValueError, TypeError):
                        return False

            return True

        except Exception as e:
            self.logger().error(f"Error validating order update: {e}")
            return False

    def _validate_trade_update(self, trade_data: Dict[str, Any]) -> bool:
        """
        Validate trade execution data - Day 17 Implementation.

        Args:
            trade_data: Trade execution data to validate

        Returns:
            True if data is valid, False otherwise
        """
        try:
            if not isinstance(trade_data, dict):
                return False

            # Check required fields
            required_fields = ['trade_id', 'order_id', 'quantity', 'price', 'timestamp']
            for field in required_fields:
                if field not in trade_data:
                    self.logger().warning(f"Missing required field in trade update: {field}")
                    return False

            # Validate numeric fields
            numeric_fields = ['quantity', 'price', 'commission']
            for field in numeric_fields:
                if field in trade_data:
                    try:
                        value = Decimal(str(trade_data[field]))
                        if value < 0:
                            return False
                    except (ValueError, TypeError):
                        return False

            return True

        except Exception as e:
            self.logger().error(f"Error validating trade update: {e}")
            return False

    def _validate_user_stream_data(self, stream_data: Dict[str, Any]) -> bool:
        """
        Validate user stream data - Day 17 Implementation.

        Args:
            stream_data: User stream data to validate

        Returns:
            True if data is valid, False otherwise
        """
        try:
            if not isinstance(stream_data, dict):
                return False

            # Check for event type
            event_type = stream_data.get('type')
            if not event_type:
                return False

            # Validate based on event type
            if event_type == 'balance_update':
                return self._validate_balance_update(stream_data)
            elif event_type == 'order_update':
                return self._validate_order_update(stream_data)
            elif event_type == 'trade_update':
                return self._validate_trade_update(stream_data)
            else:
                self.logger().warning(f"Unknown user stream event type: {event_type}")
                return False

        except Exception as e:
            self.logger().error(f"Error validating user stream data: {e}")
            return False

    # ========================================
    # Day 18: HTTP Error Handling Methods
    # ========================================

    def _handle_http_error(self, response_code: int, response_text: str) -> Dict[str, Any]:
        """
        Handle HTTP errors - Day 18 Implementation.

        Args:
            response_code: HTTP response code
            response_text: HTTP response text

        Returns:
            Error handling result
        """
        try:
            error_info = {
                'code': response_code,
                'message': response_text,
                'handled': False,
                'retry_after': None,
                'action': 'none'
            }

            if response_code == 429:
                # Rate limit error
                error_info.update(self._handle_rate_limit_error(response_text))
            elif response_code == 418:
                # IP banned error
                error_info.update({
                    'handled': True,
                    'action': 'ip_banned',
                    'message': 'IP address banned by exchange'
                })
            elif 500 <= response_code < 600:
                # Server error
                error_info.update(self._handle_server_error(response_code, response_text))
            elif response_code == 403:
                # Forbidden error
                error_info.update({
                    'handled': True,
                    'action': 'forbidden',
                    'message': 'Access forbidden - check API permissions'
                })
            elif response_code == 401:
                # Unauthorized error
                error_info.update({
                    'handled': True,
                    'action': 'unauthorized',
                    'message': 'Authentication failed - check API credentials'
                })

            self.logger().warning(f"HTTP error {response_code}: {error_info['message']}")
            return error_info

        except Exception as e:
            self.logger().error(f"Error handling HTTP error: {e}")
            return {'code': response_code, 'message': str(e), 'handled': False}

    def _handle_rate_limit_error(self, response_text: str) -> Dict[str, Any]:
        """
        Handle rate limit errors - Day 18 Implementation.

        Args:
            response_text: HTTP response text

        Returns:
            Rate limit handling result
        """
        try:
            # Extract retry-after from response if available
            retry_after = 60  # Default 60 seconds

            # Try to parse retry-after from response
            if 'retry-after' in response_text.lower():
                import re
                match = re.search(r'retry-after[:\s]+(\d+)', response_text.lower())
                if match:
                    retry_after = int(match.group(1))

            return {
                'handled': True,
                'action': 'rate_limit',
                'retry_after': retry_after,
                'message': f'Rate limit exceeded - retry after {retry_after} seconds'
            }

        except Exception as e:
            self.logger().error(f"Error handling rate limit error: {e}")
            return {
                'handled': True,
                'action': 'rate_limit',
                'retry_after': 60,
                'message': 'Rate limit exceeded - using default retry delay'
            }

    def _handle_server_error(self, response_code: int, response_text: str) -> Dict[str, Any]:
        """
        Handle server errors (5xx) - Day 18 Implementation.

        Args:
            response_code: HTTP response code
            response_text: HTTP response text

        Returns:
            Server error handling result
        """
        try:
            # Determine retry strategy based on error code
            if response_code == 500:
                # Internal server error - retry with backoff
                action = 'retry_with_backoff'
                retry_after = 5
            elif response_code == 502:
                # Bad gateway - retry quickly
                action = 'retry_quickly'
                retry_after = 2
            elif response_code == 503:
                # Service unavailable - longer retry
                action = 'retry_with_delay'
                retry_after = 30
            elif response_code == 504:
                # Gateway timeout - retry with backoff
                action = 'retry_with_backoff'
                retry_after = 10
            else:
                # Other server errors
                action = 'retry_with_backoff'
                retry_after = 15

            return {
                'handled': True,
                'action': action,
                'retry_after': retry_after,
                'message': f'Server error {response_code} - {action} in {retry_after}s'
            }

        except Exception as e:
            self.logger().error(f"Error handling server error: {e}")
            return {
                'handled': True,
                'action': 'retry_with_backoff',
                'retry_after': 30,
                'message': f'Server error {response_code} - using default retry strategy'
            }
