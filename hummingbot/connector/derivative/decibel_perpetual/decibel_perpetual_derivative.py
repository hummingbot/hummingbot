import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict
from decibel import get_market_addr, get_perp_engine_global_address

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
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
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
        decibel_perpetual_api_wallet_private_key: str,
        decibel_perpetual_main_wallet_public_key: str,
        decibel_perpetual_api_key: str,
        decibel_perpetual_gas_station_api_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        use_auth_for_public_endpoints: bool = True,  # Decibel requires auth on all endpoints; accepted so non-trading instantiation paths (e.g. TradingPairFetcher) can pass it through.
    ):
        """
        Initialize Decibel Perpetual connector.

        Uses delegation pattern (like Pacifica):
        - API wallet signs all transactions
        - Main wallet delegates trading permissions to API wallet
        - Main wallet private key is NEVER exposed to the bot

        :param decibel_perpetual_api_wallet_private_key: API wallet private key (for signing)
        :param decibel_perpetual_main_wallet_public_key: Main wallet public key (for subaccount derivation)
        :param decibel_perpetual_api_key: Required API key from geomi.dev for all API access
        :param decibel_perpetual_gas_station_api_key: Required gas station API key for sponsored transactions
        :param trading_pairs: List of trading pairs to trade
        :param trading_required: Whether trading is required
        :param domain: Domain to use (mainnet or testnet)
        :param balance_asset_limit: Balance asset limits
        :param rate_limits_share_pct: Rate limit share percentage
        """
        self._api_wallet_private_key = decibel_perpetual_api_wallet_private_key
        self._main_wallet_public_key = decibel_perpetual_main_wallet_public_key
        self._api_key = decibel_perpetual_api_key
        self._gas_station_api_key = decibel_perpetual_gas_station_api_key

        # Credentials received correctly (verified via logs)
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

        # Reverse lookup: market_addr (hex) -> hummingbot trading pair.
        # Populated lazily. Needed because REST/WS position events return the market as
        # an on-chain address, not the market_name used in the symbol_map.
        self._market_addr_to_trading_pair: Dict[str, str] = {}

        # Market info cache
        self._market_info: Dict[str, Dict[str, Any]] = {}

        # Last poll timestamps
        self._last_poll_timestamp = 0

        super().__init__(balance_asset_limit=balance_asset_limit, rate_limits_share_pct=rate_limits_share_pct)

    @property
    def name(self) -> str:
        """Exchange name."""
        return self._domain

    async def _make_network_check_request(self):
        """
        Decibel requires authentication for all endpoints.
        """
        await self._api_get(
            path_url=self.check_network_request_path,
            is_auth_required=True,
        )

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

    def get_package_address(self) -> str:
        """
        Get the Decibel package address on Aptos.
        This is needed for deriving subaccount addresses.
        """
        if self._package_address is None:
            if self._domain == CONSTANTS.NETNA_DOMAIN:
                self._package_address = CONSTANTS.NETNA_PACKAGE
            elif self._domain == CONSTANTS.TESTNET_DOMAIN:
                self._package_address = CONSTANTS.TESTNET_PACKAGE
            else:
                self._package_address = CONSTANTS.MAINNET_PACKAGE
        return self._package_address

    def get_perp_engine_global_address(self) -> str:
        """
        Get the PerpEngineGlobal address derived from package address.
        This is needed for deriving market addresses.
        """
        package_address = self.get_package_address()
        return get_perp_engine_global_address(package_address)

    async def _get_transaction_builder(self) -> DecibelPerpetualTransactionBuilder:
        """
        Get or create transaction builder instance.
        """
        if self._transaction_builder is None:
            package_address = self.get_package_address()
            fullnode_url = web_utils.fullnode_url(self._domain)
            self._transaction_builder = DecibelPerpetualTransactionBuilder(
                auth=self.authenticator,
                package_address=package_address,
                fullnode_url=fullnode_url,
                domain=self._domain,
                api_key=self._api_key,
                gas_station_api_key=self._gas_station_api_key,
            )
        return self._transaction_builder

    def supported_order_types(self) -> List[OrderType]:
        """
        Decibel supports LIMIT, LIMIT_MAKER, and MARKET orders.
        Market orders are implemented as IOC orders with slippage.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        """
        Decibel only supports ONEWAY position mode (net positions).
        """
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        """
        Get collateral token for buy orders.
        Decibel uses USDC as collateral, but we return the quote asset to signal
        Hummingbot core that the collateral is 1:1 with the market quote.
        """
        base, quote = split_hb_trading_pair(trading_pair)
        return quote

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        """
        Get collateral token for sell orders.
        Decibel uses USDC as collateral, but we return the quote asset to signal
        Hummingbot core that the collateral is 1:1 with the market quote.
        """
        base, quote = split_hb_trading_pair(trading_pair)
        return quote

    async def _make_trading_rules_request(self) -> Any:
        """
        Fetch trading rules from Decibel API.
        Mainnet requires authentication for /api/v1/markets endpoint.
        """
        exchange_info = await self._api_get(
            path_url=CONSTANTS.GET_MARKETS_PATH_URL,
            limit_id=CONSTANTS.GET_MARKETS_PATH_URL,
            is_auth_required=True,  # Required for mainnet
        )
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        """
        Fetch available trading pairs from Decibel API.
        """
        return await self._make_trading_rules_request()

    def _create_trading_pair_symbol_map(self, exchange_info: Dict[str, Any]) -> bidict:
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
        Decibel API requires market address, not market name.

        Note: If market doesn't exist on mainnet yet, this will fail.
        Ensure the trading pair is available on the network.
        """
        try:
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

            if exchange_symbol is None:
                self.logger().error(f"Cannot get price for {trading_pair}: exchange symbol not found. Market may not exist on this network.")
                return 0.0

            # Convert market name to market address
            perp_engine_global = self.get_perp_engine_global_address()

            try:
                market_addr = get_market_addr(exchange_symbol, perp_engine_global)
            except Exception as e:
                self.logger().error(f"Cannot derive market address for {exchange_symbol}: {e}. Market may not exist on this network.")
                return 0.0

            params = {"market": market_addr}

            # Mainnet price endpoint requires authentication
            response = await self._api_get(
                path_url=CONSTANTS.GET_MARKET_PRICES_PATH_URL,
                params=params,
                limit_id=CONSTANTS.GET_MARKET_PRICES_PATH_URL,
                is_auth_required=True,  # Required for mainnet
                return_err=True,  # Return error response instead of raising
            )

            # Handle error response
            if isinstance(response, dict) and response.get("status") == "failed":
                self.logger().error(f"Price fetch failed for {trading_pair}: {response.get('message', 'Unknown error')}")
                return 0.0

            # Response is a list of market prices, get the first one
            if isinstance(response, list) and len(response) > 0:
                mark_px = response[0].get("mark_px")
                if mark_px is not None:
                    return float(mark_px)
            elif isinstance(response, dict):
                mark_px = response.get("mark_px")
                if mark_px is not None:
                    return float(mark_px)

            self.logger().error(f"No price data returned for {trading_pair} (market: {market_addr})")
            return 0.0

        except Exception as e:
            self.logger().error(f"Error fetching price for {trading_pair}: {e}", exc_info=True)
            return 0.0

    async def _update_trading_rules(self):
        """
        Update trading rules from exchange.
        """
        self.logger().debug("Updating trading rules...")
        exchange_info = await self._make_trading_rules_request()
        self.logger().debug(f"Received exchange info for trading rules: {len(exchange_info)} markets found.")
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self.logger().debug(f"Formatted {len(trading_rules_list)} trading rules.")
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
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_0,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        """
        Calculate trading fee.

        Uses the tier-specific TradeFeeSchema populated by _update_trading_fees
        (based on the user's 30-day volume) when available. Falls back to the
        DEFAULT_FEES Tier 0 schema from utils.py until the first successful poll
        — conservative overstatement rather than understatement.
        """
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)

        fee_schema: Optional[TradeFeeSchema] = self._trading_fees.get(trading_pair)
        if fee_schema is not None:
            percent = (fee_schema.maker_percent_fee_decimal if is_maker
                       else fee_schema.taker_percent_fee_decimal)
            flat_fees = (fee_schema.maker_fixed_fees if is_maker
                         else fee_schema.taker_fixed_fees)
            return TradeFeeBase.new_perpetual_fee(
                fee_schema=fee_schema,
                position_action=position_action,
                percent=percent,
                percent_token=fee_schema.percent_fee_token,
                flat_fees=flat_fees,
            )

        return build_perpetual_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            position_action=position_action,
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

        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_OVERVIEW_PATH_URL,
            params=params,
            limit_id=CONSTANTS.GET_ACCOUNT_OVERVIEW_PATH_URL,
            is_auth_required=True,
        )

        # Decibel API returns USD-denominated balances (field names contain "usdc" but represent USD value)
        # API response format: {"perp_equity_balance": 1000.0, "usdc_cross_withdrawable_balance": 1000.0, ...}
        # Balance is stored as USD to match the trading pair quote asset (BTC-USD, ETH-USD, etc.)
        total_balance = Decimal(str(response.get("perp_equity_balance", 0)))
        available_balance = Decimal(str(response.get("usdc_cross_withdrawable_balance", 0)))

        self.logger().debug(f"Updated balances - Total: {total_balance} USD, Available: {available_balance} USD")
        self._account_balances["USD"] = total_balance
        self._account_available_balances["USD"] = available_balance

    async def _update_positions(self):
        """
        Update positions from Decibel API.
        """
        # Decibel API uses main wallet address, not derived subaccount
        account_addr = self.authenticator.main_wallet_address

        params = {"account": account_addr}

        response = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_POSITIONS_PATH_URL,
            params=params,
            limit_id=CONSTANTS.GET_ACCOUNT_POSITIONS_PATH_URL,
            is_auth_required=True,
        )

        # Decibel format: {"positions": [{"market": "BTC/USD", "size": 1.5, "entry_price": 50000, ...}]}
        # or list format: [{"market": "BTC/USD", "size": 1.5, ...}]
        positions = response if isinstance(response, list) else response.get("positions", [])

        for position_data in positions:
            try:
                raw_market = position_data.get("market")
                trading_pair = await self._trading_pair_from_market_identifier(raw_market)
                if trading_pair is None:
                    # The Decibel positions API returned a market identifier we can't resolve.
                    # Storing it as-is would register the position under a hex address,
                    # preventing the strategy from recognizing / closing it (see QA reports
                    # where strategy appended buys instead of closing on fill).
                    self.logger().warning(
                        f"Skipping position with unknown market identifier: {raw_market}"
                    )
                    continue

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
        Fetch all trade updates for a specific order from trade history API.

        API requires: account, pagination, filter, sorting (all required)
        Optional: market, order_id (order_id requires market)
        """
        # Use direct attribute access to avoid timeout
        exchange_order_id = order.exchange_order_id
        if exchange_order_id is None:
            # Order doesn't have exchange_order_id yet - no trades to fetch
            return []

        account_addr = self.authenticator.main_wallet_address
        exchange_symbol = await self.exchange_symbol_associated_to_pair(order.trading_pair)

        # Convert market name to market address
        perp_engine_global = self.get_perp_engine_global_address()
        market_addr = get_market_addr(exchange_symbol, perp_engine_global)

        # Fetch trade history for the market
        params = {
            "account": account_addr,
            "market": market_addr,
            "order_id": exchange_order_id,
        }

        response = await self._api_get(
            path_url=CONSTANTS.GET_USER_TRADE_HISTORY_PATH_URL,
            params=params,
            limit_id=CONSTANTS.GET_USER_TRADE_HISTORY_PATH_URL,
            is_auth_required=True,
        )

        updates = []
        for trade in response.get("trades", []):
            fee_amount = Decimal(str(trade.get("fee", "0")))
            fee_asset = order.quote_asset
            fill_price = Decimal(str(trade.get("price", "0")))
            fill_size = Decimal(str(trade.get("size", "0")))
            updates.append(TradeUpdate(
                trade_id=str(trade.get("trade_id", "")),
                client_order_id=order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=order.trading_pair,
                fill_timestamp=trade.get("timestamp", time.time() * 1000) / 1000,
                fill_price=fill_price,
                fill_base_amount=fill_size,
                fill_quote_amount=fill_price * fill_size,
                fee=TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=order.position,
                    percent_token=fee_asset,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_asset)],
                ),
            ))
        return updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status from exchange via REST API.
        Uses /api/v1/orders endpoint to fetch single order by order_id.
        """
        account_addr = self.authenticator.main_wallet_address
        exchange_order_id = tracked_order.exchange_order_id

        # If order doesn't have exchange_order_id yet, it hasn't been submitted
        # Return PENDING_CREATE to signal the base class to retry later
        if exchange_order_id is None:
            return OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=None,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.PENDING_CREATE,
            )

        exchange_symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)

        # Convert market name to market address
        perp_engine_global = self.get_perp_engine_global_address()
        market_addr = get_market_addr(exchange_symbol, perp_engine_global)

        # Fetch single order by order_id
        response = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_PATH_URL,
            params={"account": account_addr, "market": market_addr, "order_id": exchange_order_id},
            limit_id=CONSTANTS.GET_ORDER_PATH_URL,
            is_auth_required=True,
        )

        # Response format per API docs:
        # Success: {"status": "Filled", "details": "", "order": {...}}
        # Not found: {"status": "notFound", "message": "Order with order_id: 123 not found"}
        order_status = response.get("status", "")

        if order_status == "notFound":
            # Order not found - treat as cancelled
            state = OrderState.CANCELED
            timestamp = time.time() * 1000
        else:
            new_state_from_api = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)

            # Don't overwrite terminal state (CANCELED) with non-terminal state (OPEN) from API.
            # This prevents race conditions where API returns stale "Open" status after we've
            # already confirmed the cancel locally (blockchain propagation delay).
            # Pattern used by dYdX and other blockchain-based connectors.
            if new_state_from_api == OrderState.OPEN and tracked_order.current_state == OrderState.CANCELED:
                self.logger().debug(
                    f"Ignoring stale 'Open' status for canceled order {exchange_order_id}"
                )
                state = OrderState.CANCELED
                order_data = response.get("order", {})
                timestamp = order_data.get("unix_ms", time.time() * 1000)
            else:
                state = new_state_from_api
                order_data = response.get("order", {})
                timestamp = order_data.get("unix_ms", time.time() * 1000)

        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=timestamp / 1000,
            new_state=state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
        )

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

            # Use mid price as mark price.
            # OrderBook.get_price() returns float; convert to Decimal at the boundary
            # so the rest of the price math (slippage, chain-unit conversion) stays Decimal.
            best_ask = Decimal(str(order_book.get_price(True)))
            best_bid = Decimal(str(order_book.get_price(False)))
            mark_price = (best_ask + best_bid) / Decimal("2")

            # Apply slippage: BUY adds slippage, SELL subtracts slippage
            if is_buy:
                price = mark_price * (Decimal("1") + CONSTANTS.MARKET_ORDER_SLIPPAGE)
            else:
                price = mark_price * (Decimal("1") - CONSTANTS.MARKET_ORDER_SLIPPAGE)

            # Decibel rejects any price that is not a multiple of the market's
            # tick_size (min_price_increment) with Move abort
            # ``EPRICE_NOT_RESPECTING_TICKER_SIZE(0x6)``. For LIMIT orders the
            # exchange base already quantizes, but MARKET orders compute a fresh
            # price from the order book here, so we must quantize it ourselves
            # before converting to chain units.
            unquantized_price = price
            price = self.quantize_order_price(trading_pair, price)

            self.logger().debug(
                f"Market order converted to IOC: mark_price={mark_price}, "
                f"slippage={CONSTANTS.MARKET_ORDER_SLIPPAGE}, "
                f"unquantized_price={unquantized_price}, limit_price={price}"
            )

        # Convert to chain units (not needed for SDK, but keep for logging)
        chain_price = self._convert_price_to_chain_units(trading_pair, price)
        chain_size = self._convert_size_to_chain_units(trading_pair, amount)

        # Retry logic: attempt order placement up to 3 times with 5-second delays
        # Uses new SDK exceptions (TxnSubmitError, TxnConfirmError) for precise error handling
        from decibel import TxnConfirmError, TxnSubmitError

        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                self.logger().info(
                    f"Placing order: {trading_pair} {trade_type.name} {amount} @ {price} "
                    f"(chain: {chain_size} @ {chain_price}) (attempt {attempt}/{max_retries})"
                )

                # Get transaction builder
                tx_builder = await self._get_transaction_builder()

                # Submit order transaction (SDK expects chain units)
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
                    f"Order placed successfully: client_order_id={order_id}, exchange_order_id={exchange_order_id}, tx_hash={tx_hash}"
                )

                return exchange_order_id, timestamp

            except TxnSubmitError as e:
                # Transaction submission failed - never reached blockchain
                # SAFE TO RETRY
                if attempt < max_retries:
                    self.logger().warning(
                        f"[ORDER RETRY {attempt}/{max_retries}] client={order_id} submission failed [{e}], retrying in 5s..."
                    )
                    await asyncio.sleep(5)
                else:
                    self.logger().error(f"[ORDER SUBMIT FAILED] client={order_id} placement failed after {max_retries} retries: {e}")
                    raise

            except TxnConfirmError as e:
                # Transaction was submitted but confirmation timed out/failed
                # Transaction MAY be on-chain - retry since we're not sure
                if attempt < max_retries:
                    self.logger().warning(
                        f"[ORDER RETRY {attempt}/{max_retries}] client={order_id} confirmation issue [{e}], retrying in 5s..."
                    )
                    await asyncio.sleep(5)
                else:
                    self.logger().error(f"[ORDER CONFIRM ISSUE] client={order_id} confirmation failed after {max_retries} retries: {e}")
                    raise

            except Exception as e:
                # Unknown error (e.g., PlaceOrderFailure with actual error)
                self.logger().error(f"Error placing order: {e}", exc_info=True)
                raise

        # Should not reach here
        raise RuntimeError("Order placement retry loop exited unexpectedly")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        Cancel order on Decibel exchange.

        Like order placement, cancellation is done via on-chain transaction.
        Uses new SDK exceptions (TxnSubmitError, TxnConfirmError) for precise error handling.

        :return: True if cancellation was successful
        """
        from decibel import TxnConfirmError, TxnSubmitError

        self.logger().debug(f"[CANCEL ATTEMPT] order_id={order_id}, exchange_order_id={tracked_order.exchange_order_id}")

        # Get exchange_order_id, waiting for it if order placement is still pending
        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            self.logger().debug(f"[CANCEL] Got exchange_order_id={exchange_order_id} for {order_id}")
        except asyncio.TimeoutError:
            self.logger().warning(
                f"[CANCEL] Timeout waiting for exchange_order_id for order {order_id}. "
                f"Order may not have been submitted to the exchange."
            )
            await self._order_tracker.process_order_not_found(order_id)
            return False

        if exchange_order_id is None:
            self.logger().warning(
                f"[CANCEL] Cannot cancel order {order_id} - no exchange_order_id. "
                f"The order placement may have failed."
            )
            return False

        try:
            trading_pair = tracked_order.trading_pair
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)

            self.logger().debug(f"[CANCEL] Submitting cancel: exchange_order_id={exchange_order_id} for {trading_pair}")

            # Retry logic: attempt cancel up to 3 times with 5-second delays
            # Handles TxnSubmitError (safe to retry) vs TxnConfirmError (may be on-chain)
            max_retries = 3

            for attempt in range(1, max_retries + 1):
                try:
                    # Get transaction builder (inside retry loop so initialization failures are retried)
                    tx_builder = await self._get_transaction_builder()

                    # Submit cancel transaction
                    tx_hash, timestamp = await tx_builder.cancel_order(
                        market_id=exchange_symbol,
                        order_id=exchange_order_id,
                    )

                    if tx_hash:
                        self.logger().debug(f"[CANCEL SUCCESS] client={order_id} exchange={exchange_order_id} canceled: tx_hash={tx_hash} (attempt {attempt}/{max_retries})")
                    else:
                        self.logger().warning(f"[CANCEL] client={order_id} exchange={exchange_order_id} cancel submitted but no tx_hash received")

                    return True

                except TxnSubmitError as e:
                    # Submission failed - transaction never reached blockchain
                    # SAFE TO RETRY
                    if attempt < max_retries:
                        self.logger().warning(
                            f"[CANCEL RETRY {attempt}/{max_retries}] client={order_id} exchange={exchange_order_id} submission failed [{e}], retrying in 5s..."
                        )
                        await asyncio.sleep(5)
                    else:
                        self.logger().warning(
                            f"[CANCEL SUBMIT FAILED] client={order_id} exchange={exchange_order_id} after {max_retries} retries: {e}. Will retry after cooldown."
                        )
                        return False

                except TxnConfirmError as e:
                    # Transaction was submitted but confirmation timed out or failed
                    # Transaction MAY be on-chain - return True to mark as PENDING_CANCEL
                    # Let WebSocket/polling confirm final state
                    self.logger().warning(
                        f"[CANCEL CONFIRM TIMEOUT] client={order_id} exchange={exchange_order_id}: {e} - may already be on-chain. "
                        f"Letting WS/polling confirm final state."
                    )
                    return True

                except Exception as e:
                    # Unknown error - retry since we can't tell if tx was submitted
                    if attempt < max_retries:
                        self.logger().warning(
                            f"[CANCEL RETRY {attempt}/{max_retries}] client={order_id} exchange={exchange_order_id} unexpected error [{e}], retrying in 5s..."
                        )
                        await asyncio.sleep(5)
                    else:
                        self.logger().error(
                            f"[CANCEL ERROR] client={order_id} exchange={exchange_order_id} failed after {max_retries} retries: {e}"
                        )
                        return False

            return False

        except ValueError as e:
            # Handle on-chain errors like "EORDER_NOT_FOUND"
            error_message = str(e)
            if "EORDER_NOT_FOUND" in error_message:
                self.logger().debug(
                    f"[CANCEL CONFIRMED] client={order_id} exchange={exchange_order_id} not found on-chain - already canceled/filled. Stopping tracking."
                )
                # Explicitly stop tracking to remove from active_orders immediately
                self.stop_tracking_order(order_id)
                return True
            else:
                self.logger().error(f"[CANCEL ERROR] client={order_id} exchange={exchange_order_id}: {e}")
                return False

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

            response = await self._api_get(
                path_url=CONSTANTS.GET_USER_TRADE_HISTORY_PATH_URL,
                params=params,
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
                        fee_schema=self.trade_fee_schema(),
                        position_action=tracked_order.position,
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

        Decibel WS messages carry a "topic" field like:
          "account_open_orders:0x...", "user_trades:0x...",
          "user_positions:0x...", "account_overview:0x..."
        Route by topic prefix, not a 'type' field (which doesn't exist).
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if not isinstance(event_message, dict):
                    continue

                topic = event_message.get("topic", "")
                data = event_message.get("data", event_message)

                if CONSTANTS.WS_ORDER_UPDATE_CHANNEL in topic:
                    await self._process_order_update_event(data)
                elif CONSTANTS.WS_USER_OPEN_ORDERS_CHANNEL in topic:
                    # account_open_orders: process each order in the list
                    for order_data in (data if isinstance(data, list) else data.get("orders", [])):
                        await self._process_order_update_event(order_data)
                elif CONSTANTS.WS_USER_TRADES_CHANNEL in topic:
                    # user_trades: process each trade in the list
                    for trade_data in (data if isinstance(data, list) else data.get("trades", [])):
                        await self._process_trade_event(trade_data)
                elif CONSTANTS.WS_USER_POSITIONS_CHANNEL in topic:
                    # user_positions: process each position in the list
                    for pos_data in (data if isinstance(data, list) else data.get("positions", [])):
                        await self._process_position_update_event(pos_data)
                elif CONSTANTS.WS_ACCOUNT_OVERVIEW_CHANNEL in topic:
                    await self._process_balance_update_event(data)

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
        new_state = CONSTANTS.ORDER_STATE.get(current_state, OrderState.FAILED)

        # Ignore "Open" status updates for orders that have been explicitly canceled
        # This prevents race conditions where WS updates arrive after local cancel confirmation
        if new_state == OrderState.OPEN and tracked_order.current_state == OrderState.CANCELED:
            self.logger().debug(
                f"Ignoring stale 'Open' status for canceled order {exchange_order_id}"
            )
            return

        update_timestamp = event.get("timestamp", time.time() * 1000) / 1000

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
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
            raw_market = event.get("market", "")
            trading_pair = await self._trading_pair_from_market_identifier(raw_market)
            if trading_pair is None:
                # Same guard as in _update_positions - don't register a position under
                # an unresolved hex market address.
                self.logger().warning(
                    f"Ignoring WS position update with unknown market identifier: {raw_market}"
                )
                return

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
            # Decibel WebSocket returns account_overview object:
            # {"perp_equity_balance": 1000.0, "usdc_cross_withdrawable_balance": 1000.0, ...}
            # The data may be nested under "account_overview" key or be the event itself
            overview = event.get("account_overview", event)

            total_balance = Decimal(str(overview.get("perp_equity_balance", 0)))
            available_balance = Decimal(str(overview.get("usdc_cross_withdrawable_balance", 0)))

            # Guard: Ignore 0 balance updates from WS if we already have a positive balance from REST
            # This handles the case where WS sends 0 during initial sync or for pending state
            current_available = self._account_available_balances.get("USD", Decimal("0"))
            if available_balance == 0 and current_available > 0:
                self.logger().debug(f"Ignoring 0 balance update from WS as we have a positive balance ({current_available}) from REST.")
                return

            self._account_available_balances["USD"] = available_balance
            self._account_balances["USD"] = total_balance
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

    async def _trading_pair_from_market_identifier(self, market_id: str) -> Optional[str]:
        """
        Resolve a Decibel ``market`` field (as returned by REST/WS payloads) to a
        Hummingbot trading pair.

        Decibel is inconsistent about what this field contains:
        - ``/api/v1/markets`` returns ``market_name`` (e.g., ``"BTC/USD"``), which is
          what ``_trading_pair_symbol_map`` is keyed on.
        - Position and trade payloads often return the on-chain ``market_addr`` (hex
          like ``"0x0b5031a8ca..."``), which is NOT in the symbol map.

        This helper tries the market_name path first, then falls back to a
        ``market_addr -> trading_pair`` cache that we build lazily from the symbol
        map by deriving addresses via ``get_market_addr``. Returns ``None`` if the
        identifier can't be resolved, so callers can skip the update instead of
        silently storing a position under a hex key (which breaks position close /
        reduce-only logic in strategies).
        """
        if not market_id:
            return None

        if self._trading_pair_symbol_map is None:
            await self._initialize_trading_pair_symbol_map()

        # Direct hit: market_name like "BTC/USD"
        if market_id in self._trading_pair_symbol_map:
            return self._trading_pair_symbol_map[market_id]

        # Fallback: on-chain market address. Build / refresh the reverse map.
        if market_id not in self._market_addr_to_trading_pair:
            try:
                perp_engine_global = self.get_perp_engine_global_address()
            except Exception:
                self.logger().exception("Could not derive perp_engine_global address for market_addr reverse lookup")
                return None

            for exchange_symbol, trading_pair in self._trading_pair_symbol_map.items():
                try:
                    addr = get_market_addr(exchange_symbol, perp_engine_global)
                except Exception:
                    self.logger().debug(f"Skipping {exchange_symbol} in market_addr reverse map: get_market_addr failed", exc_info=True)
                    continue
                self._market_addr_to_trading_pair[addr] = trading_pair

        return self._market_addr_to_trading_pair.get(market_id)

    async def get_market_addr_for_pair(self, trading_pair: str) -> str:
        """
        Compute market address for a trading pair using the Decibel SDK.
        No HTTP request needed — it's a deterministic derivation.
        """
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        perp_engine_global = self.get_perp_engine_global_address()
        return get_market_addr(exchange_symbol, perp_engine_global)

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
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various exchange's components. Used to determine if the connector is ready
        """
        return super().status_dict

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
        """
        Whether cancel requests are synchronous.

        Decibel cancel is SYNCHRONOUS because:
        1. SDK waits for confirmation (120s timeout)
        2. On success, order is immediately CANCELED and removed from tracking
        3. On timeout or "not found" errors, _is_order_not_found_during_cancelation_error()
           captures them and base class handles cleanup properly

        This ensures orders are removed from active_orders immediately after cancel,
        allowing new orders to be placed without waiting.
        """
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
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
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

            # Convert market name to market address
            perp_engine_global = self.get_perp_engine_global_address()
            market_addr = get_market_addr(exchange_symbol, perp_engine_global)

            params = {
                "account": account_addr,
                "market": market_addr,
                "limit": 1
            }

            response = await self._api_get(
                path_url=CONSTANTS.GET_USER_FUNDING_HISTORY_PATH_URL,
                params=params,
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

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """Initialize trading pair symbol map from exchange info."""
        self._trading_pair_symbol_map = self._create_trading_pair_symbol_map(exchange_info)
        self._set_trading_pair_symbol_map(self._trading_pair_symbol_map)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """
        Check if error indicates order not found during cancellation.

        Decibel on-chain error:
        - "EORDER_NOT_FOUND": Order was already filled, cancelled, or never existed
          (Move abort in 0x...::single_order_book::EORDER_NOT_FOUND)

        When this returns True, the base class calls process_order_not_found()
        which moves the order to _lost_orders.

        NOTE: We also explicitly stop tracking in _place_cancel when we get
        EORDER_NOT_FOUND to immediately remove from active_orders.
        """
        return "EORDER_NOT_FOUND" in str(cancelation_exception)

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        """
        Override time synchronizer update for blockchain-based exchange.
        Decibel uses Aptos blockchain timestamps, so no server time sync needed.
        """
        # No-op: blockchain timestamps are validated on-chain
        pass

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """
        Check if error indicates order not found during status update.

        This is called when REST API calls in _update_order_status fail with an exception.
        Note: The API normally returns {"status": "notFound"} for missing orders,
        which is handled gracefully without raising an exception.

        This method catches edge cases where "not found" appears in exception messages.
        """
        error_str = str(status_update_exception).lower()
        return "not found" in error_str or "does not exist" in error_str

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """Check if request exception is related to time synchronization."""
        error_str = str(request_exception).lower()
        return "timestamp" in error_str or "time" in error_str

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Set leverage for trading pair.
        Decibel handles leverage per trade or at account level.
        Treating as success to allow strategy to proceed.
        """
        return True, ""

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        Set position mode for trading pair.
        Decibel only supports ONEWAY mode.
        """
        if mode == PositionMode.ONEWAY:
            return True, ""
        return False, f"Position mode {mode} not supported by Decibel."

    @staticmethod
    def _fees_for_30d_volume(volume: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Map a 30-day USD trading volume to (maker_decimal, taker_decimal) using
        CONSTANTS.FEE_TIER_SCHEDULE. The schedule is sorted high-to-low, so the
        first matching threshold wins. Tier 0 (min_volume=0) guarantees a match.
        """
        for _tier, min_volume, maker, taker in CONSTANTS.FEE_TIER_SCHEDULE:
            if volume >= min_volume:
                return maker, taker

    async def _update_trading_fees(self):
        """
        Update trading fees based on the user's 30-day volume tier.

        Decibel exposes tier-dependent fees (Tier 0: 0.0110% maker / 0.0340% taker,
        decreasing at higher tiers with maker reaching 0% from Tier 4 onward).
        There is no direct "current fee tier" endpoint, so - per guidance from
        the Decibel team - we derive the tier by reading the 30-day volume from
        /api/v1/account_overviews (with volume_window="30d") and mapping it
        against CONSTANTS.FEE_TIER_SCHEDULE.

        On transient failure we leave any previously computed fees in place so
        strategies keep working; the base class polling loop will retry.
        """
        account_addr = self.authenticator.main_wallet_address
        try:
            response = await self._api_get(
                path_url=CONSTANTS.GET_ACCOUNT_OVERVIEW_PATH_URL,
                params={"account": account_addr, "volume_window": CONSTANTS.VOLUME_WINDOW_30D},
                limit_id=CONSTANTS.GET_ACCOUNT_OVERVIEW_PATH_URL,
                is_auth_required=True,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().warning(
                "Failed to fetch 30d volume from account_overviews; keeping previous "
                "fee tier. Strategies will temporarily use the last-known (or Tier 0 default) fees.",
                exc_info=True,
            )
            return

        # `volume` may be null for accounts with no trading history → treat as 0 (Tier 0).
        volume_30d = Decimal(str(response.get("volume") or 0))
        maker_decimal, taker_decimal = self._fees_for_30d_volume(volume_30d)

        fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=maker_decimal,
            taker_percent_fee_decimal=taker_decimal,
        )
        # Tier is account-wide, so the same schema applies to every trading pair.
        for trading_pair in self._trading_pairs:
            self._trading_fees[trading_pair] = fee_schema

        self.logger().debug(
            f"Updated trading fees from 30d volume ${volume_30d}: "
            f"maker={maker_decimal}, taker={taker_decimal}"
        )

    async def get_all_pairs_prices(self) -> List[Dict[str, Any]]:
        """
        Retrieves the prices (mark price) for all trading pairs.
        Required for Rate Oracle support.

        Decibel API returns prices per market address, so we:
        1. Fetch all markets to get market_name -> market_addr mapping
        2. Fetch prices for each market
        3. Return list of {trading_pair, price} dicts

        Sample output:
        [
            {"trading_pair": "BTC-USD", "price": "50120.5"},
            {"trading_pair": "ETH-USD", "price": "3200.0"},
        ]
        """
        try:
            # Ensure trading pair symbol map is initialized
            if self._trading_pair_symbol_map is None:
                await self._initialize_trading_pair_symbol_map()

            # If map is still None after initialization attempt, return empty
            if self._trading_pair_symbol_map is None:
                self.logger().debug("[get_all_pairs_prices] Trading pair symbol map could not be initialized")
                return []

            results = []
            perp_engine_global = self.get_perp_engine_global_address()

            # Iterate through known markets and fetch prices
            for exchange_symbol, hb_trading_pair in self._trading_pair_symbol_map.items():
                try:
                    market_addr = get_market_addr(exchange_symbol, perp_engine_global)

                    response = await self._api_get(
                        path_url=CONSTANTS.GET_MARKET_PRICES_PATH_URL,
                        params={"market": market_addr},
                        limit_id=CONSTANTS.GET_MARKET_PRICES_PATH_URL,
                        is_auth_required=True,
                    )

                    # Response is a list of market prices or a single price dict
                    if isinstance(response, list) and len(response) > 0:
                        price_data = response[0]
                    elif isinstance(response, dict):
                        price_data = response
                    else:
                        continue

                    mark_px = price_data.get("mark_px")
                    if mark_px is not None:
                        results.append({
                            "trading_pair": hb_trading_pair,
                            "price": str(mark_px),
                        })
                except Exception:
                    self.logger().debug(f"Failed to fetch price for {exchange_symbol}")
                    continue

            return results
        except Exception as e:
            self.logger().error(f"[get_all_pairs_prices] Failed to fetch all pairs prices: {e}")
            return []
