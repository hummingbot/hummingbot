import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_swap import GatewaySwap
from hummingbot.core.data_type.common import LPType, OrderType, TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    MarketEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateFailureEvent,
)
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future


class TokenInfo(BaseModel):
    address: str
    symbol: str
    decimals: int


class AMMPoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    price: float
    fee_pct: float = Field(alias="feePct")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")


class CLMMPoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    bin_step: int = Field(alias="binStep")
    fee_pct: float = Field(alias="feePct")
    price: float
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    active_bin_id: int = Field(alias="activeBinId")


class AMMPositionInfo(BaseModel):
    pool_address: str = Field(alias="poolAddress")
    wallet_address: str = Field(alias="walletAddress")
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    lp_token_amount: float = Field(alias="lpTokenAmount")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    price: float
    base_token: Optional[str] = None
    quote_token: Optional[str] = None


class CLMMPositionInfo(BaseModel):
    address: str
    pool_address: str = Field(alias="poolAddress")
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    base_fee_amount: float = Field(alias="baseFeeAmount")
    quote_fee_amount: float = Field(alias="quoteFeeAmount")
    lower_bin_id: int = Field(alias="lowerBinId")
    upper_bin_id: int = Field(alias="upperBinId")
    lower_price: float = Field(alias="lowerPrice")
    upper_price: float = Field(alias="upperPrice")
    price: float
    base_token: Optional[str] = None
    quote_token: Optional[str] = None


