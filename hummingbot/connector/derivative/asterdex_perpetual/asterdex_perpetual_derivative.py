import asyncio
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.asterdex_perpetual import (
    asterdex_perpetual_constants as CONSTANTS,
    asterdex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.asterdex_perpetual.asterdex_perpetual_auth import AsterdexPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

bpm_logger = None


class AsterdexPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            asterdex_perpetual_api_secret: str = None,
            use_vault: bool = False,
            asterdex_perpetual_api_key: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DOMAIN,
    ):
        self.asterdex_perpetual_api_key = asterdex_perpetual_api_key
        self.asterdex_perpetual_secret_key = asterdex_perpetual_api_secret
        self._use_vault = use_vault
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self.coin_to_asset: Dict[str, int] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[AsterdexPerpetualAuth]:
        if self._trading_required:
            return AsterdexPerpetualAuth(self.asterdex_perpetual_api_key, self.asterdex_perpetual_secret_key,
                                                self._use_vault)
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
    def funding_fee_poll_interval(self) -> int:
        return CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND

    # Essential abstract method implementations
    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Get all trade updates for a specific order"""
        return []

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """Create order book data source"""
        from hummingbot.connector.derivative.asterdex_perpetual.asterdex_perpetual_api_order_book_data_source import AsterdexPerpetualAPIOrderBookDataSource
        return AsterdexPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=None,  # Will be set later
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """Create user stream data source"""
        from hummingbot.connector.derivative.asterdex_perpetual.asterdex_perpetual_api_user_stream_data_source import AsterdexPerpetualAPIUserStreamDataSource
        return AsterdexPerpetualAPIUserStreamDataSource(
            auth=self.authenticator,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=None,  # Will be set later
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Create web assistants factory"""
        return WebAssistantsFactory(
            throttler=self._throttler,
            auth=self.authenticator,
        )

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[Decimal, Decimal]:
        """Fetch last fee payment for a trading pair"""
        return Decimal("0"), Decimal("0")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """Format trading rules from exchange info"""
        return []

    async def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        """Get trading fee"""
        return build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """Initialize trading pair symbols from exchange info"""
        mapping = bidict()
        valid_pairs = 0
        
        if "symbols" in exchange_info:
            for symbol_data in exchange_info["symbols"]:
                symbol = symbol_data.get("symbol", "")
                if not symbol or symbol_data.get("status") != "TRADING":
                    continue
                
                # Parse base and quote assets
                base = symbol_data.get("baseAsset", "")
                quote = symbol_data.get("quoteAsset", "")
                
                if base and quote:
                    hb_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[symbol] = hb_pair
                    valid_pairs += 1
                    self.logger().info(f"Added trading pair: {symbol} -> {hb_pair}")
        
        self._set_trading_pair_symbol_map(mapping)
        self.logger().info(f"Initialized {valid_pairs} trading pairs from exchange info")

    async def _is_order_not_found_during_cancelation_error(self, status: str) -> bool:
        """Check if order not found during cancellation"""
        return False

    async def _is_order_not_found_during_status_update_error(self, status: str) -> bool:
        """Check if order not found during status update"""
        return False

    async def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """Check if request exception is related to time synchronizer"""
        return False

    async def _place_cancel(self, order: InFlightOrder) -> str:
        """Place cancel order"""
        return ""

    async def _place_order(self, order: InFlightOrder, **kwargs) -> str:
        """Place order"""
        return ""

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Request order status"""
        return OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=tracked_order.current_state,
        )

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> bool:
        """Set trading pair leverage"""
        return True

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> bool:
        """Set trading pair position mode"""
        return True

    async def _update_balances(self):
        """Update balances"""
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            response = await self._api_get(path_url=CONSTANTS.ACCOUNT_INFO_URL, is_auth_required=True)
            
            # Debug: Log the response
            self.logger().info(f"Balance API response type: {type(response)}, content: {response}")

            # AsterDex futures API returns assets array with walletBalance and availableBalance
            if isinstance(response, dict) and "assets" in response:
                for asset_entry in response["assets"]:
                    asset_name = asset_entry["asset"]
                    wallet_balance = Decimal(asset_entry["walletBalance"])
                    available_balance = Decimal(asset_entry["availableBalance"])
                    
                    # Only add assets with non-zero balances
                    if wallet_balance > 0:
                        self._account_available_balances[asset_name] = available_balance
                        self._account_balances[asset_name] = wallet_balance
                        remote_asset_names.add(asset_name)
                        self.logger().info(f"Updated balance for {asset_name}: {wallet_balance} (available: {available_balance})")
            else:
                self.logger().warning(f"Unexpected balance response format: {response}")
                return

            # Remove assets that are no longer present
            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

        except Exception as e:
            self.logger().error(f"Error fetching balances: {e}")
            raise

    async def _update_positions(self):
        """Update positions"""
        pass

    async def _update_trading_fees(self):
        """Update trading fees"""
        pass

    async def _user_stream_event_listener(self):
        """User stream event listener"""
        pass

    # Additional required methods
    async def _get_buy_collateral_token(self, trading_pair: str) -> str:
        """Get buy collateral token"""
        return "USDT"

    async def _get_sell_collateral_token(self, trading_pair: str) -> str:
        """Get sell collateral token"""
        return "USDT"

    async def _get_funding_payment(self, trading_pair: str) -> Decimal:
        """Get funding payment"""
        return Decimal("0")

    async def _get_funding_rate(self, trading_pair: str) -> Decimal:
        """Get funding rate"""
        return Decimal("0")

    async def _get_leverage(self, trading_pair: str) -> int:
        """Get leverage for trading pair"""
        return 1

    async def _get_position_mode(self) -> PositionMode:
        """Get position mode"""
        return PositionMode.ONEWAY

    async def _get_trading_pair_position_mode(self, trading_pair: str) -> PositionMode:
        """Get trading pair position mode"""
        return PositionMode.ONEWAY

    async def _set_position_mode(self, mode: PositionMode) -> bool:
        """Set position mode"""
        return True

    # Required abstract methods from ExchangePyBase
    @property
    def trading_pairs(self) -> List[str]:
        """Get trading pairs"""
        return self._trading_pairs or []

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Check if cancel request is synchronous"""
        return False

    @property
    def is_trading_required(self) -> bool:
        """Check if trading is required"""
        return self._trading_required

    @property
    def supported_order_types(self) -> List[OrderType]:
        """Get supported order types"""
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def supported_position_modes(self) -> List[PositionMode]:
        """Get supported position modes"""
        return [PositionMode.ONEWAY]

    # Required abstract methods from PerpetualDerivativePyBase
    def get_buy_collateral_token(self, trading_pair: str) -> str:
        """Get buy collateral token"""
        return "USDT"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        """Get sell collateral token"""
        return "USDT"