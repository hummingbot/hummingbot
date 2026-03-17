"""Limitless Exchange connector for Hummingbot.

Wraps the existing LimitlessConnector class from connector.py, delegating all
API interaction (order placement, cancellation, balance queries, orderbook
fetching) to it. This class implements Hummingbot's ExchangePyBase interface.
"""

import asyncio
import hashlib
import logging
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.limitless import limitless_constants as CONSTANTS, limitless_web_utils as web_utils

# Import the inner connector — symlinked into this package
from hummingbot.connector.exchange.limitless.connector import LimitlessConnector
from hummingbot.connector.exchange.limitless.limitless_api_order_book_data_source import LimitlessAPIOrderBookDataSource
from hummingbot.connector.exchange.limitless.limitless_api_user_stream_data_source import (
    LimitlessAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.limitless.limitless_auth import LimitlessAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

logger = logging.getLogger(__name__)


class LimitlessExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
        self,
        limitless_api_key: str = "",
        limitless_private_key: str = "",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        self._api_key = limitless_api_key
        self._private_key = limitless_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []
        self._domain = domain
        self._last_trade_history_timestamp = None

        # Trading pair <-> market slug mapping
        # Populated during _initialize_trading_pair_symbol_map
        self._slug_map: Dict[str, str] = {}  # trading_pair -> slug
        self._slug_reverse_map: Dict[str, str] = {}  # slug -> trading_pair
        self._market_data: Dict[str, dict] = {}  # slug -> market dict

        # Inner connector — handles all actual API calls
        self._inner_connector: Optional[LimitlessConnector] = None
        self._inner_started = False

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    # ── Inner connector lifecycle ───────────────────────────────

    async def _ensure_inner_connector(self):
        """Lazily create and start the inner LimitlessConnector."""
        if self._inner_started:
            return
        if self._inner_connector is None:
            self._inner_connector = LimitlessConnector(
                api_key=self._api_key,
                private_key=self._private_key,
                markets=[],  # will be populated per trading pair
                paper_mode=False,
                max_order_size_usd=100.0,
                ws_enabled=True,
            )
        await self._inner_connector.start()
        self._inner_started = True

    async def _stop_inner_connector(self):
        if self._inner_connector and self._inner_started:
            await self._inner_connector.stop()
            self._inner_started = False

    # ── Network lifecycle ──────────────────────────────────────

    async def start_network(self):
        """Override to eagerly initialize symbol map and trading rules."""
        await self._ensure_inner_connector()
        await self._initialize_trading_pair_symbol_map()
        await self._update_trading_rules()
        await self._update_balances()
        await super().start_network()

    # ── Readiness ─────────────────────────────────────────────

    @property
    def status_dict(self) -> Dict[str, bool]:
        # For Limitless, the inner connector handles orderbook via WS.
        # Skip the HB orderbook tracker ready check if inner connector has cached orderbooks.
        ob_ready = self.order_book_tracker.ready if self.order_book_tracker else False
        if not ob_ready and self._inner_started and self._inner_connector:
            # Check if inner connector has any cached orderbooks
            cached = self._inner_connector.cached_orderbooks
            if cached:
                ob_ready = True
        sd = {
            "symbols_mapping_initialized": self.trading_pair_symbol_map_ready(),
            "order_books_initialized": ob_ready,
            "account_balance": not self.is_trading_required or len(self._account_balances) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self.is_trading_required else True,
            "user_stream_initialized": self._is_user_stream_initialized(),
            "inner_connector_started": self._inner_started,
        }
        not_ready = {k: v for k, v in sd.items() if not v}
        if not_ready:
            logger.warning("LimitlessExchange status_dict not ready: %s", not_ready)
        return sd

    # ── ExchangePyBase required properties ──────────────────────

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[LimitlessAuth]:
        if self._trading_required:
            return LimitlessAuth(self._api_key, self._private_key)
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
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_URL

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
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    # ── Network / ping ──────────────────────────────────────────

    async def _make_network_check_request(self):
        await self._ensure_inner_connector()

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    # ── Trading pair / symbol mapping ───────────────────────────

    # ── Pass-through methods for controller access ─────────────

    async def get_active_markets(self, ticker: Optional[str] = None) -> list:
        """Delegate to inner connector."""
        await self._ensure_inner_connector()
        return await self._inner_connector.get_active_markets(ticker=ticker)

    async def get_order_book_data(self, market_slug: str) -> dict:
        """Fetch raw orderbook data from inner connector (for market_manager).

        Named to avoid shadowing ExchangeBase.get_order_book() which the
        Cython layer calls synchronously and expects an OrderBook object.
        """
        await self._ensure_inner_connector()
        return await self._inner_connector.get_order_book(market_slug)

    async def get_market(self, market_slug: str) -> dict:
        """Delegate to inner connector."""
        await self._ensure_inner_connector()
        return await self._inner_connector.get_market(market_slug)

    # ── Slug mapping ─────────────────────────────────────────────

    def _trading_pair_to_slug(self, trading_pair: str) -> str:
        """Convert Hummingbot trading pair to Limitless market slug."""
        return self._slug_map.get(trading_pair, trading_pair)

    def _slug_to_trading_pair(self, slug: str) -> Optional[str]:
        """Convert Limitless market slug to Hummingbot trading pair."""
        return self._slug_reverse_map.get(slug)

    def _make_trading_rule(self, trading_pair: str) -> TradingRule:
        """Create a standard TradingRule for a Limitless market."""
        return TradingRule(
            trading_pair=trading_pair,
            min_order_size=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.01"),
            min_price_increment=Decimal("0.001"),
            min_order_value=Decimal("0.01"),
        )

    @staticmethod
    def _is_no_pair(trading_pair: str) -> bool:
        """Check if a trading pair is a NO-side pair (e.g. ETHNO-USDC)."""
        base = trading_pair.split("-")[0]
        return base.endswith("NO")

    @staticmethod
    def _yes_pair(no_tp: str) -> str:
        """Convert a NO pair back to YES pair: ETHNO-USDC -> ETH-USDC."""
        base, quote = no_tp.split("-", 1)
        return f"{base[:-2]}-{quote}"  # strip 'NO' suffix from base

    @staticmethod
    def no_pair(yes_tp: str) -> str:
        """Derive the NO-side trading pair from a YES pair.

        ETH-USDC -> ETHNO-USDC (single dash, compatible with Hummingbot's
        base-quote split convention).
        """
        return yes_tp.replace("-USDC", "NO-USDC")

    def _ensure_no_pair(self, yes_tp: str, slug: str):
        """Ensure the NO-side trading pair exists for a YES pair.

        Every YES pair (e.g. ETH-USDC) needs a corresponding NO pair
        (ETHNO-USDC) so executors can trade the NO token. Both map to
        the same market slug — the connector routes by detecting 'NO-'
        prefix in the base token.
        """
        no_tp = self.no_pair(yes_tp)
        if no_tp == yes_tp or no_tp in self._trading_rules:
            return  # not a USDC pair, or already registered
        self._slug_map[no_tp] = slug
        self._trading_rules[no_tp] = self._make_trading_rule(no_tp)
        logger.info("Registered NO-side pair: %s -> %s", no_tp, slug)

    async def register_market(self, slug: str, trading_pair: Optional[str] = None):
        """Dynamically register a market slug so executors can trade it.

        Idempotent — safe to call repeatedly. Creates both YES and NO
        trading pairs on first registration, and backfills the NO pair
        if only the YES pair existed (e.g. from startup discovery).

        Args:
            slug: Limitless market slug (e.g. 'dollareth-above-...')
            trading_pair: Hummingbot trading pair label (defaults to slug)
        """
        tp = trading_pair or slug

        if slug in self._slug_reverse_map:
            # YES side already known — just ensure NO pair exists
            self._ensure_no_pair(tp, slug)
            return

        # --- First registration: full setup ---
        self._slug_map[tp] = slug
        self._slug_reverse_map[slug] = tp

        # Symbol map for orderbook tracker
        try:
            self._trading_pair_symbol_map[slug] = tp
        except Exception:
            pass  # bidict may reject duplicates

        # Cache market data + subscribe WS
        await self._ensure_inner_connector()
        if slug not in self._inner_connector._markets:
            await self._inner_connector.get_market(slug)
        await self._inner_connector.subscribe_market(slug)

        # Trading rules for YES side
        self._trading_rules[tp] = self._make_trading_rule(tp)
        logger.info("Registered dynamic market: %s -> %s", tp, slug)

        # Trading rules for NO side
        self._ensure_no_pair(tp, slug)

    def get_price_by_type(self, trading_pair: str, price_type) -> Decimal:
        """Override to handle NO-side pairs by flipping YES orderbook prices."""
        if self._is_no_pair(trading_pair):
            # Look up the YES pair's price and flip it
            yes_tp = self._yes_pair(trading_pair)
            try:
                yes_price = super().get_price_by_type(yes_tp, price_type)
                return Decimal("1") - yes_price
            except Exception:
                return Decimal("0.5")  # safe fallback
        return super().get_price_by_type(trading_pair, price_type)

    def get_trading_rules(self) -> Dict[str, TradingRule]:
        """Return all trading rules including dynamically registered ones."""
        return self._trading_rules

    async def _initialize_trading_pair_symbol_map(self):
        """Discover markets from Limitless and build the symbol mapping.

        For each configured trading pair (e.g. "BTC-USDC"), we resolve the
        ticker part (BTC) to find active markets, then map the trading pair
        to the first matching market slug.
        """
        try:
            logger.info("Initializing trading pair symbol map for: %s", self._trading_pairs)
            await self._ensure_inner_connector()
            mapping = bidict()

            for tp in self._trading_pairs:
                parts = tp.split("-")
                ticker = parts[0] if parts else tp

                try:
                    markets = await self._inner_connector.get_active_markets(ticker=ticker)
                    logger.info("Found %d markets for ticker %s", len(markets), ticker)
                except Exception:
                    self.logger().warning(f"Failed to discover markets for ticker {ticker}", exc_info=True)
                    markets = []

                if markets:
                    # Use the first active market for this ticker
                    market = markets[0]
                    slug = market["slug"]
                    self._slug_map[tp] = slug
                    self._slug_reverse_map[slug] = tp
                    self._market_data[slug] = market
                    mapping[slug] = tp
                    logger.info("Mapped %s -> %s", tp, slug)

                    # Ensure the inner connector has this market cached
                    if slug not in self._inner_connector._markets:
                        await self._inner_connector.get_market(slug)
                    # Subscribe WS
                    await self._inner_connector.subscribe_market(slug)
                else:
                    self.logger().warning(f"No active markets found for {tp}")
                    # Create a pass-through mapping so connector can still start
                    mapping[tp] = tp
                    self._slug_map[tp] = tp
                    self._slug_reverse_map[tp] = tp

            self._set_trading_pair_symbol_map(mapping)
            logger.info("Trading pair symbol map initialized: %s", dict(mapping))
        except Exception:
            self.logger().exception("Error initializing trading pair symbol map.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Any):
        # Not used — we override _initialize_trading_pair_symbol_map directly
        pass

    # ── Trading rules ───────────────────────────────────────────

    async def _make_trading_rules_request(self) -> Any:
        return self._market_data

    async def _make_trading_pairs_request(self) -> Any:
        return self._market_data

    async def _update_trading_rules(self):
        await self._ensure_inner_connector()
        # Refresh market data for all configured pairs
        for tp in self._trading_pairs:
            slug = self._trading_pair_to_slug(tp)
            if slug and slug != tp:
                try:
                    market = await self._inner_connector.get_market(slug)
                    self._market_data[slug] = market
                except Exception:
                    self.logger().warning(f"Failed to refresh market data for {slug}")

        trading_rules = await self._format_trading_rules(self._market_data)
        self._trading_rules.clear()
        for rule in trading_rules:
            self._trading_rules[rule.trading_pair] = rule

    async def _format_trading_rules(self, market_data: Dict[str, dict]) -> List[TradingRule]:
        rules = []
        for slug, market in market_data.items():
            tp = self._slug_reverse_map.get(slug, slug)
            # Prediction markets: price 0-1 (cents), min size $1, step $1
            rules.append(
                TradingRule(
                    trading_pair=tp,
                    min_order_size=Decimal("0.01"),
                    min_base_amount_increment=Decimal("0.01"),
                    min_price_increment=Decimal("0.001"),
                    min_order_value=Decimal("0.01"),
                )
            )
        return rules

    # ── Data sources ────────────────────────────────────────────

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LimitlessAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LimitlessAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    # ── Prices ──────────────────────────────────────────────────

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        await self._ensure_inner_connector()
        result = []
        for tp in self._trading_pairs:
            slug = self._trading_pair_to_slug(tp)
            try:
                bid, ask = await self._inner_connector.get_best_bid_ask(slug)
                mid = ((bid or 0) + (ask or 0)) / 2.0 if bid and ask else 0
                result.append({"symbol": tp, "price": str(mid)})
            except Exception:
                result.append({"symbol": tp, "price": "0"})
        return result

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        await self._ensure_inner_connector()
        slug = self._trading_pair_to_slug(trading_pair)
        try:
            return await self._inner_connector.get_mid_price(slug)
        except Exception:
            return 0.0

    # ── Order placement ─────────────────────────────────────────

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=hex_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return hex_order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode("utf-8"))
        hex_order_id = f"0x{md5.hexdigest()}"
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=hex_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return hex_order_id

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
        """Place order via inner LimitlessConnector."""
        await self._ensure_inner_connector()
        slug = self._trading_pair_to_slug(trading_pair)

        # Determine token from trading pair format
        # ETH-USDC = YES side, ETHNO-USDC = NO side
        is_no_side = self._is_no_pair(trading_pair)
        token = "NO" if is_no_side else "YES"
        order_price = float(price)
        # NO price is already flipped by controller, send as-is

        # Both sides use the same slug (same market)
        if is_no_side:
            yes_pair = self._yes_pair(trading_pair)
            slug = self._trading_pair_to_slug(yes_pair)
        
        result = await self._inner_connector.buy(
            market_slug=slug,
            price=order_price,
            size=float(amount),
            order_type="GTC",
            token=token,
        )

        exchange_order_id = str(result.get("order_id", order_id))
        return exchange_order_id, self.current_timestamp

    # ── Order cancellation ──────────────────────────────────────

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        await self._ensure_inner_connector()
        cancel_id = tracked_order.exchange_order_id or order_id
        try:
            await self._inner_connector.cancel(cancel_id)
            return True
        except Exception as e:
            if "not found" in str(e).lower():
                await self._order_tracker.process_order_not_found(order_id)
                raise IOError(f"Order {order_id} not found on exchange")
            raise

    # ── Balance updates ─────────────────────────────────────────

    async def _update_balances(self):
        await self._ensure_inner_connector()
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            balance_info = await self._inner_connector.get_balance()

            # SDK returns dict with clob positions, rewards, etc.
            # Extract USDC balance from on-chain + locked collateral
            total_usdc = Decimal("0")
            total_locked = Decimal("0")

            if isinstance(balance_info, dict):
                # Sum collateral locked in CLOB positions
                for pos in balance_info.get("clob", []):
                    orders = pos.get("orders", {})
                    locked = orders.get("totalCollateralLocked", "0")
                    total_locked += Decimal(str(locked)) / Decimal("1000000")

                    # Track position values
                    positions = pos.get("positions", {})
                    for side in ("yes", "no"):
                        side_data = positions.get(side, {})
                        cost = Decimal(str(side_data.get("cost", "0"))) / Decimal("1000000")
                        total_usdc += cost

                # Read on-chain USDC balance directly via web3
                try:
                    import os

                    from web3 import Web3
                    rpc_url = os.environ.get("ETHEREUM_PROVIDER_BASE", "https://base.llamarpc.com")
                    w3 = Web3(Web3.HTTPProvider(rpc_url))
                    usdc_addr = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
                    wallet = self._inner_connector._account.address
                    usdc_abi = [{"inputs": [{"name": "account", "type": "address"}],
                                 "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}],
                                 "stateMutability": "view", "type": "function"}]
                    contract = w3.eth.contract(address=usdc_addr, abi=usdc_abi)
                    raw = contract.functions.balanceOf(wallet).call()
                    total_usdc += Decimal(str(raw)) / Decimal("1000000")
                except Exception as e:
                    self.logger().debug(f"On-chain USDC read failed: {e}")

            self._account_available_balances["USDC"] = total_usdc - total_locked
            self._account_balances["USDC"] = total_usdc
            remote_asset_names.add("USDC")

        except Exception as e:
            self.logger().warning(f"Failed to update balances: {e}")

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    # ── Order status updates ────────────────────────────────────

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Poll order status from the inner connector."""
        await self._ensure_inner_connector()
        slug = self._trading_pair_to_slug(tracked_order.trading_pair)

        try:
            # Check open orders on the market
            open_orders = await self._inner_connector.get_open_orders(slug)

            exchange_oid = tracked_order.exchange_order_id
            found = False
            for order in open_orders:
                oid = str(getattr(order, "id", "")) if not isinstance(order, dict) else str(order.get("id", ""))
                if oid == exchange_oid:
                    found = True
                    break

            if found:
                new_state = OrderState.OPEN
            else:
                # Order not in open orders — could be filled or canceled
                new_state = OrderState.FILLED

            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=new_state,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(tracked_order.exchange_order_id),
            )
        except Exception as e:
            self.logger().warning(f"Error fetching order status: {e}")
            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=time.time(),
                new_state=OrderState.OPEN,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(tracked_order.exchange_order_id),
            )

    # ── Fees ────────────────────────────────────────────────────

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
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _update_trading_fees(self):
        pass

    # ── User stream (no-op, polling-based) ──────────────────────

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 second.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Limitless.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """Process user stream events. Currently minimal since Limitless
        doesn't have user WS streams — status is updated via polling."""
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    channel = event_message.get("channel", "")
                    if channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                        for order_msg in event_message.get("data", []):
                            self._process_order_message(order_msg)
                    elif channel == CONSTANTS.USEREVENT_ENDPOINT_NAME:
                        results = event_message.get("data", {})
                        if "fills" in results:
                            for trade_msg in results["fills"]:
                                await self._process_trade_message(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener.", exc_info=True)
                await self._sleep(5.0)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        client_order_id = str(order_msg.get("client_order_id", order_msg.get("cloid", "")))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            return
        status = order_msg.get("status", "open")
        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=CONSTANTS.ORDER_STATE.get(status, OrderState.OPEN),
            client_order_id=client_order_id,
            exchange_order_id=str(order_msg.get("order_id", tracked_order.exchange_order_id)),
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _process_trade_message(self, trade: Dict[str, Any]):
        client_order_id = str(trade.get("client_order_id", trade.get("cloid", "")))
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if tracked_order is None:
            return
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=tracked_order.trade_type,
            percent_token="USDC",
            flat_fees=[TokenAmount(amount=Decimal(str(trade.get("fee", 0))), token="USDC")],
        )
        trade_update = TradeUpdate(
            trade_id=str(trade.get("trade_id", trade.get("tid", str(int(time.time() * 1e6))))),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade.get("order_id", tracked_order.exchange_order_id)),
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=time.time(),
            fill_price=Decimal(str(trade.get("price", trade.get("px", 0)))),
            fill_base_amount=Decimal(str(trade.get("size", trade.get("sz", 0)))),
            fill_quote_amount=Decimal(str(trade.get("price", trade.get("px", 0)))) * Decimal(str(trade.get("size", trade.get("sz", 0)))),
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    # ── Misc overrides ──────────────────────────────────────────

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal(round(float(f"{price:.5g}"), 6))

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        return []

    def stop(self, clock=None):
        import asyncio
        asyncio.ensure_future(self._stop_inner_connector())
        super().stop(clock)