class GatewayLp(GatewaySwap):
    """
    Handles AMM and CLMM liquidity provision functionality including fetching pool info and adding/removing liquidity.
    Maintains order tracking and wallet interactions in the base class.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store LP operation metadata for triggering proper events
        self._lp_orders_metadata: Dict[str, Dict] = {}

    def _trigger_lp_events_if_needed(self, order_id: str, transaction_hash: str):
        """
        Helper to trigger LP-specific events when an order completes.
        This is called by both fast monitoring and slow polling to avoid duplication.
        """
        # Check if already triggered (metadata would be deleted)
        if order_id not in self._lp_orders_metadata:
            return

        tracked_order = self._order_tracker.fetch_order(order_id)
        if not tracked_order or tracked_order.trade_type != TradeType.RANGE:
            return

        metadata = self._lp_orders_metadata[order_id]

        # Trigger appropriate event based on transaction result
        # For LP operations (RANGE orders), state stays OPEN even when done, so check is_done
        is_successful = tracked_order.is_done and not tracked_order.is_failure and not tracked_order.is_cancelled

        if is_successful:
            # Transaction successful - trigger LP-specific events
            if metadata["operation"] == "add":
                self._trigger_add_liquidity_event(
                    order_id=order_id,
                    exchange_order_id=transaction_hash,
                    trading_pair=tracked_order.trading_pair,
                    lower_price=metadata["lower_price"],
                    upper_price=metadata["upper_price"],
                    amount=metadata["amount"],
                    fee_tier=metadata["fee_tier"],
                    creation_timestamp=tracked_order.creation_timestamp,
                    trade_fee=TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type,
                        flat_fees=[TokenAmount(amount=metadata.get("tx_fee", Decimal("0")), token=self._native_currency)]
                    ),
                    # P&L tracking fields from gateway response
                    position_address=metadata.get("position_address", ""),
                    base_amount=metadata.get("base_amount", Decimal("0")),
                    quote_amount=metadata.get("quote_amount", Decimal("0")),
                    position_rent=metadata.get("position_rent", Decimal("0")),
                )
            elif metadata["operation"] == "remove":
                self._trigger_remove_liquidity_event(
                    order_id=order_id,
                    exchange_order_id=transaction_hash,
                    trading_pair=tracked_order.trading_pair,
                    token_id=metadata["position_address"],
                    creation_timestamp=tracked_order.creation_timestamp,
                    trade_fee=TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type,
                        flat_fees=[TokenAmount(amount=metadata.get("tx_fee", Decimal("0")), token=self._native_currency)]
                    ),
                    # P&L tracking fields from gateway response
                    position_address=metadata.get("position_address", ""),
                    base_amount=metadata.get("base_amount", Decimal("0")),
                    quote_amount=metadata.get("quote_amount", Decimal("0")),
                    base_fee=metadata.get("base_fee", Decimal("0")),
                    quote_fee=metadata.get("quote_fee", Decimal("0")),
                    position_rent_refunded=metadata.get("position_rent_refunded", Decimal("0")),
                )
        elif tracked_order.is_failure:
            # Transaction failed - trigger LP-specific failure event for strategy handling
            operation_type = "add" if metadata["operation"] == "add" else "remove"
            self.logger().error(
                f"LP {operation_type} liquidity transaction failed for order {order_id} (tx: {transaction_hash})"
            )
            # Trigger RangePositionUpdateFailureEvent so strategies can retry
            self.trigger_event(
                MarketEvent.RangePositionUpdateFailure,
                RangePositionUpdateFailureEvent(
                    timestamp=self.current_timestamp,
                    order_id=order_id,
                    order_action=LPType.ADD if metadata["operation"] == "add" else LPType.REMOVE,
                )
            )
        elif tracked_order.is_cancelled:
            # Transaction cancelled
            operation_type = "add" if metadata["operation"] == "add" else "remove"
            self.logger().warning(
                f"LP {operation_type} liquidity transaction cancelled for order {order_id} (tx: {transaction_hash})"
            )

        # Clean up metadata (prevents double-triggering) and stop tracking
        del self._lp_orders_metadata[order_id]
        self.stop_tracking_order(order_id)

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """
        Override to trigger RangePosition events after LP transactions complete (batch polling).
        """
        # Call parent implementation (handles timeout checking)
        await super().update_order_status(tracked_orders)

        # Trigger LP events for any completed LP operations
        for tracked_order in tracked_orders:
            if tracked_order.trade_type == TradeType.RANGE:
                # Get transaction hash
                try:
                    tx_hash = await tracked_order.get_exchange_order_id()
                    self._trigger_lp_events_if_needed(tracked_order.client_order_id, tx_hash)
                except Exception as e:
                    self.logger().warning(f"Error triggering LP event for {tracked_order.client_order_id}: {e}", exc_info=True)

    # Error code from gateway for transaction confirmation timeout
    TRANSACTION_TIMEOUT_CODE = "TRANSACTION_TIMEOUT"

    def _handle_operation_failure(self, order_id: str, trading_pair: str, operation_name: str, error: Exception):
        """
        Override to trigger RangePositionUpdateFailureEvent for LP operations.
        Only triggers retry for transaction confirmation timeouts (code: TRANSACTION_TIMEOUT).
        """
        # Call parent implementation
        super()._handle_operation_failure(order_id, trading_pair, operation_name, error)

        # Check if this is a transaction timeout error (retryable)
        # Gateway returns error with code "TRANSACTION_TIMEOUT" for tx confirmation timeouts
        error_str = str(error)
        is_timeout_error = self.TRANSACTION_TIMEOUT_CODE in error_str

        if is_timeout_error and order_id in self._lp_orders_metadata:
            metadata = self._lp_orders_metadata[order_id]
            operation = metadata.get("operation", "")
            self.logger().warning(
                f"Transaction timeout detected for LP {operation} order {order_id} on {trading_pair}. "
                f"Chain may be congested. Triggering retry event..."
            )
            self.trigger_event(
                MarketEvent.RangePositionUpdateFailure,
                RangePositionUpdateFailureEvent(
                    timestamp=self.current_timestamp,
                    order_id=order_id,
                    order_action=LPType.ADD if operation == "add" else LPType.REMOVE,
                )
            )
            # Clean up metadata
            del self._lp_orders_metadata[order_id]
        elif order_id in self._lp_orders_metadata:
            # Non-retryable error, just clean up metadata
            self.logger().warning(f"Non-retryable error for {order_id}: {error_str[:100]}")
            del self._lp_orders_metadata[order_id]

    def _trigger_add_liquidity_event(
        self,
        order_id: str,
        exchange_order_id: str,
        trading_pair: str,
        lower_price: Decimal,
        upper_price: Decimal,
        amount: Decimal,
        fee_tier: str,
        creation_timestamp: float,
        trade_fee: TradeFeeBase,
        position_address: str = "",
        base_amount: Decimal = Decimal("0"),
        quote_amount: Decimal = Decimal("0"),
        mid_price: Decimal = Decimal("0"),
        position_rent: Decimal = Decimal("0"),
    ):
        """Trigger RangePositionLiquidityAddedEvent"""
        event = RangePositionLiquidityAddedEvent(
            timestamp=self.current_timestamp,
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            lower_price=lower_price,
            upper_price=upper_price,
            amount=amount,
            fee_tier=fee_tier,
            creation_timestamp=creation_timestamp,
            trade_fee=trade_fee,
            token_id=0,
            # P&L tracking fields
            position_address=position_address,
            mid_price=mid_price,
            base_amount=base_amount,
            quote_amount=quote_amount,
            position_rent=position_rent,
        )
        self.trigger_event(MarketEvent.RangePositionLiquidityAdded, event)
        self.logger().info(f"Triggered RangePositionLiquidityAddedEvent for order {order_id}")

    def _trigger_remove_liquidity_event(
        self,
        order_id: str,
        exchange_order_id: str,
        trading_pair: str,
        token_id: str,
        creation_timestamp: float,
        trade_fee: TradeFeeBase,
        position_address: str = "",
        lower_price: Decimal = Decimal("0"),
        upper_price: Decimal = Decimal("0"),
        mid_price: Decimal = Decimal("0"),
        base_amount: Decimal = Decimal("0"),
        quote_amount: Decimal = Decimal("0"),
        base_fee: Decimal = Decimal("0"),
        quote_fee: Decimal = Decimal("0"),
        position_rent_refunded: Decimal = Decimal("0"),
    ):
        """Trigger RangePositionLiquidityRemovedEvent"""
        event = RangePositionLiquidityRemovedEvent(
            timestamp=self.current_timestamp,
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            token_id=token_id,
            trade_fee=trade_fee,
            creation_timestamp=creation_timestamp,
            # P&L tracking fields
            position_address=position_address,
            lower_price=lower_price,
            upper_price=upper_price,
            mid_price=mid_price,
            base_amount=base_amount,
            quote_amount=quote_amount,
            base_fee=base_fee,
            quote_fee=quote_fee,
            position_rent_refunded=position_rent_refunded,
        )
        self.trigger_event(MarketEvent.RangePositionLiquidityRemoved, event)
        self.logger().info(f"Triggered RangePositionLiquidityRemovedEvent for order {order_id}")

    @async_ttl_cache(ttl=300, maxsize=10)
    async def get_pool_address(self, trading_pair: str) -> Optional[str]:
        """Get pool address for a trading pair (cached for 5 minutes)"""
        try:
            # Parse connector to get type (amm or clmm)
            connector_type = get_connector_type(self.connector_name)
            pool_type = "clmm" if connector_type == ConnectorType.CLMM else "amm"

            # Get pool info from gateway using the get_pool method
            connector_name = self.connector_name.split("/")[0]
            pool_info = await self._get_gateway_instance().get_pool(
                trading_pair=trading_pair,
                connector=connector_name,
                network=self.network,
                type=pool_type
            )

            pool_address = pool_info.get("address")
            if not pool_address:
                self.logger().warning(f"No pool address found for {trading_pair}")

            return pool_address

        except Exception as e:
            self.logger().error(f"Error getting pool address for {trading_pair}: {e}")
            return None

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_pool_info_by_address(
        self,
        pool_address: str,
    ) -> Optional[Union[AMMPoolInfo, CLMMPoolInfo]]:
        """
        Retrieves pool information by pool address directly.
        Uses the appropriate model (AMMPoolInfo or CLMMPoolInfo) based on connector type.

        :param pool_address: The pool contract address
        :return: Pool info object or None if not found
        """
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().pool_info(
                connector=self.connector_name,
                network=self.network,
                pool_address=pool_address,
            )

            if not resp:
                return None

            # Determine which model to use based on connector type
            connector_type = get_connector_type(self.connector_name)
            if connector_type == ConnectorType.CLMM:
                return CLMMPoolInfo(**resp)
            elif connector_type == ConnectorType.AMM:
                return AMMPoolInfo(**resp)
            else:
                self.logger().warning(f"Unknown connector type: {connector_type} for {self.connector_name}")
                return None

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error fetching pool info for address {pool_address} on {self.connector_name}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None

    async def resolve_trading_pair_from_pool(
        self,
        pool_address: str,
    ) -> Optional[Dict[str, str]]:
        """
        Resolve trading pair information from pool address.
        Fetches pool info and returns token symbols and addresses.

        :param pool_address: The pool contract address
        :return: Dictionary with trading_pair, base_token, quote_token, base_token_address, quote_token_address
                 or None if pool not found
        """
        try:
            # Fetch pool info
            pool_info_resp = await self._get_gateway_instance().pool_info(
                connector=self.connector_name,
                network=self.network,
                pool_address=pool_address
            )

            if not pool_info_resp:
                raise ValueError(f"Could not fetch pool info for pool address {pool_address}")

            # Get token addresses from pool info
            base_token_address = pool_info_resp.get("baseTokenAddress")
            quote_token_address = pool_info_resp.get("quoteTokenAddress")

            if not base_token_address or not quote_token_address:
                raise ValueError(f"Pool info missing token addresses: {pool_info_resp}")

            # Try to get token symbols from connector's token cache
            base_token_info = self.get_token_by_address(base_token_address)
            quote_token_info = self.get_token_by_address(quote_token_address)

            base_symbol = base_token_info.get("symbol") if base_token_info else base_token_address
            quote_symbol = quote_token_info.get("symbol") if quote_token_info else quote_token_address

            trading_pair = f"{base_symbol}-{quote_symbol}"

            return {
                "trading_pair": trading_pair,
                "base_token": base_symbol,
                "quote_token": quote_symbol,
                "base_token_address": base_token_address,
                "quote_token_address": quote_token_address,
            }

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error resolving trading pair from pool {pool_address}: {str(e)}", exc_info=True)
            return None

    async def get_pool_info(
        self,
        trading_pair: str,
    ) -> Optional[Union[AMMPoolInfo, CLMMPoolInfo]]:
        """
        Retrieves pool information for a given trading pair.
        Uses the appropriate model (AMMPoolInfo or CLMMPoolInfo) based on connector type.
        """
        try:
            # First get the pool address for the trading pair
            pool_address = await self.get_pool_address(trading_pair)

            if not pool_address:
                self.logger().warning(f"Could not find pool address for {trading_pair}")
                return None

            return await self.get_pool_info_by_address(pool_address)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error fetching pool info for {trading_pair} on {self.connector_name}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None

    def add_liquidity(self, trading_pair: str, price: float, **request_args) -> str:
        """
        Adds liquidity to a pool - either concentrated (CLMM) or regular (AMM) based on the connector type.
        :param trading_pair: The market trading pair
        :param price: The center price for the position.
        :param request_args: Additional arguments for liquidity addition
        :return: A newly created order id (internal).
        """
        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.create_market_order_id(trade_type, trading_pair)

        # Check connector type and call appropriate function
        connector_type = get_connector_type(self.connector_name)
        if connector_type == ConnectorType.CLMM:
            safe_ensure_future(self._clmm_add_liquidity(trade_type, order_id, trading_pair, price, **request_args))
        elif connector_type == ConnectorType.AMM:
            safe_ensure_future(self._amm_add_liquidity(trade_type, order_id, trading_pair, price, **request_args))
        else:
            raise ValueError(f"Connector type {connector_type} does not support liquidity provision")

        return order_id

    async def _clmm_add_liquidity(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        price: float,
        lower_price: Optional[float] = None,
        upper_price: Optional[float] = None,
        upper_width_pct: Optional[float] = None,
        lower_width_pct: Optional[float] = None,
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        pool_address: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        """
        Opens a concentrated liquidity position with explicit price range or calculated from percentages.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param price: The center price for the position (used if lower/upper_price not provided)
        :param lower_price: Explicit lower price bound (takes priority over percentages)
        :param upper_price: Explicit upper price bound (takes priority over percentages)
        :param upper_width_pct: The upper range width percentage from center price (e.g. 10.0 for +10%)
        :param lower_width_pct: The lower range width percentage from center price (e.g. 5.0 for -5%)
        :param base_token_amount: Amount of base token to add (optional)
        :param quote_token_amount: Amount of quote token to add (optional)
        :param slippage_pct: Maximum allowed slippage percentage
        :param pool_address: Explicit pool address (optional, will lookup by trading_pair if not provided)
        :param extra_params: Optional connector-specific parameters (e.g., {"strategyType": 0} for Meteora)
        :return: Response from the gateway API
        """
        # Check connector type is CLMM
        if get_connector_type(self.connector_name) != ConnectorType.CLMM:
            raise ValueError(f"Connector {self.connector_name} is not of type CLMM.")

        # Split trading_pair to get base and quote tokens
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

        # Calculate the total amount in base token units
        base_amount = base_token_amount or 0.0
        quote_amount_in_base = (quote_token_amount or 0.0) / price if price > 0 else 0.0
        total_amount_in_base = base_amount + quote_amount_in_base

        # Start tracking order with calculated amount
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=Decimal(str(price)),
                                  amount=Decimal(str(total_amount_in_base)),
                                  order_type=OrderType.AMM_ADD)

        # Determine position price range
        # Priority: explicit prices > width percentages
        if lower_price is not None and upper_price is not None:
            # Use explicit price bounds (highest priority)
            pass  # lower_price and upper_price already set
        elif upper_width_pct is not None and lower_width_pct is not None:
            # Calculate from width percentages
            lower_width_decimal = lower_width_pct / 100.0
            upper_width_decimal = upper_width_pct / 100.0
            lower_price = price * (1 - lower_width_decimal)
            upper_price = price * (1 + upper_width_decimal)
        else:
            raise ValueError("Must provide either (lower_price and upper_price) or (upper_width_pct and lower_width_pct)")

        # Get pool address - use explicit if provided, otherwise lookup by trading pair
        if not pool_address:
            pool_address = await self.get_pool_address(trading_pair)
            if not pool_address:
                raise ValueError(f"Could not find pool for {trading_pair}")

        # Store metadata for event triggering (will be enriched with response data)
        self._lp_orders_metadata[order_id] = {
            "operation": "add",
            "lower_price": Decimal(str(lower_price)),
            "upper_price": Decimal(str(upper_price)),
            "amount": Decimal(str(total_amount_in_base)),
            "fee_tier": pool_address,  # Use pool address as fee tier identifier
        }

        # Open position
        try:
            transaction_result = await self._get_gateway_instance().clmm_open_position(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                lower_price=lower_price,
                upper_price=upper_price,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=slippage_pct,
                extra_params=extra_params
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                # Store response data in metadata for P&L tracking
                # Gateway returns positive values for token amounts
                data = transaction_result.get("data", {})
                self._lp_orders_metadata[order_id].update({
                    "position_address": data.get("positionAddress", ""),
                    "base_amount": Decimal(str(data.get("baseTokenAmountAdded", 0))),
                    "quote_amount": Decimal(str(data.get("quoteTokenAmountAdded", 0))),
                    # SOL rent paid to create position
                    "position_rent": Decimal(str(data.get("positionRent", 0))),
                    # SOL transaction fee
                    "tx_fee": Decimal(str(data.get("fee", 0))),
                })
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "opening CLMM position", e)
            raise  # Re-raise so executor can catch and retry if needed

    async def _amm_add_liquidity(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        price: float,
        base_token_amount: float,
        quote_token_amount: float,
        slippage_pct: Optional[float] = None,
    ):
        """
        Opens a regular AMM liquidity position.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param price: The price for the position
        :param base_token_amount: Amount of base token to add (required)
        :param quote_token_amount: Amount of quote token to add (required)
        :param slippage_pct: Maximum allowed slippage percentage
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Split trading_pair to get base and quote tokens
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

        # Calculate the total amount in base token units
        quote_amount_in_base = quote_token_amount / price if price > 0 else 0.0
        total_amount_in_base = base_token_amount + quote_amount_in_base

        # Start tracking order with calculated amount
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=Decimal(str(price)),
                                  amount=Decimal(str(total_amount_in_base)),
                                  order_type=OrderType.AMM_ADD)

        # Get pool address for the trading pair
        pool_address = await self.get_pool_address(trading_pair)
        if not pool_address:
            raise ValueError(f"Could not find pool for {trading_pair}")

        # Add liquidity to AMM pool
        try:
            transaction_result = await self._get_gateway_instance().amm_add_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=slippage_pct
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "opening AMM position", e)

    def remove_liquidity(
        self,
        trading_pair: str,
        position_address: Optional[str] = None,
        percentage: float = 100.0,
        **request_args
    ) -> str:
        """
        Removes liquidity from a position - either concentrated (CLMM) or regular (AMM) based on the connector type.
        :param trading_pair: The market trading pair
        :param position_address: The address of the position (required for CLMM, optional for AMM)
        :param percentage: Percentage of liquidity to remove (defaults to 100%)
        :return: A newly created order id (internal).
        """
        connector_type = get_connector_type(self.connector_name)

        # Verify we have a position address for CLMM positions
        if connector_type == ConnectorType.CLMM and position_address is None:
            raise ValueError("position_address is required to close a CLMM position")

        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.create_market_order_id(trade_type, trading_pair)

        # Call appropriate function based on connector type and percentage
        if connector_type == ConnectorType.CLMM:
            if percentage == 100.0:
                # Complete close for CLMM
                safe_ensure_future(self._clmm_close_position(trade_type, order_id, trading_pair, position_address, **request_args))
            else:
                # Partial removal for CLMM
                safe_ensure_future(self._clmm_remove_liquidity(trade_type, order_id, trading_pair, position_address, percentage, **request_args))
        elif connector_type == ConnectorType.AMM:
            # AMM always uses remove_liquidity
            safe_ensure_future(self._amm_remove_liquidity(trade_type, order_id, trading_pair, percentage, **request_args))
        else:
            raise ValueError(f"Connector type {connector_type} does not support liquidity provision")

        return order_id

    async def _clmm_close_position(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        position_address: str,
        fail_silently: bool = False,
    ):
        """
        Closes a concentrated liquidity position for the given position address.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param position_address: The address of the position to close
        :param fail_silently: Whether to fail silently on error
        """
        # Check connector type is CLMM
        if get_connector_type(self.connector_name) != ConnectorType.CLMM:
            raise ValueError(f"Connector {self.connector_name} is not of type CLMM.")

        # Start tracking order
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  order_type=OrderType.AMM_REMOVE)

        # Store metadata for event triggering (will be enriched with response data)
        self._lp_orders_metadata[order_id] = {
            "operation": "remove",
            "position_address": position_address,
        }

        try:
            transaction_result = await self._get_gateway_instance().clmm_close_position(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                position_address=position_address,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                # Store response data in metadata for P&L tracking
                # Gateway returns positive values for token amounts
                data = transaction_result.get("data", {})
                self._lp_orders_metadata[order_id].update({
                    "base_amount": Decimal(str(data.get("baseTokenAmountRemoved", 0))),
                    "quote_amount": Decimal(str(data.get("quoteTokenAmountRemoved", 0))),
                    "base_fee": Decimal(str(data.get("baseFeeAmountCollected", 0))),
                    "quote_fee": Decimal(str(data.get("quoteFeeAmountCollected", 0))),
                    # SOL rent refunded on close
                    "position_rent_refunded": Decimal(str(data.get("positionRentRefunded", 0))),
                    # SOL transaction fee
                    "tx_fee": Decimal(str(data.get("fee", 0))),
                })
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "closing CLMM position", e)
            raise  # Re-raise so executor can catch and retry if needed

    async def _clmm_remove_liquidity(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        position_address: str,
        percentage: float = 100.0,
        fail_silently: bool = False,
    ):
        """
        Removes liquidity from a CLMM position (partial removal).

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param position_address: The address of the position
        :param percentage: Percentage of liquidity to remove (0-100)
        :param fail_silently: Whether to fail silently on error
        """
        # Check connector type is CLMM
        if get_connector_type(self.connector_name) != ConnectorType.CLMM:
            raise ValueError(f"Connector {self.connector_name} is not of type CLMM.")

        # Start tracking order
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  order_type=OrderType.AMM_REMOVE)

        # Store metadata for event triggering (will be enriched with response data)
        self._lp_orders_metadata[order_id] = {
            "operation": "remove",
            "position_address": position_address,
        }

        try:
            transaction_result = await self._get_gateway_instance().clmm_remove_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                position_address=position_address,
                percentage=percentage,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                # Store response data in metadata for P&L tracking
                # Gateway returns positive values for token amounts
                data = transaction_result.get("data", {})
                self._lp_orders_metadata[order_id].update({
                    "base_amount": Decimal(str(data.get("baseTokenAmountRemoved", 0))),
                    "quote_amount": Decimal(str(data.get("quoteTokenAmountRemoved", 0))),
                    "base_fee": Decimal(str(data.get("baseFeeAmountCollected", 0))),
                    "quote_fee": Decimal(str(data.get("quoteFeeAmountCollected", 0))),
                    # SOL rent refunded on close
                    "position_rent_refunded": Decimal(str(data.get("positionRentRefunded", 0))),
                    # SOL transaction fee
                    "tx_fee": Decimal(str(data.get("fee", 0))),
                })
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "removing CLMM liquidity", e)

    async def _amm_remove_liquidity(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        percentage: float = 100.0,
        fail_silently: bool = False,
    ):
        """
        Closes an AMM liquidity position by removing specified percentage of liquidity.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param percentage: Percentage of liquidity to remove (0-100)
        :param fail_silently: Whether to fail silently on error
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Get pool address for the trading pair
        pool_address = await self.get_pool_address(trading_pair)
        if not pool_address:
            raise ValueError(f"Could not find pool for {trading_pair}")

        # Start tracking order
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  order_type=OrderType.AMM_REMOVE)

        try:
            transaction_result = await self._get_gateway_instance().amm_remove_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                percentage=percentage,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "closing AMM position", e)

    async def amm_add_liquidity(
        self,
        trading_pair: str,
        base_token_amount: float,
        quote_token_amount: float,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Adds liquidity to an AMM pool.
        :param trading_pair: The trading pair for the position
        :param base_token_amount: Amount of base token to add
        :param quote_token_amount: Amount of quote token to add
        :param slippage_pct: Maximum allowed slippage percentage
        :param fail_silently: Whether to fail silently on error
        :return: Response from the gateway API
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Get pool address for the trading pair
        pool_address = await self.get_pool_address(trading_pair)
        if not pool_address:
            raise ValueError(f"Could not find pool for {trading_pair}")

        order_id: str = self.create_market_order_id(TradeType.RANGE, trading_pair)
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=TradeType.RANGE)
        try:
            transaction_result = await self._get_gateway_instance().amm_add_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=slippage_pct,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
            else:
                raise ValueError
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "adding AMM liquidity", e)

    async def amm_remove_liquidity(
        self,
        trading_pair: str,
        percentage: float,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Removes liquidity from an AMM pool.
        :param trading_pair: The trading pair for the position
        :param percentage: Percentage of liquidity to remove (0-100)
        :param fail_silently: Whether to fail silently on error
        :return: Response from the gateway API
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Get pool address for the trading pair
        pool_address = await self.get_pool_address(trading_pair)
        if not pool_address:
            raise ValueError(f"Could not find pool for {trading_pair}")

        order_id: str = self.create_market_order_id(TradeType.RANGE, trading_pair)
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=TradeType.RANGE)
        try:
            transaction_result = await self._get_gateway_instance().amm_remove_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                percentage=percentage,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
            else:
                raise ValueError
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "removing AMM liquidity", e)

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_position_info(
        self,
        trading_pair: str,
        position_address: Optional[str] = None
    ) -> Union[AMMPositionInfo, CLMMPositionInfo, None]:
        """
        Retrieves position information for a given liquidity position.

        :param trading_pair: The trading pair for the position
        :param position_address: The address of the position (required for CLMM, optional for AMM)
        :return: Position information from gateway, validated against appropriate schema
        """
        try:
            # Split trading_pair to get base and quote tokens
            tokens = trading_pair.split("-")
            if len(tokens) != 2:
                raise ValueError(f"Invalid trading pair format: {trading_pair}")

            base_token, quote_token = tokens

            connector_type = get_connector_type(self.connector_name)
            if connector_type == ConnectorType.CLMM:
                if position_address is None:
                    raise ValueError("position_address is required for CLMM positions")

                resp: Dict[str, Any] = await self._get_gateway_instance().clmm_position_info(
                    connector=self.connector_name,
                    network=self.network,
                    position_address=position_address,
                    wallet_address=self.address,
                )
                # Validate response against CLMM schema
                return CLMMPositionInfo(**resp) if resp else None

            elif connector_type == ConnectorType.AMM:
                resp: Dict[str, Any] = await self._get_gateway_instance().amm_position_info(
                    connector=self.connector_name,
                    network=self.network,
                    pool_address=position_address,
                    wallet_address=self.address,
                )
                # Validate response against AMM schema
                return AMMPositionInfo(**resp) if resp else None

            else:
                raise ValueError(f"Connector type {connector_type} does not support liquidity positions")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            addr_info = f"position {position_address}" if position_address else trading_pair
            self.logger().network(
                f"Error fetching position info for {addr_info} on {self.connector_name}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None

    async def get_user_positions(self, pool_address: Optional[str] = None) -> List[Union[AMMPositionInfo, CLMMPositionInfo]]:
        """
        Fetch all user positions for this connector and wallet.

        :param pool_address: Optional pool address to filter positions (required for AMM)
        :return: List of position information objects
        """
        positions = []

        try:
            connector_type = get_connector_type(self.connector_name)

            if connector_type == ConnectorType.CLMM:
                # For CLMM, use positions-owned endpoint
                # Note: Gateway API doesn't support poolAddress filtering, so we filter client-side
                response = await self._get_gateway_instance().clmm_positions_owned(
                    connector=self.connector_name,
                    network=self.network,
                    wallet_address=self.address,
                    pool_address=None  # Gateway doesn't support this parameter
                )
            else:
                # For AMM, we need a pool address
                if not pool_address:
                    self.logger().warning("AMM position fetching requires a pool address")
                    return []

                # For AMM, get position info directly from the pool
                # We'll need to get pool info first to extract tokens
                pool_resp = await self._get_gateway_instance().pool_info(
                    connector=self.connector_name,
                    network=self.network,
                    pool_address=pool_address
                )

                if not pool_resp:
                    return []

                # Now get the position info
                resp = await self._get_gateway_instance().amm_position_info(
                    connector=self.connector_name,
                    network=self.network,
                    pool_address=pool_address,
                    wallet_address=self.address
                )

                if resp:
                    position = AMMPositionInfo(**resp)
                    # Get token symbols from loaded token data
                    base_token_info = self.get_token_by_address(position.base_token_address)
                    quote_token_info = self.get_token_by_address(position.quote_token_address)

                    # Use symbol if found, otherwise use address
                    position.base_token = base_token_info.get("symbol", position.base_token_address) if base_token_info else position.base_token_address
                    position.quote_token = quote_token_info.get("symbol", position.quote_token_address) if quote_token_info else position.quote_token_address
                    return [position]
                else:
                    return []

            # Parse position data based on connector type (for CLMM)
            # Handle case where response might be a list directly or a dict with 'positions' key
            positions_list = response if isinstance(response, list) else response.get("positions", [])
            for pos_data in positions_list:
                try:
                    if connector_type == ConnectorType.CLMM:
                        position = CLMMPositionInfo(**pos_data)

                        # Get token symbols from loaded token data
                        base_token_info = self.get_token_by_address(position.base_token_address)
                        quote_token_info = self.get_token_by_address(position.quote_token_address)

                        # Use symbol if found, otherwise use address
                        position.base_token = base_token_info.get("symbol", position.base_token_address) if base_token_info else position.base_token_address
                        position.quote_token = quote_token_info.get("symbol", position.quote_token_address) if quote_token_info else position.quote_token_address

                        positions.append(position)
                    else:
                        position = AMMPositionInfo(**pos_data)

                        # Get token symbols from loaded token data
                        base_token_info = self.get_token_by_address(position.base_token_address)
                        quote_token_info = self.get_token_by_address(position.quote_token_address)

                        # Use symbol if found, otherwise use address
                        position.base_token = base_token_info.get("symbol", position.base_token_address) if base_token_info else position.base_token_address
                        position.quote_token = quote_token_info.get("symbol", position.quote_token_address) if quote_token_info else position.quote_token_address

                        positions.append(position)

                except Exception as e:
                    self.logger().error(f"Error parsing position data: {e}", exc_info=True)
                    continue

            # Filter positions by pool_address if specified (client-side filtering)
            if pool_address and connector_type == ConnectorType.CLMM:
                positions = [p for p in positions if hasattr(p, 'pool_address') and p.pool_address == pool_address]

        except Exception as e:
            self.logger().error(f"Error fetching positions: {e}", exc_info=True)

        return positions
