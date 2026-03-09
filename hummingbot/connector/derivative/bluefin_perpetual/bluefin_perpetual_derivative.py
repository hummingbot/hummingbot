"""
Bluefin Perpetual derivative connector.

Main connector class that implements PerpetualDerivativePyBase for Bluefin.
"""
# pyright: reportMissingTypeStubs=false, reportMissingImports=false

import asyncio
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.bluefin_perpetual import (
    bluefin_perpetual_constants as CONSTANTS,
    bluefin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_api_order_book_data_source import (
    BluefinPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_auth import BluefinPerpetualAuth
from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_user_stream_data_source import (
    BluefinPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.bluefin_perpetual.data_sources.bluefin_data_source import BluefinDataSource
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

# Bluefin SDK imports
try:
    from bluefin_pro_sdk import Order
    from openapi_client import (
        OrderType as BluefinOrderType,
        OrderSide as BluefinOrderSide,
        OrderTimeInForce,
        SelfTradePreventionType,
    )
except ImportError:
    Order = None
    BluefinOrderType = None
    BluefinOrderSide = None
    OrderTimeInForce = None
    SelfTradePreventionType = None


class BluefinPerpetualDerivative(PerpetualDerivativePyBase):
    """Bluefin Perpetual derivative connector."""

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
        self,
        bluefin_perpetual_wallet_mnemonic: str,
        bluefin_perpetual_network: str = "MAINNET",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        """
        Initialize Bluefin Perpetual connector.

        :param bluefin_perpetual_wallet_mnemonic: 24-word mnemonic
        :param bluefin_perpetual_network: Network ("MAINNET" or "STAGING")
        :param trading_pairs: List of trading pairs to trade
        :param trading_required: Whether trading is required
        :param balance_asset_limit: Balance limits
        :param rate_limits_share_pct: Rate limit sharing percentage
        """
        self._wallet_mnemonic = bluefin_perpetual_wallet_mnemonic
        self._network = bluefin_perpetual_network
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []
        self._domain = CONSTANTS.DOMAIN if bluefin_perpetual_network == "MAINNET" else CONSTANTS.STAGING_DOMAIN
        self._is_starting_network = False

        # SDK wrapper is initialized lazily and reused by all connector components
        self._data_source: BluefinDataSource = BluefinDataSource(
            wallet_mnemonic=self._wallet_mnemonic,
            network=self._network,
            debug=False,
        )

        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        """Get connector name."""
        return self._domain

    @property
    def authenticator(self) -> Optional[BluefinPerpetualAuth]:
        """Get authenticator."""
        if self._trading_required:
            return BluefinPerpetualAuth(
                wallet_mnemonic=self._wallet_mnemonic,
                network=self._network
            )
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        """Get rate limit rules."""
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        """Get domain."""
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        """Get max client order ID length."""
        return CONSTANTS.MAX_ORDER_ID_LEN or 64

    @property
    def client_order_id_prefix(self) -> str:
        """Get client order ID prefix."""
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        """Get trading rules request path."""
        return ""  # Not used - SDK handles this

    @property
    def trading_pairs_request_path(self) -> str:
        """Get trading pairs request path."""
        return ""  # Not used - SDK handles this

    @property
    def check_network_request_path(self) -> str:
        """Get check network request path."""
        return ""  # Not used - SDK handles this

    @property
    def funding_fee_poll_interval(self) -> int:
        """Get funding fee poll interval in seconds."""
        return CONSTANTS.FUNDING_RATE_UPDATE_INTERVAL_SECOND

    @property
    def trading_pairs(self) -> List[str]:
        """Get trading pairs."""
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Check if cancel request is synchronous."""
        return False  # Async via SDK

    @property
    def is_trading_required(self) -> bool:
        """Check if trading is required."""
        return self._trading_required

    def supported_position_modes(self) -> List[PositionMode]:
        """Get supported position modes."""
        # Bluefin only supports ONEWAY position mode
        return [PositionMode.ONEWAY]

    def supported_order_types(self) -> List[OrderType]:
        """
        :return: a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        """Get buy collateral token."""
        return CONSTANTS.CURRENCY  # Always USDC

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        """Get sell collateral token."""
        return CONSTANTS.CURRENCY  # Always USDC

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """Check if exception is related to time synchronizer."""
        return False  # SDK handles time synchronization

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Create web assistants factory."""
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """Create order book data source."""
        return BluefinPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            data_source=self._data_source,
            domain=self._domain
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """Create user stream data source."""
        return BluefinPerpetualUserStreamDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            data_source=self._data_source,
            domain=self._domain
        )

    async def start_network(self):
        """Start connector services and Bluefin SDK connections."""
        self._is_starting_network = True
        try:
            await self._ensure_data_source_started()
            await self._data_source.create_market_data_stream(self._trading_pairs)
            await self._data_source.create_account_data_stream()
            await super().start_network()
        finally:
            self._is_starting_network = False

    async def stop_network(self):
        """Stop connector services and Bluefin SDK connections."""
        await super().stop_network()
        if not self._is_starting_network and self._data_source.is_initialized:
            await self._data_source.shutdown()

    async def _ensure_data_source_started(self):
        if not self._data_source.is_initialized:
            await self._data_source.initialize()

    async def _make_trading_rules_request(self) -> Any:
        """Make trading rules request."""
        await self._ensure_data_source_started()
        return await self._data_source.get_exchange_info()

    async def _make_trading_pairs_request(self) -> Any:
        """Make trading pairs request."""
        await self._ensure_data_source_started()
        return await self._data_source.get_exchange_info()

    async def _update_trading_rules(self):
        """Update trading rules from exchange."""
        exchange_info = await self._make_trading_rules_request()
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, exchange_info_dict: Any) -> List[TradingRule]:
        """
        Format trading rules from exchange info.

        :param exchange_info_dict: Exchange info response
        :return: List of TradingRule objects
        """
        trading_rules: List[TradingRule] = []

        for market in exchange_info_dict.markets:
            try:
                # Convert Bluefin symbol to hummingbot symbol
                bluefin_symbol = market.symbol
                trading_pair = self._data_source.bluefin_to_hb_symbol(bluefin_symbol)

                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=self._data_source.from_e9(market.min_trade_quantity_e9),
                        min_price_increment=self._data_source.from_e9(market.tick_size_e9),
                        min_base_amount_increment=self._data_source.from_e9(market.step_size_e9),
                        buy_order_collateral_token=CONSTANTS.CURRENCY,
                        sell_order_collateral_token=CONSTANTS.CURRENCY,
                    )
                )
            except (AttributeError, TypeError, ValueError, KeyError):
                self.logger().exception("Error parsing trading rule for %s. Skipping.", getattr(market, "symbol", "unknown"))

        return trading_rules

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """Check if error is order not found."""
        return "not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """Check if cancellation error is order not found."""
        return "not found" in str(cancelation_exception).lower()

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs: Any,
    ) -> Tuple[str, float]:
        """
        Place an order.

        :param order_id: Client order ID
        :param trading_pair: Trading pair
        :param amount: Order amount
        :param trade_type: BUY or SELL
        :param order_type: LIMIT or MARKET
        :param price: Order price
        :param position_action: Position action
        :return: Tuple of (exchange_order_id, timestamp)
        """
        del kwargs

        if any(v is None for v in (Order, BluefinOrderType, BluefinOrderSide, OrderTimeInForce, SelfTradePreventionType)):
            raise RuntimeError("Bluefin SDK models are unavailable. Verify bluefin_pro_sdk installation.")

        # Convert hummingbot order type to Bluefin order type
        is_post_only = False
        if order_type == OrderType.LIMIT:
            bluefin_order_type = BluefinOrderType.LIMIT
        elif order_type == OrderType.LIMIT_MAKER:
            bluefin_order_type = BluefinOrderType.LIMIT
            is_post_only = True
        elif order_type == OrderType.MARKET:
            bluefin_order_type = BluefinOrderType.MARKET
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        # Convert trade type to Bluefin order side
        bluefin_side = BluefinOrderSide.LONG if trade_type == TradeType.BUY else BluefinOrderSide.SHORT

        await self._ensure_data_source_started()

        # Quantize price and amount
        quantized_price = self.quantize_order_price(trading_pair, price)
        quantized_amount = self.quantize_order_amount(trading_pair, amount)

        # Create order
        order = Order(
            client_order_id=order_id,
            type=bluefin_order_type,
            symbol=trading_pair,  # Will be converted to Bluefin symbol in data_source
            price_e9=self._data_source.to_e9(quantized_price),
            quantity_e9=self._data_source.to_e9(quantized_amount),
            side=bluefin_side,
            leverage_e9=self._data_source.to_e9(Decimal("1")),  # Default 1x leverage
            is_isolated=False,  # Cross margin by default
            expires_at_millis=int(time.time() * 1000) + 120000,  # 2 minute expiry
            reduce_only=position_action == PositionAction.CLOSE,
            post_only=is_post_only,
            time_in_force=OrderTimeInForce.GTT,
            self_trade_prevention_type=SelfTradePreventionType.TAKER,
        )

        # Place order via SDK with retry logic
        max_retries = 3
        retry_delay = 1.0
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = await self._data_source.place_order(order)
                return response.order_hash, time.time()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    self.logger().warning(
                        f"Order placement failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger().error(
                        f"Order placement failed after {max_retries} attempts: {str(e)}",
                        exc_info=True
                    )

        # If all retries failed, raise the last exception
        raise last_exception or RuntimeError("Order placement failed with unknown error")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancel an order with retry logic.

        :param order_id: Client order ID
        :param tracked_order: Tracked order
        """
        await self._ensure_data_source_started()
        exchange_order_id = tracked_order.exchange_order_id

        if exchange_order_id is None:
            self.logger().warning(f"Order {order_id} has no exchange order ID. Cannot cancel.")
            return

        max_retries = 3
        retry_delay = 0.5
        last_exception = None

        for attempt in range(max_retries):
            try:
                await self._data_source.cancel_order(
                    symbol=tracked_order.trading_pair,
                    order_hash=exchange_order_id
                )
                return
            except Exception as e:
                last_exception = e
                # Check if error is "order not found" - this is acceptable
                if self._is_order_not_found_during_cancelation_error(e):
                    self.logger().info(f"Order {order_id} already cancelled or filled")
                    return

                if attempt < max_retries - 1:
                    self.logger().warning(
                        f"Order cancellation failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.logger().error(
                        f"Order cancellation failed after {max_retries} attempts: {str(e)}",
                        exc_info=True
                    )

        # If all retries failed, raise the last exception
        raise last_exception or RuntimeError("Order cancellation failed with unknown error")

    async def _update_balances(self):
        """Update account balances with retry logic."""
        await self._ensure_data_source_started()

        max_retries = 2
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                account = await self._data_source.get_account()

                self._account_balances[CONSTANTS.CURRENCY] = Decimal("0")
                self._account_available_balances[CONSTANTS.CURRENCY] = Decimal("0")

                for asset in getattr(account, "assets", []):
                    symbol = getattr(asset, "symbol", None)
                    if symbol is None:
                        continue
                    total_balance = self._data_source.from_e9(getattr(asset, "quantity_e9", "0"))
                    available_balance = self._data_source.from_e9(getattr(asset, "max_withdraw_quantity_e9", "0"))
                    self._account_balances[symbol] = total_balance
                    self._account_available_balances[symbol] = available_balance

                return  # Success

            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger().warning(
                        f"Balance update failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger().error(
                        f"Balance update failed after {max_retries} attempts: {str(e)}",
                        exc_info=True
                    )
                    # Don't raise - allow connector to continue with stale data
                    # This prevents complete failure if balance API is temporarily unavailable

    async def _update_positions(self):
        """Update positions with retry logic."""
        await self._ensure_data_source_started()

        max_retries = 2
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                account = await self._data_source.get_account()

                # Clear existing positions
                self._account_positions.clear()

                # Update positions from account data
                if hasattr(account, 'positions') and account.positions:
                    for pos_data in account.positions:
                        trading_pair = self._data_source.bluefin_to_hb_symbol(pos_data.symbol)
                        amount = self._data_source.from_e9(getattr(pos_data, "size_e9", "0"))

                        if amount == Decimal("0"):
                            continue

                        side_name = getattr(getattr(pos_data, "side", None), "value", str(getattr(pos_data, "side", "")))
                        position_side = PositionSide.LONG if side_name.upper() == "LONG" else PositionSide.SHORT

                        # Create position
                        position = Position(
                            trading_pair=trading_pair,
                            position_side=position_side,
                            unrealized_pnl=self._data_source.from_e9(getattr(pos_data, "unrealized_pnl_e9", "0")),
                            entry_price=self._data_source.from_e9(getattr(pos_data, "avg_entry_price_e9", "0")),
                            amount=abs(amount),
                            leverage=self._data_source.from_e9(getattr(pos_data, "client_set_leverage_e9", self._data_source.to_e9(Decimal("1")))),
                        )

                        position_key = self._perpetual_trading.position_key(trading_pair, position_side)
                        self._perpetual_trading.set_position(position_key, position)

                return  # Success

            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger().warning(
                        f"Position update failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger().error(
                        f"Position update failed after {max_retries} attempts: {str(e)}",
                        exc_info=True
                    )
                    # Don't raise - allow connector to continue with stale data
                    # This prevents complete failure if position API is temporarily unavailable

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """
        Set leverage for a trading pair with retry logic.

        :param trading_pair: Trading pair
        :param leverage: Leverage value
        :return: Tuple of (success, message)
        """
        max_retries = 2
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                await self._ensure_data_source_started()
                await self._data_source.set_leverage(trading_pair, Decimal(str(leverage)))
                return True, ""
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                if attempt < max_retries - 1:
                    self.logger().warning(
                        f"Set leverage failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    error_msg = f"Failed to set leverage after {max_retries} attempts: {str(e)}"
                    self.logger().error(error_msg, exc_info=True)
                    return False, error_msg

        return False, "Set leverage failed with unknown error"

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """
        Set position mode for a trading pair.

        Bluefin only supports ONEWAY mode, so this is a no-op.

        :param mode: Position mode
        :param trading_pair: Trading pair
        :return: Tuple of (success, message)
        """
        if mode != PositionMode.ONEWAY:
            return False, "Bluefin only supports ONEWAY position mode"
        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """
        Fetch last funding fee payment.

        :param trading_pair: Trading pair
        :return: Tuple of (timestamp, funding_rate, payment)
        """
        del trading_pair

        try:
            # Get funding rate history
            history = await self._data_source.get_account_funding_rate_history(limit=1)

            if history and len(history.data) > 0:
                last_payment = history.data[0]
                timestamp = last_payment.executed_at_millis / 1000.0
                payment = self._data_source.from_e9(last_payment.payment_amount_e9)
                rate = self._data_source.from_e9(last_payment.rate_e9)
                return timestamp, rate, payment
            else:
                # No payment history
                return 0.0, Decimal("0"), Decimal("0")

        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            self.logger().error("Error fetching funding fee payment: %s", e)
            return 0.0, Decimal("0"), Decimal("0")

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        """
        Get fee for an order.

        :param base_currency: Base currency
        :param quote_currency: Quote currency
        :param order_type: Order type
        :param order_side: Order side
        :param amount: Order amount
        :param price: Order price
        :param is_maker: Whether order is maker
        :return: TradeFeeBase
        """
        is_maker = is_maker or False
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

    async def _update_trading_fees(self):
        # Trading fees are static for now and configured in bluefin_perpetual_utils.DEFAULT_FEES.
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        await self._ensure_data_source_started()
        trade_updates: List[TradeUpdate] = []
        exchange_order_id = order.exchange_order_id or await order.get_exchange_order_id()
        trades = await self._data_source.get_account_trades(symbol=order.trading_pair, limit=200)
        for trade in trades:
            if getattr(trade, "order_hash", None) != exchange_order_id:
                continue

            fee_token = getattr(trade, "trading_fee_asset", None) or CONSTANTS.CURRENCY
            fee_amount = self._data_source.from_e9(getattr(trade, "trading_fee_e9", "0"))
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=order.position,
                percent_token=fee_token,
                flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)],
            )

            fill_price = self._data_source.from_e9(trade.price_e9)
            fill_base_amount = self._data_source.from_e9(trade.quantity_e9)
            quote_quantity_e9 = getattr(trade, "quote_quantity_e9", None)
            fill_quote_amount = (
                self._data_source.from_e9(quote_quantity_e9)
                if quote_quantity_e9 is not None
                else fill_price * fill_base_amount
            )

            trade_updates.append(
                TradeUpdate(
                    trade_id=trade.id,
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fill_timestamp=trade.executed_at_millis * 1e-3,
                    fill_price=fill_price,
                    fill_base_amount=fill_base_amount,
                    fill_quote_amount=fill_quote_amount,
                    fee=fee,
                    is_taker=not bool(getattr(trade, "is_maker", False)),
                )
            )

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        await self._ensure_data_source_started()
        exchange_order_id = tracked_order.exchange_order_id
        if exchange_order_id is None:
            exchange_order_id = await tracked_order.get_exchange_order_id()

        open_orders = await self._data_source.get_open_orders(tracked_order.trading_pair)
        matching_order = next(
            (
                o for o in open_orders
                if getattr(o, "order_hash", None) == exchange_order_id
                or getattr(o, "client_order_id", None) == tracked_order.client_order_id
            ),
            None,
        )

        if matching_order is None:
            trades = await self._data_source.get_account_trades(symbol=tracked_order.trading_pair, limit=100)
            was_filled = any(getattr(trade, "order_hash", None) == exchange_order_id for trade in trades)
            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FILLED if was_filled else OrderState.CANCELED,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=exchange_order_id,
            )

        status_value = getattr(getattr(matching_order, "status", None), "value", str(getattr(matching_order, "status", "")))
        new_state = CONSTANTS.ORDER_STATE.get(status_value, OrderState.OPEN)
        update_timestamp = getattr(matching_order, "updated_at_millis", int(self.current_timestamp * 1000)) * 1e-3
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
            client_order_id=getattr(matching_order, "client_order_id", tracked_order.client_order_id),
            exchange_order_id=getattr(matching_order, "order_hash", exchange_order_id),
        )

    async def _iter_user_event_queue(self) -> AsyncIterable[Any]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                self.logger().network(
                    "Unknown error while reading Bluefin user stream. Retrying in 1 second.",
                    exc_info=True,
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                self._process_user_stream_event(event_message)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for market in getattr(exchange_info, "markets", []):
            symbol = getattr(market, "symbol", None)
            if symbol is None:
                continue
            base = symbol.split("-")[0]
            hb_trading_pair = combine_to_hb_trading_pair(base, "USD")
            mapping[symbol] = hb_trading_pair

        self._set_trading_pair_symbol_map(mapping)

    def _process_user_stream_event(self, event: Any):
        """
        Process user stream event.

        :param event: Event from user stream
        """
        try:
            event_name = type(event).__name__
            if event_name == "AccountOrderUpdate":
                self._process_order_update(event)
            elif event_name == "AccountTradeUpdate":
                self._process_trade_update(event)
            elif event_name == "AccountPositionUpdate":
                self._process_position_update(event)
            elif event_name == "AccountUpdate":
                self._process_account_update(event)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self.logger().exception("Error processing user stream event")

    def _process_order_update(self, event: Any):
        """Process order update event."""
        # AccountOrderUpdate is a oneOf type containing either ActiveOrderUpdate or OrderCancellationUpdate
        if hasattr(event, 'actual_instance'):
            actual_event = event.actual_instance
            actual_event_name = type(actual_event).__name__

            if actual_event_name == "ActiveOrderUpdate":
                # Order fill or partial fill
                client_order_id = actual_event.client_order_id
                exchange_order_id = actual_event.order_hash
                trading_pair = self._data_source.bluefin_to_hb_symbol(actual_event.symbol)

                # Map order status
                new_state = CONSTANTS.ORDER_STATE.get(actual_event.status.value, None)

                if new_state:
                    order_update = OrderUpdate(
                        trading_pair=trading_pair,
                        update_timestamp=actual_event.updated_at_millis / 1000.0,
                        new_state=new_state,
                        client_order_id=client_order_id,
                        exchange_order_id=exchange_order_id,
                    )
                    self._order_tracker.process_order_update(order_update)

            elif actual_event_name == "OrderCancellationUpdate":
                # Order cancelled
                client_order_id = actual_event.client_order_id
                trading_pair = self._data_source.bluefin_to_hb_symbol(actual_event.symbol)

                order_update = OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=actual_event.created_at_millis / 1000.0,
                    new_state=CONSTANTS.ORDER_STATE["CANCELLED"],
                    client_order_id=client_order_id,
                    exchange_order_id=actual_event.order_hash,
                )
                self._order_tracker.process_order_update(order_update)

    def _process_trade_update(self, event: Any):
        """Process trade update event."""
        trade = event.trade
        exchange_order_id = getattr(trade, "order_hash", "")
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        if tracked_order is None:
            return

        fee_token = getattr(trade, "trading_fee_asset", None) or CONSTANTS.CURRENCY
        fee_amount = self._data_source.from_e9(getattr(trade, "trading_fee_e9", "0"))
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=tracked_order.position,
            percent_token=fee_token,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_token)],
        )

        fill_price = self._data_source.from_e9(trade.price_e9)
        fill_amount = self._data_source.from_e9(trade.quantity_e9)
        fill_quote_amount = self._data_source.from_e9(trade.quote_quantity_e9)

        trade_update = TradeUpdate(
            trade_id=trade.id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=trade.executed_at_millis / 1000.0,
            fill_price=fill_price,
            fill_base_amount=fill_amount,
            fill_quote_amount=fill_quote_amount,
            fee=fee,
            is_taker=not bool(getattr(trade, "is_maker", False)),
        )
        self._order_tracker.process_trade_update(trade_update)

    def _process_position_update(self, event: Any):
        """Process position update event."""
        trading_pair = self._data_source.bluefin_to_hb_symbol(event.symbol)
        position_side = PositionSide.LONG if str(getattr(event.side, "value", event.side)).upper() == "LONG" else PositionSide.SHORT
        amount = self._data_source.from_e9(event.size_e9)
        if amount == Decimal("0"):
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
            self._perpetual_trading.remove_position(pos_key)
            return

        position = Position(
            trading_pair=trading_pair,
            position_side=position_side,
            unrealized_pnl=self._data_source.from_e9(event.unrealized_pnl_e9),
            entry_price=self._data_source.from_e9(event.avg_entry_price_e9),
            amount=abs(amount),
            leverage=self._data_source.from_e9(event.client_set_leverage_e9),
        )
        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
        self._perpetual_trading.set_position(pos_key, position)

    def _process_account_update(self, event: Any):
        """Process account balance update event."""
        for asset in getattr(event, "assets", []):
            symbol = getattr(asset, "symbol", None)
            if symbol is None:
                continue
            self._account_balances[symbol] = self._data_source.from_e9(getattr(asset, "quantity_e9", "0"))
            self._account_available_balances[symbol] = self._data_source.from_e9(
                getattr(asset, "max_withdraw_quantity_e9", "0")
            )
