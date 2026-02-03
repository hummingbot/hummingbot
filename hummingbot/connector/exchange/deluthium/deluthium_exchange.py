"""
Deluthium DEX Exchange connector.

Deluthium (DarkPool) is an RFQ-based DEX that provides swap quotes and
on-chain execution across BSC, Base, and Ethereum chains.

Important notes:
- All endpoints require JWT authentication
- Orders are RFQ-based and return calldata for on-chain execution
- Hummingbot does NOT broadcast transactions - users must execute the calldata
"""

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.deluthium import (
    deluthium_constants as CONSTANTS,
    deluthium_utils as utils,
    deluthium_web_utils as web_utils,
)
from hummingbot.connector.exchange.deluthium.deluthium_api_order_book_data_source import (
    DeluthiumAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.deluthium.deluthium_auth import DeluthiumAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DeluthiumExchange(ExchangePyBase):
    """
    Deluthium DEX Exchange connector.
    
    This connector implements the RFQ (Request for Quote) trading model.
    Orders return calldata that must be executed on-chain by the user.
    """
    
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0
    
    web_utils = web_utils

    def __init__(
        self,
        deluthium_api_key: str = None,
        deluthium_chain_id: int = CONSTANTS.DEFAULT_CHAIN_ID,
        deluthium_wallet_address: str = "",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        """
        Initialize Deluthium exchange connector.
        
        :param deluthium_api_key: JWT token from Deluthium
        :param deluthium_chain_id: Chain ID (56=BSC, 8453=Base, 1=ETH)
        :param deluthium_wallet_address: Wallet address for RFQ quotes
        :param trading_pairs: List of trading pairs
        :param trading_required: Whether trading is required
        :param domain: Domain (default: deluthium)
        """
        self._api_key = deluthium_api_key
        self._chain_id = deluthium_chain_id
        self._wallet_address = deluthium_wallet_address
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        
        # Cache for pair_id lookups
        self._pair_id_cache: Dict[str, Dict[str, Any]] = {}
        
        # Token info cache
        self._token_info_cache: Dict[str, Dict[str, Any]] = {}
        
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[DeluthiumAuth]:
        if self._api_key:
            return DeluthiumAuth(self._api_key)
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.LISTING_PAIRS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.LISTING_PAIRS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.LISTING_PAIRS_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        # RFQ orders cannot be cancelled
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def pair_id_cache(self) -> Dict[str, Dict[str, Any]]:
        return self._pair_id_cache

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def _get_pair_cache(self, trading_pair: str) -> Dict[str, Any]:
        """
        Get pair cache with chain-qualified lookup.
        
        Cache keys are formatted as "{trading_pair}:{chain_id}" to support
        the same symbol on different chains.
        """
        cache_key = f"{trading_pair}:{self._chain_id}"
        return self._pair_id_cache.get(cache_key, {})

    @property
    def wallet_address(self) -> str:
        return self._wallet_address

    def supported_order_types(self) -> List[OrderType]:
        """
        Deluthium only supports market orders (RFQ-based).
        
        IMPORTANT LIMITATIONS:
        - Limit orders are NOT supported
        - Order book data is synthetic (no real depth)
        - Strategies requiring order book depth will not work correctly
        - Strategies requiring limit orders will not work
        
        Compatible strategies: Simple arbitrage, market making with external signals
        Incompatible strategies: Grid trading, order book-based strategies
        """
        return [OrderType.MARKET]

    async def _make_network_check_request(self):
        """Check network connectivity."""
        params = {"chain_id": self._chain_id}
        await self._api_get(
            path_url=self.check_network_request_path,
            params=params,
            is_auth_required=True
        )

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return DeluthiumAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> Optional[UserStreamTrackerDataSource]:
        # Deluthium doesn't have user stream - RFQ is stateless
        return None

    async def _make_trading_rules_request(self) -> Any:
        params = {"chain_id": self._chain_id}
        response = await self._api_get(
            path_url=self.trading_rules_request_path,
            params=params,
            is_auth_required=True
        )
        return response

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    async def _update_trading_rules(self):
        """Update trading rules from exchange."""
        response = await self._make_trading_rules_request()
        trading_rules_list = await self._format_trading_rules(response)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=response)

    async def _format_trading_rules(self, exchange_info: Dict) -> List[TradingRule]:
        """Parse trading rules from exchange info."""
        trading_rules = []
        
        data = exchange_info.get("data", {})
        pairs = data.get("pairs", []) if isinstance(data, dict) else data
        if not isinstance(pairs, list):
            pairs = []
        
        for pair_info in pairs:
            try:
                if not utils.is_exchange_information_valid(pair_info):
                    continue
                
                pair_symbol = pair_info.get("pair_symbol", "")
                trading_pair = utils.convert_symbol_to_hummingbot(pair_symbol)
                
                base_token = pair_info.get("base_token", {})
                quote_token = pair_info.get("quote_token", {})
                
                base_decimals = base_token.get("decimals", 18)
                quote_decimals = quote_token.get("decimals", 18)
                
                min_order_size = Decimal(10 ** -base_decimals)
                min_price_increment = Decimal(10 ** -quote_decimals)
                
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        min_base_amount_increment=min_order_size,
                        min_price_increment=min_price_increment,
                    )
                )
                
                # Cache pair info with chain-qualified key
                pair_id = pair_info.get("pair_id")
                chain_id = pair_info.get("chain_id", self._chain_id)
                cache_key = f"{trading_pair}:{chain_id}"
                self._pair_id_cache[cache_key] = {
                    "pair_id": pair_id,
                    "chain_id": chain_id,
                    "base_token": base_token,
                    "quote_token": quote_token,
                }
                
            except Exception as e:
                self.logger().error(f"Error parsing trading rule: {e}", exc_info=True)
        
        return trading_rules

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict):
        """Initialize trading pair symbol mapping."""
        mapping = bidict()
        
        data = exchange_info.get("data", {})
        pairs = data.get("pairs", []) if isinstance(data, dict) else data
        if not isinstance(pairs, list):
            pairs = []
        
        for pair_info in pairs:
            try:
                if not utils.is_exchange_information_valid(pair_info):
                    continue
                
                pair_symbol = pair_info.get("pair_symbol", "")
                exchange_symbol = pair_symbol  # e.g., "WBNB-USDT"
                trading_pair = utils.convert_symbol_to_hummingbot(pair_symbol)  # "WBNB/USDT"
                
                if trading_pair not in mapping.inverse:
                    mapping[exchange_symbol] = trading_pair
                
                # Cache pair info with chain-qualified key
                pair_id = pair_info.get("pair_id")
                chain_id = pair_info.get("chain_id", self._chain_id)
                cache_key = f"{trading_pair}:{chain_id}"
                self._pair_id_cache[cache_key] = {
                    "pair_id": pair_id,
                    "chain_id": chain_id,
                    "base_token": pair_info.get("base_token", {}),
                    "quote_token": pair_info.get("quote_token", {}),
                }
                
            except Exception as e:
                self.logger().error(f"Error mapping trading pair: {e}", exc_info=True)
        
        self._set_trading_pair_symbol_map(mapping)

    async def _initialize_trading_pair_symbol_map(self):
        """Initialize trading pair symbol map."""
        try:
            exchange_info = await self._make_trading_pairs_request()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().exception(f"Error requesting exchange info: {e}")

    async def load_markets(self):
        """Load markets and cache pair IDs."""
        await self._update_trading_rules()

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
    ) -> TradeFeeBase:
        """Get trading fee."""
        # Deluthium fees are typically deducted from returns
        is_maker = False  # RFQ is always taker
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _update_trading_fees(self):
        """Update trading fees - no-op for Deluthium."""
        pass

    async def _update_balances(self):
        """
        Update balances.
        
        IMPORTANT: Deluthium is a DEX - on-chain balance querying is not implemented.
        Users must verify their wallet balances externally before trading.
        
        For production use with balance-dependent strategies, consider:
        1. Using web3.py to query on-chain balances
        2. Manually setting initial balances in strategy config
        3. Using external balance monitoring tools
        """
        self.logger().warning(
            "Deluthium DEX: Balance querying not implemented. "
            "On-chain balances must be verified externally before trading. "
            "Strategies requiring accurate balance information may not work correctly."
        )

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
        """
        Place an order (get firm quote).
        
        IMPORTANT: This returns calldata for on-chain execution.
        Hummingbot does NOT broadcast the transaction.
        """
        if order_type != OrderType.MARKET:
            raise ValueError("Deluthium only supports market orders (RFQ-based)")
        
        pair_cache = self._get_pair_cache(trading_pair)
        base_token = pair_cache.get("base_token", {})
        quote_token = pair_cache.get("quote_token", {})
        chain_id = pair_cache.get("chain_id", self._chain_id)
        
        # Determine token_in and token_out based on trade type
        if trade_type == TradeType.BUY:
            token_in = quote_token.get("token_address", "")
            token_out = base_token.get("token_address", "")
            token_in_decimals = quote_token.get("decimals", 18)
        else:
            token_in = base_token.get("token_address", "")
            token_out = quote_token.get("token_address", "")
            token_in_decimals = base_token.get("decimals", 18)
        
        # Convert amount to wei
        amount_in_wei = utils.to_wei(amount, token_in_decimals)
        
        wallet_address = kwargs.get("wallet_address", self._wallet_address)
        slippage = kwargs.get("slippage", CONSTANTS.DEFAULT_SLIPPAGE)
        expiry_time = kwargs.get("expiry_time_sec", CONSTANTS.DEFAULT_EXPIRY_TIME_SEC)
        
        request_params = {
            "src_chain_id": chain_id,
            "dst_chain_id": chain_id,
            "from_address": wallet_address,
            "to_address": wallet_address,
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": amount_in_wei,
            "slippage": slippage,
            "expiry_time_sec": expiry_time,
        }
        
        response = await self._api_post(
            path_url=CONSTANTS.QUOTE_FIRM_URL,
            data=request_params,
            is_auth_required=True
        )
        
        # Handle response
        self._handle_response_errors(response)
        
        data = response.get("data", {})
        quote_id = data.get("quote_id", order_id)
        
        # Store calldata info for user to execute
        self.logger().info(
            f"Firm quote received for {trading_pair}. "
            f"Quote ID: {quote_id}. "
            f"Calldata available in order info. "
            f"User must broadcast transaction to execute."
        )
        
        return (quote_id, self.current_timestamp)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancel an order.
        
        Note: RFQ orders cannot be cancelled. They either get executed
        on-chain or expire after the deadline.
        """
        self.logger().warning(
            f"Cannot cancel RFQ order {order_id}. "
            f"RFQ quotes expire automatically after deadline."
        )
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status.
        
        Note: RFQ orders don't have persistent status on the API.
        Status is determined by on-chain execution.
        """
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=tracked_order.current_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
        )

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Get trade updates for an order."""
        # RFQ doesn't provide trade history via API
        return []

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """Get last traded price for a trading pair."""
        pair_cache = self._get_pair_cache(trading_pair)
        pair_id = pair_cache.get("pair_id")
        chain_id = pair_cache.get("chain_id", self._chain_id)
        
        if pair_id is None:
            return 0.0
        
        params = {
            "chainId": chain_id,
            "pairId": pair_id,
            "interval": "1h",
        }
        
        try:
            response = await self._api_get(
                path_url=CONSTANTS.MARKET_PAIR_URL,
                params=params,
                is_auth_required=True
            )
            data = response.get("data", {})
            price = float(data.get("price", 0))
            return price
        except Exception as e:
            self.logger().warning(f"Error fetching price for {trading_pair}: {e}")
            return 0.0

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """Get last traded prices for multiple trading pairs."""
        prices = {}
        for trading_pair in trading_pairs:
            price = await self._get_last_traded_price(trading_pair)
            prices[trading_pair] = price
        return prices

    async def get_indicative_quote(
        self,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get an indicative quote for a swap.
        
        This is useful for displaying estimated prices before committing.
        """
        pair_cache = self._get_pair_cache(trading_pair)
        base_token = pair_cache.get("base_token", {})
        quote_token = pair_cache.get("quote_token", {})
        chain_id = pair_cache.get("chain_id", self._chain_id)
        
        if trade_type == TradeType.BUY:
            token_in = quote_token.get("token_address", "")
            token_out = base_token.get("token_address", "")
            token_in_decimals = quote_token.get("decimals", 18)
        else:
            token_in = base_token.get("token_address", "")
            token_out = quote_token.get("token_address", "")
            token_in_decimals = base_token.get("decimals", 18)
        
        amount_in_wei = utils.to_wei(amount, token_in_decimals)
        
        request_params = {
            "src_chain_id": chain_id,
            "dst_chain_id": chain_id,
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": amount_in_wei,
        }
        
        response = await self._api_post(
            path_url=CONSTANTS.QUOTE_INDICATIVE_URL,
            data=request_params,
            is_auth_required=True
        )
        
        self._handle_response_errors(response)
        return response.get("data", {})

    def _handle_response_errors(self, response: Dict[str, Any]):
        """
        Handle API response errors (dual format - string and numeric codes).
        
        Raises appropriate exception types for different error conditions.
        """
        if response is None:
            return
        
        code = response.get("code")
        
        # Check for success
        if code == CONSTANTS.SUCCESS_CODE or code == str(CONSTANTS.SUCCESS_CODE):
            return
        
        message = response.get("message", "Unknown error")
        
        # Exception type mapping
        exception_map = {
            "BadRequest": ValueError,
            "BadSymbol": ValueError,
            "InvalidOrder": ValueError,
            "InsufficientFunds": ValueError,
            "ExchangeNotAvailable": IOError,
            "ExchangeError": IOError,
            "AuthenticationError": PermissionError,
            "RequestTimeout": TimeoutError,
            "OrderNotFound": ValueError,
        }
        
        # Handle string error codes (Trading Service)
        if isinstance(code, str) and code in CONSTANTS.STRING_ERROR_CODES:
            error_type = CONSTANTS.STRING_ERROR_CODES[code]
            exception_class = exception_map.get(error_type, IOError)
            raise exception_class(f"Deluthium {error_type}: {message}")
        
        # Handle numeric error codes (Market Data Service)
        if isinstance(code, int) and code in CONSTANTS.NUMERIC_ERROR_CODES:
            error_type = CONSTANTS.NUMERIC_ERROR_CODES[code]
            if error_type:
                exception_class = exception_map.get(error_type, IOError)
                raise exception_class(f"Deluthium {error_type}: {message}")
        
        # Generic error - use IOError for API errors
        if code is not None and code != CONSTANTS.SUCCESS_CODE:
            raise IOError(f"Deluthium API Error [{code}]: {message}")
