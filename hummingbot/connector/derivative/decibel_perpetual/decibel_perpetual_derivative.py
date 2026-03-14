import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_transaction_builder import (
    DecibelPerpetualTransactionBuilder,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_user_stream_data_source import (
    DecibelPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

s_decimal_0 = Decimal(0)


class DecibelPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Decibel Perpetual connector for Hummingbot.

    Decibel is a decentralized perpetual exchange built on Aptos blockchain.
    Key characteristics:
    - Orders are placed as on-chain transactions (not REST API calls)
    - Uses subaccounts for trading operations
    - Authentication via Aptos private key
    - Supports limit orders and IOC orders (no direct market orders)
    - Position mode: ONEWAY only (net positions)
    - Funding payments every hour
    """

    web_utils = web_utils

    def __init__(
        self,
        decibel_perpetual_api_wallet_public_key: str,
        decibel_perpetual_api_wallet_private_key: str,
        decibel_perpetual_main_wallet_public_key: str,
        decibel_perpetual_api_key: str = "",
        decibel_perpetual_market_order_slippage: Decimal = Decimal("0.08"),
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        """
        Initialize Decibel Perpetual connector.

        Uses delegation pattern (like Pacifica):
        - API wallet signs all transactions
        - Main wallet delegates trading permissions to API wallet
        - Main wallet private key is NEVER exposed to the bot

        :param decibel_perpetual_api_wallet_public_key: API wallet public key
        :param decibel_perpetual_api_wallet_private_key: API wallet private key (for signing)
        :param decibel_perpetual_main_wallet_public_key: Main wallet public key (for subaccount derivation)
        :param decibel_perpetual_api_key: Required API key from geomi.dev for all API access
        :param decibel_perpetual_market_order_slippage: Slippage for market orders (default 0.08 = 8%)
        :param trading_pairs: List of trading pairs to trade
        :param trading_required: Whether trading is required
        :param domain: Domain to use (mainnet or testnet)
        :param balance_asset_limit: Balance asset limits
        :param rate_limits_share_pct: Rate limit share percentage
        """
        self._api_wallet_public_key = decibel_perpetual_api_wallet_public_key
        self._api_wallet_private_key = decibel_perpetual_api_wallet_private_key
        self._main_wallet_public_key = decibel_perpetual_main_wallet_public_key
        self._api_key = decibel_perpetual_api_key
        self._market_order_slippage = decibel_perpetual_market_order_slippage
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []

        # Lazy-initialized auth
        self._auth: Optional[DecibelPerpetualAuth] = None

        # Transaction builder (lazy-initialized)
        self._transaction_builder: Optional[DecibelPerpetualTransactionBuilder] = None

        # Package address (lazy-loaded from API)
        self._package_address: Optional[str] = None

        # Trading pair mappings (exchange symbol <-> hummingbot trading pair)
        self._trading_pair_symbol_map: Optional[bidict] = None

        # Market info cache
        self._market_info: Dict[str, Dict[str, Any]] = {}

        # Last poll timestamps
        self._last_poll_timestamp = 0

        super().__init__(balance_asset_limit=balance_asset_limit, rate_limits_share_pct=rate_limits_share_pct)

    @property
    def name(self) -> str:
        """Exchange name."""
        return self._domain

    @property
    def api_key(self) -> str:
        """Get API key for REST API authentication."""
        return self._api_key

    @property
    def authenticator(self) -> DecibelPerpetualAuth:
        """
        Get authenticator instance.
        Lazy initialization to avoid creating account on import.
        """
        if self._auth is None:
            self._auth = DecibelPerpetualAuth(
                api_wallet_private_key=self._api_wallet_private_key,
                main_wallet_public_key=self._main_wallet_public_key,
                api_key=self._api_key,
            )
        return self._auth

    @property
    def rate_limits_rules(self):
        """
        Get rate limit rules for Decibel API.
        Note: All Decibel API requests require an API key (no anonymous tier).
        Rate limit: 200 requests per 30 seconds (400 per minute).
        """
        return CONSTANTS.RATE_LIMITS

    async def get_package_address(self) -> str:
        """
        Get the Decibel package address on Aptos.
        This is needed for deriving subaccount addresses.
        """
        if self._package_address is None:
            if self._domain == CONSTANTS.TESTNET_DOMAIN:
                self._package_address = CONSTANTS.TESTNET_PACKAGE
            else:
                self._package_address = CONSTANTS.MAINNET_PACKAGE
        return self._package_address

    async def _get_transaction_builder(self) -> DecibelPerpetualTransactionBuilder:
        """
        Get or create transaction builder instance.
        """
        if self._transaction_builder is None:
            package_address = await self.get_package_address()
            fullnode_url = web_utils.fullnode_url(self._domain)
            self._transaction_builder = DecibelPerpetualTransactionBuilder(
                auth=self.authenticator,
                package_address=package_address,
                fullnode_url=fullnode_url,
            )
        return self._transaction_builder

    async def _api_request(
        self,
        path_url: str,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make API request with optional authentication.
        """
        # Add API key to headers if available
        if self._api_key:
            api_headers = {"Authorization": f"Bearer {self._api_key}"}
            if headers:
                headers.update(api_headers)
            else:
                headers = api_headers

        return await super()._api_request(
            path_url=path_url,
            method=method,
            params=params,
            data=data,
            is_auth_required=is_auth_required,
            return_err=return_err,
            limit_id=limit_id,
            headers=headers,
            **kwargs
        )

    async def _api_request_url(self, path_url: str, is_auth_required: bool = False) -> str:
        """Get full URL for API request."""
        return web_utils.public_rest_url(path_url, domain=self._domain)

    def supported_order_types(self) -> List[OrderType]:
        """
        Decibel supports LIMIT and LIMIT_MAKER orders.
        Market orders can be simulated using IOC with aggressive pricing.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def supported_position_modes(self) -> List[PositionMode]:
        """
        Decibel only supports ONEWAY position mode (net positions).
        """
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        """
        Get collateral token for buy orders.
        Decibel uses USDC as collateral.
        """
        return "USDC"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        """
        Get collateral token for sell orders.
        Decibel uses USDC as collateral.
        """
        return "USDC"

    async def _make_trading_rules_request(self) -> Any:
        """
        Fetch trading rules from Decibel API.
        """
        exchange_info = await self._api_request(
            path_url=CONSTANTS.GET_MARKETS_PATH_URL,
            method=RESTMethod.GET,
            limit_id=CONSTANTS.GET_MARKETS_PATH_URL,
        )
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        """
        Fetch available trading pairs from Decibel API.
        """
        return await self._make_trading_rules_request()

    async def _initialize_trading_pair_symbol_map(self):
        """
        Initialize bidirectional mapping between exchange symbols and Hummingbot trading pairs.
        """
        try:
            exchange_info = await self._make_trading_pairs_request()
            self._trading_pair_symbol_map = await self._create_trading_pair_symbol_map(exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    async def _create_trading_pair_symbol_map(self, exchange_info: Dict[str, Any]) -> bidict:
        """
        Create bidirectional mapping from exchange info.

        Decibel format: {"markets": [{"market": "BTC/USD", ...}, ...]}
        or list format: [{"market": "BTC/USD", ...}, ...]
        """
        mapping = bidict()

        # Handle both dict format {"markets": [...]} and list format [...]
        markets = exchange_info if isinstance(exchange_info, list) else exchange_info.get("markets", [])

        for market in markets:
            # Decibel API uses "market_name" field (not "market")
            exchange_symbol = market.get("market_name")
            if exchange_symbol:
                # Convert BTC/USD to BTC-USD for Hummingbot
                base, quote = exchange_symbol.split("/")
                hb_trading_pair = combine_to_hb_trading_pair(base, quote)
                mapping[exchange_symbol] = hb_trading_pair
        return mapping

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Get last traded price for a trading pair.
        """
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        params = {"market": exchange_symbol}

        response = await self._api_request(
            path_url=CONSTANTS.GET_MARKET_PRICES_PATH_URL,
            params=params,
            method=RESTMethod.GET,
            limit_id=CONSTANTS.GET_MARKET_PRICES_PATH_URL,
        )

        return float(response.get("mark_px", 0))

    async def _update_trading_rules(self):
        """
        Update trading rules from exchange.
        """
        exchange_info = await self._make_trading_rules_request()
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, exchange_info: Dict[str, Any]) -> List[TradingRule]:
        """
        Convert exchange market info to TradingRule objects.

        Decibel market format:
        {
            "market": "BTC/USD",
            "min_order_size": 0.001,
            "max_order_size": 100.0,
            "tick_size": 0.1,
            "step_size": 0.001,
            "px_decimals": 1,
            "sz_decimals": 3
        }
        """
        trading_rules = []

        # Handle both dict format {"markets": [...]} and list format [...]
        markets = exchange_info if isinstance(exchange_info, list) else exchange_info.get("markets", [])

        for market in markets:
            try:
                # Decibel API uses "market_name" field
                exchange_symbol = market.get("market_name")
                hb_trading_pair = await self.trading_pair_associated_to_exchange_symbol(exchange_symbol)

                # Decibel API fields: min_size, lot_size, tick_size, px_decimals, sz_decimals
                # Convert from chain units to decimal using decimals
                px_decimals = market.get("px_decimals", 6)
                sz_decimals = market.get("sz_decimals", 8)

                min_size = Decimal(str(market.get("min_size", 0))) / Decimal(10 ** sz_decimals)
                lot_size = Decimal(str(market.get("lot_size", 0))) / Decimal(10 ** sz_decimals)
                tick_size = Decimal(str(market.get("tick_size", 0))) / Decimal(10 ** px_decimals)

                trading_rule = TradingRule(
                    trading_pair=hb_trading_pair,
                    min_order_size=min_size,
                    max_order_size=Decimal(str(market.get("max_open_interest", 0))),  # Use max OI as max size
                    min_price_increment=tick_size,
                    min_base_amount_increment=lot_size,
                    min_notional_size=Decimal("0"),  # Not provided by API
                )

                trading_rules.append(trading_rule)

                # Cache market info for later use (decimals, etc.)
                self._market_info[hb_trading_pair] = market

            except Exception:
                self.logger().exception(f"Error parsing trading rule for {market.get('market_name')}")

        return trading_rules

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """
        Create order book data source instance.
        """
        return DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """
        Create user stream data source instance.
        """
        return DecibelPerpetualUserStreamDataSource(
            connector=self,
            api_factory=self._web_assistants_factory,
            auth=self.authenticator,
            domain=self._domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_0,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        """
        Calculate trading fee.

        Decibel fees (from documentation):
        - Maker: 0.015% (0.00015)
        - Taker: 0.04% (0.0004)
        """
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)

        return build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def _update_balances(self):
        """
        Update account balances from Decibel API.
        """
        # Decibel API uses main wallet address, not derived subaccount
        account_addr = self.authenticator.main_wallet_address

        params = {"account": account_addr}

        response = await self._api_request(
            path_url=CONSTANTS.GET_ACCOUNT_OVERVIEW_PATH_URL,
            params=params,
            method=RESTMethod.GET,
            limit_id=CONSTANTS.GET_ACCOUNT_OVERVIEW_PATH_URL,
            is_auth_required=True,
        )

        # Decibel returns balances in USDC
        # API response format: {"perp_equity_balance": 1000.0, "usdc_cross_withdrawable_balance": 1000.0, ...}
        total_balance = Decimal(str(response.get("perp_equity_balance", 0)))
        available_balance = Decimal(str(response.get("usdc_cross_withdrawable_balance", 0)))

        self._account_available_balances["USDC"] = available_balance
        self._account_balances["USDC"] = total_balance

    async def _update_positions(self):
        """
        Update positions from Decibel API.
        """
        # Decibel API uses main wallet address, not derived subaccount
        account_addr = self.authenticator.main_wallet_address

        params = {"account": account_addr}

        response = await self._api_request(
            path_url=CONSTANTS.GET_ACCOUNT_POSITIONS_PATH_URL,
            params=params,
            method=RESTMethod.GET,
            limit_id=CONSTANTS.GET_ACCOUNT_POSITIONS_PATH_URL,
            is_auth_required=True,
        )

        # Decibel format: {"positions": [{"market": "BTC/USD", "size": 1.5, "entry_price": 50000, ...}]}
        # or list format: [{"market": "BTC/USD", "size": 1.5, ...}]
        positions = response if isinstance(response, list) else response.get("positions", [])

        for position_data in positions:
            try:
                exchange_symbol = position_data.get("market")
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(exchange_symbol)

                position_size = Decimal(str(position_data.get("size", 0)))

                if position_size == 0:
                    continue

                # Determine position side
                position_side = PositionSide.LONG if position_size > 0 else PositionSide.SHORT

                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=Decimal(str(position_data.get("unrealized_pnl", 0))),
                    entry_price=Decimal(str(position_data.get("entry_price", 0))),
                    amount=abs(position_size),
                    leverage=Decimal(str(position_data.get("leverage", 1))),
                )

                self._perpetual_trading.set_position(trading_pair, position)

            except Exception:
                self.logger().exception(f"Error parsing position for {position_data.get('market')}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Fetch all trade updates for a specific order.
        """
        # This will be implemented when we handle order tracking
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status from exchange.
        """
        # This will be implemented when we handle order tracking
        pass

    def _convert_price_to_chain_units(self, trading_pair: str, price: Decimal) -> int:
        """
        Convert price to chain units.

        Chain price = price * 10^px_decimals
        """
        market_info = self._market_info.get(trading_pair, {})
        px_decimals = market_info.get("px_decimals", 6)
        return int(price * Decimal(10 ** px_decimals))

    def _convert_size_to_chain_units(self, trading_pair: str, size: Decimal) -> int:
        """
        Convert size to chain units.

        Chain size = size * 10^sz_decimals
        """
        market_info = self._market_info.get(trading_pair, {})
        sz_decimals = market_info.get("sz_decimals", 6)
        return int(size * Decimal(10 ** sz_decimals))

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.OPEN,
        **kwargs
    ) -> Tuple[str, float]:
        """
        Place order on Decibel exchange.

        Unlike traditional exchanges, Decibel orders are placed as on-chain transactions.
        This method:
        1. Builds transaction payload
        2. Signs with Aptos account
        3. Submits to blockchain
        4. Waits for confirmation
        5. Returns exchange order ID and timestamp

        Market orders are implemented as IOC orders with slippage:
        - BUY: limit_price = mark_price * (1 + slippage)
        - SELL: limit_price = mark_price * (1 - slippage)

        :return: (exchange_order_id, timestamp)
        """
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

        # Determine order side
        is_buy = trade_type == TradeType.BUY

        # Determine order flags
        # IOC = Immediate or Cancel (for market-like orders)
        # POST_ONLY = Maker only (for LIMIT_MAKER)
        is_ioc = order_type == OrderType.MARKET
        is_post_only = order_type == OrderType.LIMIT_MAKER

        # For market orders, adjust price with slippage
        if order_type == OrderType.MARKET:
            # Get current mark price from order book
            order_book = self.get_order_book(trading_pair)
            if order_book is None:
                raise ValueError(f"Order book not available for {trading_pair}")

            # Use mid price as mark price
            mark_price = (order_book.get_price(True) + order_book.get_price(False)) / Decimal("2")

            # Apply slippage: BUY adds slippage, SELL subtracts slippage
            if is_buy:
                price = mark_price * (Decimal("1") + self._market_order_slippage)
            else:
                price = mark_price * (Decimal("1") - self._market_order_slippage)

            self.logger().info(
                f"Market order converted to IOC: mark_price={mark_price}, "
                f"slippage={self._market_order_slippage}, limit_price={price}"
            )

        # Convert to chain units
        chain_price = self._convert_price_to_chain_units(trading_pair, price)
        chain_size = self._convert_size_to_chain_units(trading_pair, amount)

        try:
            self.logger().info(
                f"Placing order: {trading_pair} {trade_type.name} {amount} @ {price} "
                f"(chain: {chain_size} @ {chain_price})"
            )

            # Get transaction builder
            tx_builder = await self._get_transaction_builder()

            # Submit order transaction
            tx_hash, exchange_order_id, timestamp = await tx_builder.place_order(
                market_id=exchange_symbol,
                price=chain_price,
                size=chain_size,
                is_buy=is_buy,
                is_ioc=is_ioc,
                is_post_only=is_post_only,
                client_order_id=order_id,
            )

            self.logger().info(
                f"Order placed successfully: tx_hash={tx_hash}, order_id={exchange_order_id}"
            )

            return exchange_order_id, timestamp

        except Exception as e:
            self.logger().error(f"Error placing order: {e}", exc_info=True)
            raise

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        Cancel order on Decibel exchange.

        Like order placement, cancellation is done via on-chain transaction.

        :return: True if cancellation was successful
        """
        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            trading_pair = tracked_order.trading_pair
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

            self.logger().info(f"Cancelling order: {exchange_order_id} for {trading_pair}")

            # Get transaction builder
            tx_builder = await self._get_transaction_builder()

            # Submit cancel transaction
            tx_hash, timestamp = await tx_builder.cancel_order(
                market_id=exchange_symbol,
                order_id=exchange_order_id,
            )

            self.logger().info(f"Order cancelled successfully: tx_hash={tx_hash}")

            return True

        except Exception as e:
            self.logger().error(f"Error cancelling order {order_id}: {e}", exc_info=True)
            return False

    async def _update_order_status(self):
        """
        Update status of all tracked orders.
        """
        if not self._trading_pairs:
            return

        try:
            # Decibel API uses main wallet address, not derived subaccount
            account_addr = self.authenticator.main_wallet_address

            params = {"account": account_addr}

            response = await self._api_request(
                path_url=CONSTANTS.GET_ACCOUNT_OPEN_ORDERS_PATH_URL,
                params=params,
                method=RESTMethod.GET,
                limit_id=CONSTANTS.GET_ACCOUNT_OPEN_ORDERS_PATH_URL,
                is_auth_required=True,
            )

            # Process open orders
            # Decibel format: {"orders": [{"order_id": "123", "market": "BTC/USD", ...}]}
            open_orders = {order["order_id"]: order for order in response.get("orders", [])}

            # Update tracked orders
            for order in list(self._order_tracker.active_orders.values()):
                exchange_order_id = await order.get_exchange_order_id()

                if exchange_order_id in open_orders:
                    # Order still open, update status if changed
                    order_data = open_orders[exchange_order_id]
                    current_state = order_data.get("status", "")
                    new_state = CONSTANTS.ORDER_STATE.get(current_state, OrderState.OPEN)

                    if order.current_state != new_state:
                        order_update = OrderUpdate(
                            trading_pair=order.trading_pair,
                            update_timestamp=order_data.get("timestamp", time.time() * 1000) / 1000,
                            new_state=new_state,
                            client_order_id=order.client_order_id,
                            exchange_order_id=exchange_order_id,
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                else:
                    # Order not in open orders - might be filled or cancelled
                    # Will be updated via trade history or marked as cancelled
                    if order.current_state == OrderState.OPEN:
                        # Fetch order history to determine final state
                        try:
                            history_params = {
                                "account": account_addr,
                                "order_id": exchange_order_id,
                                "limit": 1
                            }
                            history_response = await self._api_request(
                                path_url=CONSTANTS.GET_USER_ORDER_HISTORY_PATH_URL,
                                params=history_params,
                                method=RESTMethod.GET,
                                limit_id=CONSTANTS.GET_USER_ORDER_HISTORY_PATH_URL,
                                is_auth_required=True,
                            )

                            if history_response.get("orders"):
                                order_data = history_response["orders"][0]
                                final_state = order_data.get("status", "Cancelled")
                                order_update = OrderUpdate(
                                    trading_pair=order.trading_pair,
                                    update_timestamp=order_data.get("timestamp", time.time() * 1000) / 1000,
                                    new_state=CONSTANTS.ORDER_STATE.get(final_state, OrderState.CANCELED),
                                    client_order_id=order.client_order_id,
                                    exchange_order_id=exchange_order_id,
                                )
                                self._order_tracker.process_order_update(order_update=order_update)
                        except Exception:
                            self.logger().exception(f"Error fetching order history for {exchange_order_id}")

        except Exception:
            self.logger().exception("Error updating order status")

    async def _update_order_fills_from_trades(self):
        """
        Update order fills from trade history.
        """
        if not self._trading_pairs:
            return

        try:
            # Decibel API uses main wallet address, not derived subaccount
            account_addr = self.authenticator.main_wallet_address

            # Get recent trades
            params = {
                "account": account_addr,
                "limit": 100
            }

            response = await self._api_request(
                path_url=CONSTANTS.GET_USER_TRADE_HISTORY_PATH_URL,
                params=params,
                method=RESTMethod.GET,
                limit_id=CONSTANTS.GET_USER_TRADE_HISTORY_PATH_URL,
                is_auth_required=True,
            )

            # Process trades
            # Decibel format: {"trades": [{"trade_id": "456", "order_id": "123", ...}]}
            for trade_data in response.get("trades", []):
                try:
                    exchange_order_id = str(trade_data.get("order_id", ""))
                    tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(
                        exchange_order_id
                    )

                    if not tracked_order:
                        continue

                    # Extract trade details
                    trade_id = str(trade_data.get("trade_id", ""))
                    trade_price = Decimal(str(trade_data.get("price", "0")))
                    trade_size = Decimal(str(trade_data.get("size", "0")))
                    trade_timestamp = trade_data.get("timestamp", time.time() * 1000) / 1000

                    # Calculate fee
                    fee_percent = trade_data.get("fee_rate", 0.0004)  # Default taker fee
                    fee_amount = trade_size * trade_price * Decimal(str(fee_percent))
                    fee_asset = trade_data.get("fee_asset", "USD")

                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema,
                        trade_type=tracked_order.trade_type,
                        percent_token=fee_asset,
                        flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
                    )

                    trade_update = TradeUpdate(
                        trade_id=trade_id,
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=tracked_order.trading_pair,
                        fee=fee,
                        fill_base_amount=trade_size,
                        fill_quote_amount=trade_size * trade_price,
                        fill_price=trade_price,
                        fill_timestamp=trade_timestamp,
                    )

                    self._order_tracker.process_trade_update(trade_update)

                except Exception:
                    self.logger().exception(f"Error processing trade data: {trade_data}")

        except Exception:
            self.logger().exception("Error updating order fills")

    async def _user_stream_event_listener(self):
        """
        Listen to user stream events and process them.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                # Process different event types
                if isinstance(event_message, dict):
                    event_type = event_message.get("type")

                    if event_type == "order_update":
                        # Handle order updates
                        await self._process_order_update_event(event_message)
                    elif event_type == "trade":
                        # Handle trade events
                        await self._process_trade_event(event_message)
                    elif event_type == "position_update":
                        # Handle position updates
                        await self._process_position_update_event(event_message)
                    elif event_type == "balance_update":
                        # Handle balance updates
                        await self._process_balance_update_event(event_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error processing user stream event")

    async def _process_order_update_event(self, event: Dict[str, Any]):
        """Process order update from WebSocket."""
        exchange_order_id = str(event.get("order_id", ""))
        tracked_order = self._order_tracker.all_updatable_orders_by_exchange_order_id.get(exchange_order_id)

        if not tracked_order:
            self.logger().debug(
                f"Ignoring order update with id {exchange_order_id}: not in tracked orders"
            )
            return

        # Map Decibel order status to Hummingbot OrderState
        current_state = event.get("status", "")
        update_timestamp = event.get("timestamp", time.time() * 1000) / 1000

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=CONSTANTS.ORDER_STATE.get(current_state, OrderState.FAILED),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _process_trade_event(self, event: Dict[str, Any]):
        """Process trade event from WebSocket."""
        exchange_order_id = str(event.get("order_id", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            # Try to refresh order tracker
            all_orders = self._order_tracker.all_fillable_orders
            for _, order in all_orders.items():
                await order.get_exchange_order_id()
            tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

            if tracked_order is None:
                self.logger().debug(
                    f"Ignoring trade event with order_id {exchange_order_id}: not in tracked orders"
                )
                return

        # Build trade update
        fee_asset = tracked_order.quote_asset
        fee_amount = Decimal(str(event.get("fee", "0")))

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=tracked_order.position,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
        )

        fill_price = Decimal(str(event.get("price", "0")))
        fill_size = Decimal(str(event.get("size", "0")))

        trade_update = TradeUpdate(
            trade_id=str(event.get("trade_id", "")),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=event.get("timestamp", time.time() * 1000) / 1000,
            fill_price=fill_price,
            fill_base_amount=fill_size,
            fill_quote_amount=fill_price * fill_size,
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _process_position_update_event(self, event: Dict[str, Any]):
        """Process position update from WebSocket."""
        try:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(event.get("market", ""))
            position_side = PositionSide.LONG if Decimal(str(event.get("size", "0"))) > 0 else PositionSide.SHORT
            unrealized_pnl = Decimal(str(event.get("unrealized_pnl", "0")))
            entry_price = Decimal(str(event.get("entry_price", "0")))
            amount = abs(Decimal(str(event.get("size", "0"))))
            leverage = Decimal(str(event.get("leverage", "1")))

            position = Position(
                trading_pair=trading_pair,
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=amount,
                leverage=leverage,
            )
            self._perpetual_trading.set_position(trading_pair, position)
        except Exception:
            self.logger().exception("Error processing position update")

    async def _process_balance_update_event(self, event: Dict[str, Any]):
        """Process balance update from WebSocket."""
        try:
            # Decibel balance format: {"asset": "USDC", "available": "1000.0", "total": "1000.0"}
            asset = event.get("asset", "USDC")
            available_balance = Decimal(str(event.get("available", "0")))
            total_balance = Decimal(str(event.get("total", "0")))

            self._account_available_balances[asset] = available_balance
            self._account_balances[asset] = total_balance
        except Exception:
            self.logger().exception("Error processing balance update")

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        """
        Convert Hummingbot trading pair to exchange symbol.

        Example: BTC-USD -> BTC/USD
        """
        if self._trading_pair_symbol_map is None:
            await self._initialize_trading_pair_symbol_map()

        return self._trading_pair_symbol_map.inverse.get(trading_pair, trading_pair)

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        """
        Convert exchange symbol to Hummingbot trading pair.

        Example: BTC/USD -> BTC-USD
        """
        if self._trading_pair_symbol_map is None:
            await self._initialize_trading_pair_symbol_map()

        return self._trading_pair_symbol_map.get(symbol, symbol)

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """
        Get last traded prices for multiple trading pairs.
        """
        result = {}
        for trading_pair in trading_pairs:
            try:
                price = await self._get_last_traded_price(trading_pair)
                result[trading_pair] = price
            except Exception:
                self.logger().exception(f"Error fetching price for {trading_pair}")
        return result

    # ========== Required Properties ==========

    @property
    def domain(self):
        """Exchange domain."""
        return self._domain

    @property
    def client_order_id_max_length(self):
        """Maximum length for client order IDs."""
        return 32

    @property
    def client_order_id_prefix(self):
        """Prefix for client order IDs."""
        return "HBOT"

    @property
    def trading_rules_request_path(self):
        """API path for trading rules."""
        return CONSTANTS.GET_MARKETS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        """API path for trading pairs."""
        return CONSTANTS.GET_MARKETS_PATH_URL

    @property
    def check_network_request_path(self):
        """API path for network health check."""
        return CONSTANTS.GET_MARKETS_PATH_URL

    @property
    def trading_pairs(self) -> Optional[List[str]]:
        """List of trading pairs."""
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Whether cancel requests are synchronous."""
        return True

    @property
    def is_trading_required(self) -> bool:
        """Whether trading is required."""
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        """
        Funding fee poll interval in seconds.
        Decibel updates funding every hour, poll every 2 minutes.
        """
        return 120

    # ========== Required Methods ==========

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Create web assistants factory."""
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self.authenticator,
        )

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """
        Fetch last funding fee payment.

        :return: (timestamp, funding_rate, payment_amount)
        """
        try:
            # Decibel API uses main wallet address, not derived subaccount
            account_addr = self.authenticator.main_wallet_address
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

            params = {
                "account": account_addr,
                "market": exchange_symbol,
                "limit": 1
            }

            response = await self._api_request(
                path_url=CONSTANTS.GET_USER_FUNDING_HISTORY_PATH_URL,
                params=params,
                method=RESTMethod.GET,
                limit_id=CONSTANTS.GET_USER_FUNDING_HISTORY_PATH_URL,
                is_auth_required=True,
            )

            if response.get("funding_payments"):
                last_payment = response["funding_payments"][0]
                timestamp = float(last_payment.get("timestamp", 0)) / 1000
                funding_rate = Decimal(str(last_payment.get("funding_rate", 0)))
                payment = Decimal(str(last_payment.get("payment", 0)))
                return timestamp, funding_rate, payment

        except Exception:
            self.logger().exception(f"Error fetching last fee payment for {trading_pair}")

        return 0, Decimal("0"), Decimal("0")

    async def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """Initialize trading pair symbol map from exchange info."""
        self._trading_pair_symbol_map = await self._create_trading_pair_symbol_map(exchange_info)

    def _is_order_not_found_during_cancelation_error(self, error: Exception) -> bool:
        """Check if error indicates order not found during cancellation."""
        error_str = str(error).lower()
        return "not found" in error_str or "does not exist" in error_str

    def _is_order_not_found_during_status_update_error(self, error: Exception) -> bool:
        """Check if error indicates order not found during status update."""
        error_str = str(error).lower()
        return "not found" in error_str or "does not exist" in error_str

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """Check if request exception is related to time synchronization."""
        error_str = str(request_exception).lower()
        return "timestamp" in error_str or "time" in error_str

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Set leverage for trading pair.

        Decibel uses account-level leverage, not per-pair.
        This is a placeholder - actual implementation would require on-chain transaction.

        :return: (success, message)
        """
        # TODO: Implement leverage setting via on-chain transaction
        self.logger().warning(f"Leverage setting not yet implemented for {trading_pair}")
        return False, "Leverage setting not yet implemented"

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        Set position mode for trading pair.

        Decibel only supports ONEWAY mode.

        :return: (success, message)
        """
        if mode != PositionMode.ONEWAY:
            return False, f"Decibel only supports ONEWAY position mode, got {mode}"
        return True, "Position mode is ONEWAY"

    async def _update_trading_fees(self):
        """
        Update trading fees.

        Decibel has fixed fees (0.015% maker, 0.04% taker).
        No need to fetch from API.
        """
        # Fees are fixed, no update needed
        pass
