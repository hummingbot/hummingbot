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

from hummingbot.connector.gateway.gateway_base import TX_DATA_UNAVAILABLE, GatewayBase, extract_error_code
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import LPType, OrderType, PriceType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    MarketEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateFailureEvent,
)
from hummingbot.core.gateway.gateway_error import GatewayError
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather


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
    # Optional in Gateway's CLMM PoolInfo schema ("Optional - Meteora-specific"): only
    # bin-based CLMMs report a bin step. Requiring it here turned every other connector's
    # pool-info response into a pydantic ValidationError, which get_pool_info_by_address
    # swallows into None and the user sees as a misleading "pool not found".
    bin_step: Optional[int] = Field(default=None, alias="binStep")
    fee_pct: float = Field(alias="feePct")
    price: float
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    active_bin_id: int = Field(alias="activeBinId")


class AMMPositionDetail(BaseModel):
    """One individually addressable position, for AMMs whose LP is non-fungible.

    Meteora DAMM v2 positions are NFTs and a wallet may hold several in the same pool;
    remove-liquidity / add-liquidity need this address to name one of them.
    """
    position_address: str = Field(alias="positionAddress")
    lp_token_amount: float = Field(alias="lpTokenAmount")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")


class AMMPositionInfo(BaseModel):
    pool_address: str = Field(alias="poolAddress")
    wallet_address: str = Field(alias="walletAddress")
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    lp_token_amount: float = Field(alias="lpTokenAmount")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    price: float
    # Per-position breakdown; omitted by fungible-LP AMMs, where the pool address
    # identifies the whole holding.
    positions: Optional[List[AMMPositionDetail]] = None
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

    def get_price_by_type(self, trading_pair: str, price_type: PriceType) -> Decimal:
        """
        Gets price by type for gateway connectors.

        Checks RateOracle for cached prices first (set by MarketDataProvider).
        Falls back to NaN if no price is available.

        :param trading_pair: The market trading pair
        :param price_type: The price type (MidPrice, BestBid, BestAsk, etc.)
        :returns: The price or NaN if not available
        """
        # Try to get price from RateOracle (set by MarketDataProvider for gateway connectors)
        try:
            rate_oracle = RateOracle.get_instance()
            price = rate_oracle.get_pair_rate(trading_pair)
            if price and price > 0:
                return price
        except Exception:
            pass
        # Fall back to NaN if no cached price
        return Decimal("nan")

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """
        Return a dictionary with the trading pair as key and its current price as value,
        for each trading pair passed as parameter.

        ExchangeBase supplies this fan-out for order-book connectors, but Gateway
        extends ConnectorBase directly and so never inherited it. That left
        _get_last_traded_price below with no caller at all, and every consumer of the
        plural form raising AttributeError instead of returning prices.

        A pair that cannot be priced is omitted rather than reported as zero, so a
        caller can tell "no price available" from "the price is 0".

        :param trading_pairs: list of trading pairs to get the prices for
        :returns: Dictionary of associations between token pair and its latest price
        """
        results = await safe_gather(
            *[self._get_last_traded_price(trading_pair=trading_pair) for trading_pair in trading_pairs],
            return_exceptions=True,
        )
        prices: Dict[str, float] = {}
        for trading_pair, price in zip(trading_pairs, results):
            if isinstance(price, Exception):
                self.logger().warning(f"Failed to get last traded price for {trading_pair}: {price}")
                continue
            if price and price > 0:
                prices[trading_pair] = price
        return prices

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """
        Gets the last traded price for a trading pair.

        Prefers the RateOracle cache (set by MarketDataProvider) and falls back to a
        Gateway quote.

        :param trading_pair: The market trading pair
        :returns: The last traded price or 0 if not available
        """
        try:
            rate_oracle = RateOracle.get_instance()
            price = rate_oracle.get_pair_rate(trading_pair)
            if price and price > 0:
                return float(price)
        except Exception:
            pass
        # The oracle only holds pairs MarketDataProvider was asked to track, so a pair
        # priced on demand -- a pool just opened in a dashboard, a memecoin addressed by
        # mint -- finds nothing cached and used to fall straight through to 0. Quote it
        # instead: Gateway prices anything the configured swap provider can route.
        try:
            quoted = await self.get_quote_price(trading_pair, is_buy=True, amount=Decimal("1"))
            if quoted and quoted > 0:
                return float(quoted)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().debug(f"Could not quote a fallback price for {trading_pair}.", exc_info=True)
        return 0.0

    @staticmethod
    def _parse_dex_name(dex_name: str) -> tuple:
        """
        Parse dex_name into (dex, trading_type) tuple.

        The trading type is never defaulted: Gateway rejects a guessed one with a 400,
        and guessing "router" for e.g. "meteora" only surfaced at execution time — on
        the LP executor's close-out swap, with funds already exposed.

        Args:
            dex_name: DEX identifier in "name/type" form
                - "jupiter/router" -> ("jupiter", "router")
                - "orca/clmm" -> ("orca", "clmm")

        Returns:
            Tuple of (dex, trading_type)

        Raises:
            ValueError: if dex_name does not carry a trading type
        """
        if "/" not in dex_name:
            raise ValueError(
                f"Invalid swap provider '{dex_name}' - expected 'name/type' "
                "(e.g. 'jupiter/router', 'meteora/clmm')"
            )
        parts = dex_name.split("/", 1)
        return parts[0], parts[1]

    # ==================== SWAP OPERATIONS ====================

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            slippage_pct: Optional[Decimal] = None
    ) -> Optional[Decimal]:
        """
        Retrieves the volume weighted average price for a swap.

        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :param slippage_pct: Maximum allowed slippage percentage
        :return: The quote price.
        """
        base, quote = trading_pair.split("-")
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL

        if not self._swap_provider:
            raise ValueError("No swap provider configured for this network. Set swapProvider in Gateway network config.")

        dex, trading_type = self._parse_dex_name(self._swap_provider)

        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().quote_swap(
                network=self.network,
                chain=self.chain,
                dex=dex,
                trading_type=trading_type,
                base_asset=base,
                quote_asset=quote,
                amount=amount,
                side=side,
                slippage_pct=slippage_pct
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
    ) -> Decimal:
        """
        Retrieves the price required for an order of a given amount.
        """
        return await self.get_quote_price(trading_pair, is_buy, amount)

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
        :param kwargs: Additional parameters (dex_name, quote_id, slippage_pct, max_retries)
        """
        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        base, quote = trading_pair.split("-")

        # Check if order is already being tracked
        existing_order = self._order_tracker.fetch_order(order_id)
        if existing_order is not None:
            self.logger().debug(f"Order {order_id} already tracked, skipping")
        else:
            # Start tracking - order tracker will emit BuyOrderCreatedEvent when state transitions
            self.start_tracking_order(order_id=order_id,
                                      trading_pair=trading_pair,
                                      trade_type=trade_type,
                                      price=price,
                                      amount=amount)

        # Extract optional parameters
        quote_id = kwargs.get("quote_id")
        slippage_pct = kwargs.get("slippage_pct")
        max_retries = kwargs.get("max_retries", 10)
        # An explicit dex_name (e.g. the LP executor's configured swap_provider)
        # overrides the network's default provider — it used to be silently ignored.
        swap_provider = kwargs.get("dex_name") or self._swap_provider

        try:
            # Inside the try: a missing provider must fail the ORDER (via
            # _handle_operation_failure) — raising before this block left the order
            # tracked-but-stuck in OPEN forever with no failure event.
            if not swap_provider:
                raise ValueError(f"No swap provider configured for {self.network}.")

            dex, trading_type = self._parse_dex_name(swap_provider)

            async def execute_gateway_swap() -> Dict[str, Any]:
                if quote_id:
                    return await self._get_gateway_instance().execute_quote(
                        dex=dex,
                        network=self.network,
                        quote_id=quote_id,
                        wallet_address=self.address,
                        chain=self.chain,
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
                        chain=self.chain,
                        wallet_address=self.address,
                        slippage_pct=slippage_pct
                    )

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
        """Store swap result data by creating a TradeUpdate for proper fill tracking.

        ``amountIn``/``amountOut`` are Gateway's REALIZED amounts, derived from the
        wallet's on-chain pre/post token balance deltas for the settled transaction.
        They are what actually moved, which is not the amount that was requested:
        slippage and fees mean a swap for 62 base tokens may land 61.962753. Callers
        that spend the proceeds downstream (e.g. an LP open's ``base_amount``) must
        see the realized figure, or they will ask the chain for tokens that aren't
        there.

        Base and quote are assigned from the trade side rather than from the token
        identities, so this is independent of the quote asset (SOL, USDC, ...).

        One caveat: for an SPL token Gateway diffs the token balance exactly, but a
        NATIVE SOL leg is measured as a lamport delta that also absorbs the tx fee
        and any rent. So on a SOL-quoted pair the quote leg carries a few thousand
        lamports of noise, and on a SOL-BASE pair the base leg does. The error is
        gas-sized (~1e-5 SOL) and, for a buy, understates what arrived - which is
        the safe direction for anything that spends the proceeds.
        """
        data = order_result.get("data", {})
        amount_in = Decimal(str(data.get("amountIn", "0")))
        amount_out = Decimal(str(data.get("amountOut", "0")))

        # Gateway only populates `data` once the swap is CONFIRMED. Without this
        # guard a pending or failed swap yields zeroed amounts and would still be
        # forced to FILLED below, reporting a phantom 0-amount fill. Leave the order
        # OPEN so update_order_status() resolves it from the chain instead.
        if amount_in <= 0 or amount_out <= 0:
            self.logger().warning(
                f"Swap {order_id} ({transaction_hash}) returned no realized amounts "
                f"(status={order_result.get('status')!r}, amountIn={amount_in}, amountOut={amount_out}); "
                f"not marking as filled. Order stays open for status polling."
            )
            return

        if trade_type == TradeType.SELL:
            executed_price = amount_out / amount_in
        else:
            executed_price = amount_in / amount_out

        tracked_order = self._order_tracker.fetch_order(order_id)
        if not tracked_order:
            return

        fee = Decimal(str(data.get("fee", 0)))
        fee_asset = self._native_currency
        trade_fee = AddedToCostTradeFee(flat_fees=[TokenAmount(fee_asset, fee)])

        # A SELL sends base and receives quote; a BUY is the mirror image.
        if trade_type == TradeType.SELL:
            fill_base_amount, fill_quote_amount = amount_in, amount_out
        else:
            fill_base_amount, fill_quote_amount = amount_out, amount_in

        trade_update = TradeUpdate(
            trade_id=transaction_hash,
            client_order_id=order_id,
            exchange_order_id=transaction_hash,
            trading_pair=trading_pair,
            fill_timestamp=self.current_timestamp,
            fill_price=executed_price,
            fill_base_amount=fill_base_amount,
            fill_quote_amount=fill_quote_amount,
            fee=trade_fee
        )

        self.logger().info(
            f"Processing trade update for {order_id}: requested={amount}, "
            f"realized fill_amount={fill_base_amount}, fill_price={executed_price}, "
            f"trade_id={transaction_hash}"
        )

        # Process order update to mark order as FILLED (triggers OrderCompleted event)
        order_update = OrderUpdate(
            client_order_id=order_id,
            exchange_order_id=transaction_hash,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FILLED,
        )
        self._order_tracker.process_order_update(order_update)

        # Process trade update (triggers OrderFilled event with fill details)
        self._order_tracker.process_trade_update(trade_update)

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

        # Read the code off the exception when Gateway gave us one, instead of
        # looking for it in the rendered message.
        is_timeout_error = extract_error_code(error) == self.TRANSACTION_TIMEOUT_CODE

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
            self.logger().warning(f"Non-retryable error for {order_id}: {str(error)[:100]}")
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
                chain=self.chain,
                network=self.network,
                trading_type=trading_type,
                connector=dex_name
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
                chain=self.chain,
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

    async def get_pool_info(
        self,
        trading_pair: str,
        dex_name: str,
        trading_type: str = "clmm"
    ) -> Optional[Union[AMMPoolInfo, CLMMPoolInfo]]:
        """
        Get pool information for a trading pair.

        :param trading_pair: Trading pair (e.g., "SOL-USDC")
        :param dex_name: DEX protocol name (e.g., "orca", "meteora")
        :param trading_type: Trading type (e.g., "clmm", "amm"). Defaults to "clmm".
        :return: Pool info object or None if not found
        """
        try:
            pool_address = await self.get_pool_address(trading_pair, dex_name, trading_type)
            if not pool_address:
                return None

            return await self.get_pool_info_by_address(pool_address, dex_name, trading_type)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error getting pool info for {trading_pair}: {e}")
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
                chain=self.chain,
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
                chain=self.chain,
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
                if transaction_result.get(TX_DATA_UNAVAILABLE):
                    # The open landed on-chain but its response data is unrecoverable.
                    # Record the gap rather than writing a blank position address and
                    # zero amounts, which the caller cannot tell apart from a failure —
                    # the position is LIVE and must not be abandoned.
                    self.logger().error(
                        f"CLMM open position {transaction_hash} confirmed on-chain but Gateway's "
                        "response data is unavailable: the position address and deposited amounts "
                        "must be recovered from chain state."
                    )
                    self._lp_orders_metadata[order_id]["data_unavailable"] = True
                else:
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
        position_address: Optional[str] = None,
        max_retries: int = 10,
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

        async def execute_add_liquidity() -> Dict[str, Any]:
            return await self._get_gateway_instance().amm_add_liquidity(
                network=self.network,
                chain=self.chain,
                wallet_address=self.address,
                pool_address=pool_address,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                dex=dex_name,
                trading_type=trading_type,
                slippage_pct=slippage_pct,
                position_address=position_address,
            )

        try:
            # Same chokepoint as the CLMM verbs: a status 0 (broadcast, unconfirmed) or
            # -1 (landed and failed) response carries a signature too, so returning it
            # unchecked would report an unlanded or reverted add as a success.
            transaction_result = await self._execute_with_retry(
                operation=execute_add_liquidity,
                operation_name=f"AMM add liquidity on {trading_pair}",
                max_retries=max_retries,
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
        :param position_address: The address of the position. Required for CLMM, and for
            AMMs whose LP is non-fungible (Meteora DAMM v2 positions are NFTs and a wallet
            may hold several per pool); ignored by fungible-LP AMMs.
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
            safe_ensure_future(self._amm_remove_liquidity(trade_type, order_id, trading_pair, percentage, dex_name=dex_name, trading_type=trading_type, position_address=position_address, **request_args))
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
                chain=self.chain,
                wallet_address=self.address,
                position_address=position_address,
                dex=_dex_name,
                trading_type=_trading_type,
                fail_silently=fail_silently
            )

        try:
            # Close retry policy lives in the LP executor's CLOSING loop, which passes
            # max_retries=0 for a single attempt per re-entry and reconciles a
            # landed-but-unconfirmed attempt against fresh position state before
            # re-submitting — a blind retry here cannot do that check.
            transaction_result = await self._execute_with_retry(
                operation=execute_close_position,
                operation_name=f"CLMM close position {position_address}",
                max_retries=max_retries,
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                if transaction_result.get(TX_DATA_UNAVAILABLE):
                    # The close landed but its response data is unrecoverable. Writing the
                    # six financial keys as 0 here would silently book real collected fees
                    # and a real rent refund as zero, so record the gap instead and let the
                    # caller report incomplete accounting.
                    self.logger().error(
                        f"CLMM close position {transaction_hash} confirmed on-chain but Gateway's "
                        "response data is unavailable: collected fees, removed amounts and rent "
                        "refund could NOT be booked for this close."
                    )
                    self._lp_orders_metadata[order_id]["data_unavailable"] = True
                else:
                    data = transaction_result.get("data", {})
                    # ClosePositionResponse.data declares the collected-fee and rent keys
                    # (unlike RemoveLiquidityResponse) — the LP executor books them from
                    # this metadata, so dropping them would zero close-time fee/rent PnL.
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
        max_retries: int = 10,
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

        async def execute_remove_liquidity() -> Dict[str, Any]:
            return await self._get_gateway_instance().clmm_remove_liquidity(
                network=self.network,
                chain=self.chain,
                wallet_address=self.address,
                position_address=position_address,
                percentage=percentage,
                dex=dex_name,
                trading_type=trading_type,
                fail_silently=fail_silently
            )

        try:
            # Same chokepoint as _clmm_add_liquidity / _clmm_close_position: a status 0
            # (broadcast, unconfirmed) or -1 (landed and failed) response also carries a
            # signature, so returning it unchecked booked an unlanded or reverted removal
            # as a completed one.
            transaction_result = await self._execute_with_retry(
                operation=execute_remove_liquidity,
                operation_name=f"CLMM remove liquidity from {position_address}",
                max_retries=max_retries,
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                if transaction_result.get(TX_DATA_UNAVAILABLE):
                    self.logger().error(
                        f"CLMM remove liquidity {transaction_hash} confirmed on-chain but Gateway's "
                        "response data is unavailable: removed amounts could NOT be booked."
                    )
                    self._lp_orders_metadata[order_id]["data_unavailable"] = True
                else:
                    data = transaction_result.get("data", {})
                    # RemoveLiquidityResponse.data carries only fee + removed amounts.
                    # Fee-collected/rent keys exist only on the CLOSE response — reading
                    # them here always yielded 0 and masqueraded as "no fees collected".
                    self._lp_orders_metadata[order_id].update({
                        "base_amount": Decimal(str(data.get("baseTokenAmountRemoved", 0))),
                        "quote_amount": Decimal(str(data.get("quoteTokenAmountRemoved", 0))),
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
        position_address: Optional[str] = None,
        fail_silently: bool = False,
        max_retries: int = 10,
    ):
        """Removes liquidity from an AMM pool."""
        pool_address = await self.get_pool_address(trading_pair, dex_name=dex_name, trading_type=trading_type)
        if not pool_address:
            raise ValueError(f"Could not find pool for {trading_pair}")

        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  order_type=OrderType.AMM_REMOVE)

        async def execute_remove_liquidity() -> Dict[str, Any]:
            return await self._get_gateway_instance().amm_remove_liquidity(
                network=self.network,
                chain=self.chain,
                wallet_address=self.address,
                pool_address=pool_address,
                percentage=percentage,
                dex=dex_name,
                trading_type=trading_type,
                position_address=position_address,
                fail_silently=fail_silently
            )

        try:
            # Same chokepoint as the CLMM verbs — see _clmm_remove_liquidity.
            transaction_result = await self._execute_with_retry(
                operation=execute_remove_liquidity,
                operation_name=f"AMM remove liquidity on {trading_pair}",
                max_retries=max_retries,
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
        """Cached position info for display/analytics consumers.

        WARNING: the TTL cache stores None ("position gone") like any other value,
        so a single 404 is served for up to 5s of subsequent calls. Anything that
        makes an existence DECISION from this signal (close pre-flight, external-
        close detection) must use get_position_info_fresh instead — otherwise one
        read can masquerade as several independent confirmations.
        """
        return await self.get_position_info_fresh(
            trading_pair=trading_pair,
            dex_name=dex_name,
            trading_type=trading_type,
            position_address=position_address,
        )

    async def get_position_info_fresh(
        self,
        trading_pair: str,
        dex_name: str,
        trading_type: str = "clmm",
        position_address: Optional[str] = None
    ) -> Union[AMMPositionInfo, CLMMPositionInfo, None]:
        """Uncached position info read.

        Contract: returns None only when Gateway definitively reports the position
        does not exist on-chain; transient errors (RPC/network/5xx, unrelated 404s
        like a missing route or wallet) raise instead of being swallowed into None.
        """
        try:
            tokens = trading_pair.split("-")
            if len(tokens) != 2:
                raise ValueError(f"Invalid trading pair format: {trading_pair}")

            if trading_type == "clmm":
                if position_address is None:
                    raise ValueError("position_address is required for CLMM positions")

                resp: Dict[str, Any] = await self._get_gateway_instance().clmm_position_info(
                    network=self.network,
                    chain=self.chain,
                    position_address=position_address,
                    dex=dex_name,
                    trading_type=trading_type,
                )
                return CLMMPositionInfo(**resp) if resp else None

            elif trading_type == "amm":
                resp: Dict[str, Any] = await self._get_gateway_instance().amm_position_info(
                    network=self.network,
                    chain=self.chain,
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
            error_msg = str(e).lower()
            # None means "the position definitively does not exist on-chain". Match only
            # position-specific Gateway messages: the HTTP client stamps "(Not Found)" on
            # EVERY 404 (missing route after a redeploy, missing wallet file, ...), so a
            # bare "not found" check would report a live position as gone. Transient
            # errors must NOT be swallowed into None: callers such as
            # LPExecutor._close_position interpret None as "already closed", and a
            # swallowed transient error would silently abandon a live position.
            # A GatewayError also carries the HTTP status: require the 404 a missing
            # position returns, so a 500 whose prose happens to name the position (or a
            # transport error carrying no status at all) still raises.
            status = e.status if isinstance(e, GatewayError) else None
            is_position_gone = (
                "position not found" in error_msg
                or "position closed" in error_msg
                or "position does not exist" in error_msg
            )
            if is_position_gone and status in (None, 404):
                self.logger().info(
                    f"Position info for {addr_info} on {dex_name}/{trading_type}: position does not exist ({e})"
                )
                return None
            self.logger().network(
                f"Error fetching position info for {addr_info} on {dex_name}/{trading_type}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            raise

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
                    chain=self.chain,
                    wallet_address=self.address,
                    dex=dex_name,
                    trading_type=trading_type,
                )
            else:
                if not pool_address:
                    self.logger().warning("AMM position fetching requires a pool address")
                    return []

                pool_resp = await self._get_gateway_instance().pool_info(
                    network=self.network,
                    chain=self.chain,
                    pool_address=pool_address,
                    dex=dex_name,
                    trading_type=trading_type,
                )

                if not pool_resp:
                    return []

                resp = await self._get_gateway_instance().amm_position_info(
                    network=self.network,
                    chain=self.chain,
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
