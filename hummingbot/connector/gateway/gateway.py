"""
Combined Gateway connector for all gateway operations (swap and LP).

This module provides a unified connector for interacting with DEXes through Gateway.
The connector handles both swap operations and liquidity provision (AMM/CLMM).

Architecture:
- connector_name: Network identifier (e.g., "solana-mainnet-beta")
- dex_name: DEX protocol name passed to methods (e.g., "orca", "jupiter")
- trading_type: Pool type passed to methods (e.g., "clmm", "amm", "router")
"""

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import LPType, OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateFailureEvent,
    SellOrderCreatedEvent,
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


class Gateway(GatewayBase):
    """
    Unified Gateway connector for swap and LP operations.

    This connector handles:
    - Swap operations (buy, sell, get_quote_price)
    - LP operations (add_liquidity, remove_liquidity, get_pool_info)

    The dex_name and trading_type are passed as parameters to methods rather than
    being derived from the connector_name.
    """

    # Error code from gateway for transaction confirmation timeout
    TRANSACTION_TIMEOUT_CODE = "TRANSACTION_TIMEOUT"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store LP operation metadata for triggering proper events
        self._lp_orders_metadata: Dict[str, Dict] = {}

    @staticmethod
    def _parse_dex_name(dex_name: str, default_trading_type: str = "router") -> tuple:
        """
        Parse dex_name into (dex, trading_type) tuple.

        Args:
            dex_name: DEX identifier, can be:
                - "jupiter" -> ("jupiter", default_trading_type)
                - "jupiter/router" -> ("jupiter", "router")
                - "orca/clmm" -> ("orca", "clmm")
            default_trading_type: Default trading type if not specified

        Returns:
            Tuple of (dex, trading_type)
        """
        if "/" in dex_name:
            parts = dex_name.split("/", 1)
            return parts[0], parts[1]
        return dex_name, default_trading_type

    # ==================== SWAP OPERATIONS ====================

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            dex_name: Optional[str] = None,
            slippage_pct: Optional[Decimal] = None,
            pool_address: Optional[str] = None
    ) -> Optional[Decimal]:
        """
        Retrieves the volume weighted average price for a swap.

        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :param dex_name: DEX protocol name (e.g., "jupiter", "orca")
        :param slippage_pct: Maximum allowed slippage percentage
        :param pool_address: Optional specific pool address
        :return: The quote price.
        """
        base, quote = trading_pair.split("-")
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL

        if not dex_name:
            raise ValueError("dex_name is required for swap operations on unified Gateway connector")

        dex, trading_type = self._parse_dex_name(dex_name)

        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().quote_swap(
                network=self.network,
                dex=dex,
                trading_type=trading_type,
                base_asset=base,
                quote_asset=quote,
                amount=amount,
                side=side,
                slippage_pct=slippage_pct,
                pool_address=pool_address
            )
            price = resp.get("price", None)
            return Decimal(price) if price is not None else None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair} {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_order_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            dex_name: Optional[str] = None,
    ) -> Decimal:
        """
        Retrieves the price required for an order of a given amount.
        """
        return await self.get_quote_price(trading_pair, is_buy, amount, dex_name=dex_name)

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Buys an amount of base token for a given price (or cheaper).
        """
        return self.place_order(True, trading_pair, amount, price, **kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Sells an amount of base token for a given price (or at a higher price).
        """
        return self.place_order(False, trading_pair, amount, price, **kwargs)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal, **request_args) -> str:
        """
        Places a swap order.
        """
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL
        order_id: str = self.create_market_order_id(side, trading_pair)
        safe_ensure_future(self._create_order(side, order_id, trading_pair, amount, price, **request_args))
        return order_id

    async def _create_order(
            self,
            trade_type: TradeType,
            order_id: str,
            trading_pair: str,
            amount: Decimal,
            price: Decimal,
            **kwargs
    ):
        """
        Executes a swap order through Gateway.

        :param trade_type: BUY or SELL
        :param order_id: Internal order id
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        :param kwargs: Additional parameters (dex, quote_id, pool_address, slippage_pct, max_retries)
        """
        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        base, quote = trading_pair.split("-")

        # Check if order is already being tracked
        existing_order = self._order_tracker.fetch_order(order_id)
        if existing_order is not None:
            self.logger().debug(f"Order {order_id} already tracked, skipping event emission")
        else:
            self.start_tracking_order(order_id=order_id,
                                      trading_pair=trading_pair,
                                      trade_type=trade_type,
                                      price=price,
                                      amount=amount)

            # Emit order created event
            event_class = BuyOrderCreatedEvent if trade_type == TradeType.BUY else SellOrderCreatedEvent
            event_tag = MarketEvent.BuyOrderCreated if trade_type == TradeType.BUY else MarketEvent.SellOrderCreated
            self.trigger_event(
                event_tag,
                event_class(
                    timestamp=self.current_timestamp,
                    type=OrderType.MARKET,
                    trading_pair=trading_pair,
                    amount=amount,
                    price=price,
                    order_id=order_id,
                    creation_timestamp=self.current_timestamp,
                    exchange_order_id=None,
                )
            )

        # Extract optional parameters
        dex_name = kwargs.get("dex_name")
        quote_id = kwargs.get("quote_id")
        pool_address = kwargs.get("pool_address")
        slippage_pct = kwargs.get("slippage_pct")
        max_retries = kwargs.get("max_retries", 10)

        if not dex_name:
            raise ValueError("dex_name is required for swap operations on unified Gateway connector")

        dex, trading_type = self._parse_dex_name(dex_name)

        async def execute_gateway_swap() -> Dict[str, Any]:
            if quote_id:
                return await self._get_gateway_instance().execute_quote(
                    dex=dex,
                    trading_type=trading_type,
                    quote_id=quote_id,
                    network=self.network,
                    wallet_address=self.address
                )
            else:
                return await self._get_gateway_instance().execute_swap(
                    dex=dex,
                    trading_type=trading_type,
                    base_asset=base,
                    quote_asset=quote,
                    side=trade_type,
                    amount=amount,
                    network=self.network,
                    wallet_address=self.address,
                    pool_address=pool_address,
                    slippage_pct=slippage_pct
                )

        try:
            order_result = await self._execute_with_retry(
                operation=execute_gateway_swap,
                operation_name=f"swap {trade_type.name} {amount} on {trading_pair}",
                max_retries=max_retries,
            )

            transaction_hash: Optional[str] = order_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, order_result)
                self._store_swap_result(order_id, trade_type, trading_pair, amount, order_result, transaction_hash)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, f"submitting {trade_type.name} swap order", e)

    def _store_swap_result(
        self,
        order_id: str,
        trade_type: TradeType,
        trading_pair: str,
        amount: Decimal,
        order_result: Dict[str, Any],
        transaction_hash: str
    ):
        """Store swap result data by creating a TradeUpdate for proper fill tracking."""
        data = order_result.get("data", {})
        amount_in = Decimal(str(data.get("amountIn", "0")))
        amount_out = Decimal(str(data.get("amountOut", "0")))

        if trade_type == TradeType.SELL:
            executed_price = amount_out / amount_in if amount_in > 0 and amount_out > 0 else Decimal("0")
        else:
            executed_price = amount_in / amount_out if amount_in > 0 and amount_out > 0 else Decimal("0")

        tracked_order = self._order_tracker.fetch_order(order_id)
        if not tracked_order:
            return

        fee = Decimal(str(data.get("fee", 0)))
        fee_asset = self._native_currency
        trade_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(fee_asset, fee)])

        fill_base_amount = tracked_order.amount

        trade_update = TradeUpdate(
            trade_id=transaction_hash,
            client_order_id=order_id,
            exchange_order_id=transaction_hash,
            trading_pair=trading_pair,
            fill_timestamp=self.current_timestamp,
            fill_price=executed_price,
            fill_base_amount=fill_base_amount,
            fill_quote_amount=fill_base_amount * executed_price,
            fee=trade_fee
        )

        self.logger().info(
            f"Processing trade update for {order_id}: fill_amount={fill_base_amount}, "
            f"fill_price={executed_price}, trade_id={transaction_hash}"
        )
        self._order_tracker.process_trade_update(trade_update)

        order_update = OrderUpdate(
            client_order_id=order_id,
            exchange_order_id=transaction_hash,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FILLED,
        )
        self._order_tracker.process_order_update(order_update)

    # ==================== LP OPERATIONS ====================

    def _trigger_lp_events_if_needed(self, order_id: str, transaction_hash: str):
        """Helper to trigger LP-specific events when an order completes."""
        if order_id not in self._lp_orders_metadata:
            return

        tracked_order = self._order_tracker.fetch_order(order_id)
        if not tracked_order or tracked_order.trade_type != TradeType.RANGE:
            return

        metadata = self._lp_orders_metadata[order_id]

        is_successful = tracked_order.is_done and not tracked_order.is_failure and not tracked_order.is_cancelled

        if is_successful:
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
                    position_address=metadata.get("position_address", ""),
                    base_amount=metadata.get("base_amount", Decimal("0")),
                    quote_amount=metadata.get("quote_amount", Decimal("0")),
                    base_fee=metadata.get("base_fee", Decimal("0")),
                    quote_fee=metadata.get("quote_fee", Decimal("0")),
                    position_rent_refunded=metadata.get("position_rent_refunded", Decimal("0")),
                )
        elif tracked_order.is_failure:
            operation_type = "add" if metadata["operation"] == "add" else "remove"
            self.logger().error(
                f"LP {operation_type} liquidity transaction failed for order {order_id} (tx: {transaction_hash})"
            )
            self.trigger_event(
                MarketEvent.RangePositionUpdateFailure,
                RangePositionUpdateFailureEvent(
                    timestamp=self.current_timestamp,
                    order_id=order_id,
                    order_action=LPType.ADD if metadata["operation"] == "add" else LPType.REMOVE,
                )
            )
        elif tracked_order.is_cancelled:
            operation_type = "add" if metadata["operation"] == "add" else "remove"
            self.logger().warning(
                f"LP {operation_type} liquidity transaction cancelled for order {order_id} (tx: {transaction_hash})"
            )

        del self._lp_orders_metadata[order_id]
        self.stop_tracking_order(order_id)

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """Override to trigger RangePosition events after LP transactions complete."""
        await super().update_order_status(tracked_orders)

        for tracked_order in tracked_orders:
            if tracked_order.trade_type == TradeType.RANGE:
                try:
                    tx_hash = await tracked_order.get_exchange_order_id()
                    self._trigger_lp_events_if_needed(tracked_order.client_order_id, tx_hash)
                except Exception as e:
                    self.logger().warning(f"Error triggering LP event for {tracked_order.client_order_id}: {e}", exc_info=True)

    def _handle_operation_failure(self, order_id: str, trading_pair: str, operation_name: str, error: Exception):
        """Override to trigger RangePositionUpdateFailureEvent for LP operations."""
        super()._handle_operation_failure(order_id, trading_pair, operation_name, error)

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
            del self._lp_orders_metadata[order_id]
        elif order_id in self._lp_orders_metadata:
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
    ) -> RangePositionLiquidityAddedEvent:
        """Trigger RangePositionLiquidityAddedEvent and return the event."""
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
            position_address=position_address,
            mid_price=mid_price,
            base_amount=base_amount,
            quote_amount=quote_amount,
            position_rent=position_rent,
        )
        self.trigger_event(MarketEvent.RangePositionLiquidityAdded, event)
        self.logger().info(f"Triggered RangePositionLiquidityAddedEvent for order {order_id}")
        return event

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
    ) -> RangePositionLiquidityRemovedEvent:
        """Trigger RangePositionLiquidityRemovedEvent and return the event."""
        event = RangePositionLiquidityRemovedEvent(
            timestamp=self.current_timestamp,
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            token_id=token_id,
            trade_fee=trade_fee,
            creation_timestamp=creation_timestamp,
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
        return event

    @async_ttl_cache(ttl=300, maxsize=10)
    async def get_pool_address(
        self,
        trading_pair: str,
        dex_name: str,
        trading_type: str = "clmm"
    ) -> Optional[str]:
        """
        Get pool address for a trading pair (cached for 5 minutes).

        :param trading_pair: Trading pair (e.g., "SOL-USDC")
        :param dex_name: DEX protocol name (e.g., "orca", "meteora", "raydium")
        :param trading_type: Trading type (e.g., "clmm", "amm"). Defaults to "clmm".
        :return: Pool address or None if not found
        """
        try:
            pool_info = await self._get_gateway_instance().get_pool(
                trading_pair=trading_pair,
                dex=dex_name,
                network=self.network,
                trading_type=trading_type
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
        dex_name: str,
        trading_type: str = "clmm",
    ) -> Optional[Union[AMMPoolInfo, CLMMPoolInfo]]:
        """
        Retrieves pool information by pool address directly.

        :param pool_address: The pool contract address
        :param dex_name: DEX protocol name (e.g., "orca", "meteora")
        :param trading_type: Trading type (e.g., "clmm", "amm"). Defaults to "clmm".
        :return: Pool info object or None if not found
        """
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().pool_info(
                network=self.network,
                pool_address=pool_address,
                dex=dex_name,
                trading_type=trading_type,
            )

            if not resp:
                return None

            if trading_type == "clmm":
                return CLMMPoolInfo(**resp)
            elif trading_type == "amm":
                return AMMPoolInfo(**resp)
            else:
                self.logger().warning(f"Unknown trading type: {trading_type}")
                return None

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error fetching pool info for address {pool_address}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None

    async def resolve_trading_pair_from_pool(
        self,
        pool_address: str,
        dex_name: str,
        trading_type: str = "clmm",
    ) -> Optional[Dict[str, str]]:
        """
        Resolve trading pair information from pool address.
        """
        try:
            pool_info_resp = await self._get_gateway_instance().pool_info(
                network=self.network,
                pool_address=pool_address,
                dex=dex_name,
                trading_type=trading_type,
            )

            if not pool_info_resp:
                raise ValueError(f"Could not fetch pool info for pool address {pool_address}")

            base_token_address = pool_info_resp.get("baseTokenAddress")
            quote_token_address = pool_info_resp.get("quoteTokenAddress")

            if not base_token_address or not quote_token_address:
                raise ValueError(f"Pool info missing token addresses: {pool_info_resp}")

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

    def add_liquidity(
        self,
        trading_pair: str,
        price: float,
        dex_name: str,
        trading_type: str = "clmm",
        **request_args
    ) -> str:
        """
        Adds liquidity to a pool - either concentrated (CLMM) or regular (AMM).

        :param trading_pair: The market trading pair
        :param price: The center price for the position.
        :param dex_name: DEX protocol name (e.g., "orca", "meteora", "raydium")
        :param trading_type: Trading type (e.g., "clmm", "amm"). Defaults to "clmm".
        :param request_args: Additional arguments for liquidity addition
        :return: A newly created order id (internal).
        """
        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.create_market_order_id(trade_type, trading_pair)

        if trading_type == "clmm":
            safe_ensure_future(self._clmm_add_liquidity(trade_type, order_id, trading_pair, price, dex_name=dex_name, trading_type=trading_type, **request_args))
        elif trading_type == "amm":
            safe_ensure_future(self._amm_add_liquidity(trade_type, order_id, trading_pair, price, dex_name=dex_name, trading_type=trading_type, **request_args))
        else:
            raise ValueError(f"Trading type {trading_type} does not support liquidity provision")

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
        max_retries: int = 10,
        dex_name: Optional[str] = None,
        trading_type: str = "clmm",
    ):
        """Opens a concentrated liquidity position."""
        if not dex_name:
            raise ValueError("dex_name parameter is required for CLMM operations")

        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

        base_amount = base_token_amount or 0.0
        quote_amount_in_base = (quote_token_amount or 0.0) / price if price > 0 else 0.0
        total_amount_in_base = base_amount + quote_amount_in_base

        existing_order = self._order_tracker.fetch_order(order_id)
        if existing_order is not None:
            self.logger().debug(f"Order {order_id} already tracked, skipping start_tracking_order")
        else:
            self.start_tracking_order(order_id=order_id,
                                      trading_pair=trading_pair,
                                      trade_type=trade_type,
                                      price=Decimal(str(price)),
                                      amount=Decimal(str(total_amount_in_base)),
                                      order_type=OrderType.AMM_ADD)

        if lower_price is not None and upper_price is not None:
            pass
        elif upper_width_pct is not None and lower_width_pct is not None:
            lower_width_decimal = lower_width_pct / 100.0
            upper_width_decimal = upper_width_pct / 100.0
            lower_price = price * (1 - lower_width_decimal)
            upper_price = price * (1 + upper_width_decimal)
        else:
            raise ValueError("Must provide either (lower_price and upper_price) or (upper_width_pct and lower_width_pct)")

        if not pool_address:
            pool_address = await self.get_pool_address(trading_pair, dex_name=dex_name, trading_type=trading_type)
            if not pool_address:
                raise ValueError(f"Could not find pool for {trading_pair}")

        self._lp_orders_metadata[order_id] = {
            "operation": "add",
            "lower_price": Decimal(str(lower_price)),
            "upper_price": Decimal(str(upper_price)),
            "amount": Decimal(str(total_amount_in_base)),
            "fee_tier": pool_address,
        }

        async def execute_open_position() -> Dict[str, Any]:
            return await self._get_gateway_instance().clmm_open_position(
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                lower_price=lower_price,
                upper_price=upper_price,
                dex=dex_name,
                trading_type=trading_type,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=slippage_pct,
                extra_params=extra_params
            )

        try:
            transaction_result = await self._execute_with_retry(
                operation=execute_open_position,
                operation_name=f"CLMM open position on {trading_pair}",
                max_retries=max_retries,
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                data = transaction_result.get("data", {})
                self._lp_orders_metadata[order_id].update({
                    "position_address": data.get("positionAddress", ""),
                    "base_amount": Decimal(str(data.get("baseTokenAmountAdded", 0))),
                    "quote_amount": Decimal(str(data.get("quoteTokenAmountAdded", 0))),
                    "position_rent": Decimal(str(data.get("positionRent", 0))),
                    "tx_fee": Decimal(str(data.get("fee", 0))),
                })
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "opening CLMM position", e)
            raise

    async def _amm_add_liquidity(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        price: float,
        base_token_amount: float,
        quote_token_amount: float,
        dex_name: str,
        trading_type: str = "amm",
        slippage_pct: Optional[float] = None,
    ):
        """Opens a regular AMM liquidity position."""
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        quote_amount_in_base = quote_token_amount / price if price > 0 else 0.0
        total_amount_in_base = base_token_amount + quote_amount_in_base

        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=Decimal(str(price)),
                                  amount=Decimal(str(total_amount_in_base)),
                                  order_type=OrderType.AMM_ADD)

        pool_address = await self.get_pool_address(trading_pair, dex_name=dex_name, trading_type=trading_type)
        if not pool_address:
            raise ValueError(f"Could not find pool for {trading_pair}")

        try:
            transaction_result = await self._get_gateway_instance().amm_add_liquidity(
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                dex=dex_name,
                trading_type=trading_type,
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
        dex_name: str,
        trading_type: str = "clmm",
        position_address: Optional[str] = None,
        percentage: float = 100.0,
        **request_args
    ) -> str:
        """
        Removes liquidity from a position.

        :param trading_pair: The market trading pair
        :param dex_name: DEX protocol name (e.g., "orca", "meteora", "raydium")
        :param trading_type: Trading type (e.g., "clmm", "amm"). Defaults to "clmm".
        :param position_address: The address of the position (required for CLMM)
        :param percentage: Percentage of liquidity to remove (defaults to 100%)
        :return: A newly created order id (internal).
        """
        if trading_type == "clmm" and position_address is None:
            raise ValueError("position_address is required to close a CLMM position")

        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.create_market_order_id(trade_type, trading_pair)

        if trading_type == "clmm":
            if percentage == 100.0:
                safe_ensure_future(self._clmm_close_position(trade_type, order_id, trading_pair, position_address, dex_name=dex_name, trading_type=trading_type, **request_args))
            else:
                safe_ensure_future(self._clmm_remove_liquidity(trade_type, order_id, trading_pair, position_address, percentage, dex_name=dex_name, trading_type=trading_type, **request_args))
        elif trading_type == "amm":
            safe_ensure_future(self._amm_remove_liquidity(trade_type, order_id, trading_pair, percentage, dex_name=dex_name, trading_type=trading_type, **request_args))
        else:
            raise ValueError(f"Trading type {trading_type} does not support liquidity provision")

        return order_id

    async def _clmm_close_position(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        position_address: str,
        fail_silently: bool = False,
        max_retries: int = 10,
        dex_name: Optional[str] = None,
        trading_type: str = "clmm",
    ):
        """Closes a concentrated liquidity position."""
        if not dex_name:
            raise ValueError("dex_name parameter is required for CLMM operations")

        existing_order = self._order_tracker.fetch_order(order_id)
        if existing_order is not None:
            self.logger().debug(f"Order {order_id} already tracked, skipping start_tracking_order")
        else:
            self.start_tracking_order(order_id=order_id,
                                      trading_pair=trading_pair,
                                      trade_type=trade_type,
                                      order_type=OrderType.AMM_REMOVE)

        self._lp_orders_metadata[order_id] = {
            "operation": "remove",
            "position_address": position_address,
        }

        _dex_name = dex_name
        _trading_type = trading_type
        _network = self.network

        async def execute_close_position() -> Dict[str, Any]:
            return await self._get_gateway_instance().clmm_close_position(
                network=_network,
                wallet_address=self.address,
                position_address=position_address,
                dex=_dex_name,
                trading_type=_trading_type,
                fail_silently=fail_silently
            )

        try:
            transaction_result = await self._execute_with_retry(
                operation=execute_close_position,
                operation_name=f"CLMM close position {position_address}",
                max_retries=max_retries,
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                data = transaction_result.get("data", {})
                self._lp_orders_metadata[order_id].update({
                    "base_amount": Decimal(str(data.get("baseTokenAmountRemoved", 0))),
                    "quote_amount": Decimal(str(data.get("quoteTokenAmountRemoved", 0))),
                    "base_fee": Decimal(str(data.get("baseFeeAmountCollected", 0))),
                    "quote_fee": Decimal(str(data.get("quoteFeeAmountCollected", 0))),
                    "position_rent_refunded": Decimal(str(data.get("positionRentRefunded", 0))),
                    "tx_fee": Decimal(str(data.get("fee", 0))),
                })
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "closing CLMM position", e)
            raise

    async def _clmm_remove_liquidity(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        position_address: str,
        percentage: float,
        dex_name: str,
        trading_type: str = "clmm",
        fail_silently: bool = False,
    ):
        """Removes liquidity from a CLMM position (partial removal)."""
        existing_order = self._order_tracker.fetch_order(order_id)
        if existing_order is not None:
            self.logger().debug(f"Order {order_id} already tracked, skipping start_tracking_order")
        else:
            self.start_tracking_order(order_id=order_id,
                                      trading_pair=trading_pair,
                                      trade_type=trade_type,
                                      order_type=OrderType.AMM_REMOVE)

        self._lp_orders_metadata[order_id] = {
            "operation": "remove",
            "position_address": position_address,
        }

        try:
            transaction_result = await self._get_gateway_instance().clmm_remove_liquidity(
                network=self.network,
                wallet_address=self.address,
                position_address=position_address,
                percentage=percentage,
                dex=dex_name,
                trading_type=trading_type,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                data = transaction_result.get("data", {})
                self._lp_orders_metadata[order_id].update({
                    "base_amount": Decimal(str(data.get("baseTokenAmountRemoved", 0))),
                    "quote_amount": Decimal(str(data.get("quoteTokenAmountRemoved", 0))),
                    "base_fee": Decimal(str(data.get("baseFeeAmountCollected", 0))),
                    "quote_fee": Decimal(str(data.get("quoteFeeAmountCollected", 0))),
                    "position_rent_refunded": Decimal(str(data.get("positionRentRefunded", 0))),
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
        percentage: float,
        dex_name: str,
        trading_type: str = "amm",
        fail_silently: bool = False,
    ):
        """Removes liquidity from an AMM pool."""
        pool_address = await self.get_pool_address(trading_pair, dex_name=dex_name, trading_type=trading_type)
        if not pool_address:
            raise ValueError(f"Could not find pool for {trading_pair}")

        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  order_type=OrderType.AMM_REMOVE)

        try:
            transaction_result = await self._get_gateway_instance().amm_remove_liquidity(
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                percentage=percentage,
                dex=dex_name,
                trading_type=trading_type,
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

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_position_info(
        self,
        trading_pair: str,
        dex_name: str,
        trading_type: str = "clmm",
        position_address: Optional[str] = None
    ) -> Union[AMMPositionInfo, CLMMPositionInfo, None]:
        """Retrieves position information for a given liquidity position."""
        try:
            tokens = trading_pair.split("-")
            if len(tokens) != 2:
                raise ValueError(f"Invalid trading pair format: {trading_pair}")

            if trading_type == "clmm":
                if position_address is None:
                    raise ValueError("position_address is required for CLMM positions")

                resp: Dict[str, Any] = await self._get_gateway_instance().clmm_position_info(
                    network=self.network,
                    position_address=position_address,
                    wallet_address=self.address,
                    dex=dex_name,
                    trading_type=trading_type,
                )
                return CLMMPositionInfo(**resp) if resp else None

            elif trading_type == "amm":
                resp: Dict[str, Any] = await self._get_gateway_instance().amm_position_info(
                    network=self.network,
                    pool_address=position_address,
                    wallet_address=self.address,
                    dex=dex_name,
                    trading_type=trading_type,
                )
                return AMMPositionInfo(**resp) if resp else None

            else:
                raise ValueError(f"Trading type {trading_type} does not support liquidity positions")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            addr_info = f"position {position_address}" if position_address else trading_pair
            self.logger().network(
                f"Error fetching position info for {addr_info} on {dex_name}/{trading_type}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None

    async def get_user_positions(
        self,
        dex_name: str,
        trading_type: str = "clmm",
        pool_address: Optional[str] = None
    ) -> List[Union[AMMPositionInfo, CLMMPositionInfo]]:
        """Fetch all user positions for this connector and wallet."""
        positions = []

        try:
            if trading_type == "clmm":
                response = await self._get_gateway_instance().clmm_positions_owned(
                    network=self.network,
                    wallet_address=self.address,
                    dex=dex_name,
                    trading_type=trading_type,
                    pool_address=None
                )
            else:
                if not pool_address:
                    self.logger().warning("AMM position fetching requires a pool address")
                    return []

                pool_resp = await self._get_gateway_instance().pool_info(
                    network=self.network,
                    pool_address=pool_address,
                    dex=dex_name,
                    trading_type=trading_type,
                )

                if not pool_resp:
                    return []

                resp = await self._get_gateway_instance().amm_position_info(
                    network=self.network,
                    pool_address=pool_address,
                    wallet_address=self.address,
                    dex=dex_name,
                    trading_type=trading_type,
                )

                if resp:
                    position = AMMPositionInfo(**resp)
                    base_token_info = self.get_token_by_address(position.base_token_address)
                    quote_token_info = self.get_token_by_address(position.quote_token_address)

                    position.base_token = base_token_info.get("symbol", position.base_token_address) if base_token_info else position.base_token_address
                    position.quote_token = quote_token_info.get("symbol", position.quote_token_address) if quote_token_info else position.quote_token_address
                    return [position]
                else:
                    return []

            positions_list = response if isinstance(response, list) else response.get("positions", [])
            for pos_data in positions_list:
                try:
                    if trading_type == "clmm":
                        position = CLMMPositionInfo(**pos_data)

                        base_token_info = self.get_token_by_address(position.base_token_address)
                        quote_token_info = self.get_token_by_address(position.quote_token_address)

                        position.base_token = base_token_info.get("symbol", position.base_token_address) if base_token_info else position.base_token_address
                        position.quote_token = quote_token_info.get("symbol", position.quote_token_address) if quote_token_info else position.quote_token_address

                        positions.append(position)
                    else:
                        position = AMMPositionInfo(**pos_data)

                        base_token_info = self.get_token_by_address(position.base_token_address)
                        quote_token_info = self.get_token_by_address(position.quote_token_address)

                        position.base_token = base_token_info.get("symbol", position.base_token_address) if base_token_info else position.base_token_address
                        position.quote_token = quote_token_info.get("symbol", position.quote_token_address) if quote_token_info else position.quote_token_address

                        positions.append(position)

                except Exception as e:
                    self.logger().error(f"Error parsing position data: {e}", exc_info=True)
                    continue

            if pool_address and trading_type == "clmm":
                positions = [p for p in positions if hasattr(p, 'pool_address') and p.pool_address == pool_address]

        except Exception as e:
            self.logger().error(f"Error fetching positions: {e}", exc_info=True)

        return positions
