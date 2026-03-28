"""
SwapExecutor - Executes single swaps on Gateway AMM connectors.

Provides robust retry logic for handling transaction timeouts and failures
on Gateway connectors (e.g., Jupiter, Raydium).

Uses GatewaySwap connector when available for proper order tracking and TradeFill events.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.gateway.gateway_swap import GatewaySwap
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.gateway_retry import GatewayRetryMixin, RetryAction
from hummingbot.strategy_v2.executors.swap_executor.data_types import SwapExecutorConfig, SwapExecutorStates
from hummingbot.strategy_v2.models.executors import CloseType


class SwapExecutor(ExecutorBase, GatewayRetryMixin):
    """
    Executor for single swap operations on Gateway AMM connectors.

    Features:
    - Direct await of swap operations (no fire-and-forget)
    - Retry logic for transaction timeouts and failures
    - State machine tracking execution progress
    - Integration with executor framework for monitoring

    State Flow:
        NOT_STARTED -> EXECUTING -> COMPLETED (success)
                                 -> FAILED (max retries)
    """
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @staticmethod
    def parse_network(network: str) -> tuple:
        """Parse network string into chain and network_name.

        Args:
            network: Network string like "solana-mainnet-beta" or "ethereum-mainnet"

        Returns:
            Tuple of (chain, network_name)
        """
        parts = network.split("-", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return parts[0], "mainnet"

    def __init__(
        self,
        strategy: StrategyV2Base,
        config: SwapExecutorConfig,
        update_interval: float = 1.0,
        max_retries: int = 10,
    ):
        """
        Initialize SwapExecutor.

        Args:
            strategy: The strategy instance
            config: SwapExecutorConfig with swap parameters
            update_interval: Interval between control_task calls
            max_retries: Maximum retry attempts for failed swaps
        """
        # Parse network to get chain
        self._chain, self._network_name = self.parse_network(config.network)

        # Use swap_providers from config if specified
        connector_names = config.swap_providers or []
        super().__init__(strategy, connector_names, config, update_interval)
        self.init_retry_state(max_retries)
        self.config: SwapExecutorConfig = config
        self._state = SwapExecutorStates.NOT_STARTED
        self._executed_amount: Decimal = Decimal("0")
        self._executed_price: Decimal = Decimal("0")
        self._tx_fee: Decimal = Decimal("0")
        self._exchange_order_id: Optional[str] = None  # Transaction hash/signature
        self._selected_provider: Optional[str] = None  # Provider used for multi-provider comparison
        self._wallet_address: Optional[str] = None  # Populated on first execution

    async def control_task(self):
        """
        Main control loop implementing state machine.

        Transitions:
        - NOT_STARTED: Begin executing swap
        - EXECUTING: Continue/retry swap if needed
        - COMPLETED: Stop executor with success
        - FAILED: Stop executor with failure
        """
        match self._state:
            case SwapExecutorStates.NOT_STARTED:
                self._state = SwapExecutorStates.EXECUTING
                await self._execute_swap()

            case SwapExecutorStates.EXECUTING:
                # Check if max retries reached (safety check for edge cases)
                if self._max_retries_reached:
                    self._state = SwapExecutorStates.FAILED
                else:
                    await self._execute_swap()

            case SwapExecutorStates.COMPLETED:
                self.close_type = CloseType.COMPLETED
                self.stop()

            case SwapExecutorStates.FAILED:
                self.close_type = CloseType.FAILED
                self.stop()

    def _get_connector(self, provider: str) -> Optional[GatewaySwap]:
        """Get connector for provider if available."""
        # Try exact match first
        if provider in self.connectors:
            return self.connectors[provider]
        # Try matching by connector name pattern (e.g., "jupiter/router_solana_mainnet-beta")
        for name, conn in self.connectors.items():
            if name.startswith(provider):
                return conn
        return None

    async def _fetch_quotes(self, gateway, base: str, quote: str, amount: Decimal, network: str, swap_providers: List[str]) -> List[Dict]:
        """
        Fetch quotes from all swap_providers in parallel.

        Args:
            gateway: Gateway instance
            base: Base token symbol
            quote: Quote token symbol
            amount: Amount to swap
            network: Network name
            swap_providers: List of providers to fetch quotes from

        Returns:
            List of dicts with provider, quote, and pool_address for successful quotes
        """
        async def get_quote_for_provider(provider: str) -> Optional[Dict]:
            try:
                # Parse provider name: "meteora/clmm" -> connector="meteora", type="clmm"
                pool_address = None
                if "/" in provider:
                    connector_base, connector_type = provider.split("/", 1)
                else:
                    connector_base = provider
                    connector_type = "router"

                # Look up pool address for CLMM/AMM providers
                if connector_type in ("clmm", "amm"):
                    pool_info = await gateway.get_pool(
                        trading_pair=self.config.trading_pair,
                        connector=connector_base,
                        network=network,
                        type=connector_type
                    )
                    pool_address = pool_info.get("address")
                    if not pool_address:
                        self.logger().debug(f"No pool found for {provider}")
                        return None

                # Fetch quote
                quote_result = await gateway.quote_swap(
                    network=network,
                    connector=provider,
                    base_asset=base,
                    quote_asset=quote,
                    amount=amount,
                    side=self.config.side,
                    slippage_pct=self.config.slippage_pct,
                    pool_address=pool_address,
                    fail_silently=True
                )
                if quote_result and "error" not in quote_result:
                    self.logger().info(
                        f"Quote from {provider}: price={quote_result.get('price')}, "
                        f"amountIn={quote_result.get('amountIn')}, amountOut={quote_result.get('amountOut')}"
                    )
                    return {"provider": provider, "quote": quote_result, "pool_address": pool_address}
            except Exception as e:
                self.logger().debug(f"Quote from {provider} failed: {e}")
            return None

        # Fetch all quotes in parallel
        tasks = [get_quote_for_provider(p) for p in swap_providers]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    def _select_best_quote(self, quotes: List[Dict]) -> Optional[Dict]:
        """
        Select best quote based on trade side.

        For BUY: lower price is better (pay less quote to get base)
        For SELL: higher price is better (get more quote for base)

        Args:
            quotes: List of quote dicts from _fetch_quotes

        Returns:
            Best quote dict or None if no valid quotes
        """
        if not quotes:
            return None

        def get_price(q):
            return Decimal(str(q["quote"].get("price", 0)))

        if self.config.side == TradeType.BUY:
            return min(quotes, key=lambda q: get_price(q))
        else:
            return max(quotes, key=lambda q: get_price(q))

    async def _get_pool_address_for_provider(self, gateway, provider: str) -> Optional[str]:
        """
        Get pool address for CLMM/AMM providers.

        Args:
            gateway: Gateway HTTP client
            provider: Provider name (e.g., "meteora/clmm", "jupiter/router")

        Returns:
            Pool address if provider is CLMM/AMM, None for routers
        """
        if "/" in provider:
            connector_base, connector_type = provider.split("/", 1)
        else:
            connector_base = provider
            connector_type = "router"

        # Only CLMM/AMM providers need pool address lookup
        if connector_type not in ("clmm", "amm"):
            return None

        try:
            pool_info = await gateway.get_pool(
                trading_pair=self.config.trading_pair,
                connector=connector_base,
                network=self._network_name,
                type=connector_type
            )
            return pool_info.get("address")
        except Exception as e:
            self.logger().debug(f"Pool lookup failed for {provider}: {e}")
            return None

    async def _execute_swap(self):
        """Execute the swap operation with retry logic."""
        # Get gateway instance
        gateway = GatewayHttpClient.get_instance()

        # Get wallet address if not already cached
        if not self._wallet_address:
            wallet_address, error = await gateway.get_default_wallet(self._chain)
            if error or not wallet_address:
                self.logger().error(error or f"No default wallet configured for chain {self._chain}")
                self._state = SwapExecutorStates.FAILED
                return
            self._wallet_address = wallet_address

        # Parse trading pair
        base, quote = self.config.trading_pair.split("-")
        amount = self.config.amount

        try:
            # Determine swap providers to use
            swap_providers = self.config.swap_providers or []
            if not swap_providers:
                # Fetch default swapProvider from network config
                try:
                    network_config = await gateway.get_configuration(self.config.network)
                    default_provider = network_config.get("swapProvider")
                    if default_provider:
                        swap_providers = [default_provider]
                        self.logger().info(f"Using default swapProvider from config: {default_provider}")
                    else:
                        self.logger().error(f"No swapProvider in network config for {self.config.network}")
                        self._state = SwapExecutorStates.FAILED
                        return
                except Exception as e:
                    self.logger().error(f"Failed to get network config for {self.config.network}: {e}")
                    self._state = SwapExecutorStates.FAILED
                    return

            # If single provider, execute directly without quoting (faster)
            # If multiple providers, fetch quotes and select best
            if len(swap_providers) == 1:
                selected_provider = swap_providers[0]
                selected_pool_address = await self._get_pool_address_for_provider(gateway, selected_provider)
                self._selected_provider = selected_provider
                self.logger().info(f"Executing directly on {selected_provider} (single provider, no quote)")
            else:
                # Fetch quotes from all providers in parallel
                quotes = await self._fetch_quotes(gateway, base, quote, amount, self._network_name, swap_providers)
                best = self._select_best_quote(quotes)

                if not best:
                    self.logger().error("No valid quotes from any swap provider")
                    self._state = SwapExecutorStates.FAILED
                    return

                selected_provider = best["provider"]
                selected_pool_address = best.get("pool_address")
                self._selected_provider = selected_provider
                self.logger().info(
                    f"Selected {selected_provider} with price {best['quote'].get('price')} "
                    f"(from {len(quotes)} quotes)"
                )

            self.logger().info(
                f"Executing swap: {self.config.side.name} {amount} {base} "
                f"on {selected_provider}"
            )

            # Execute swap via direct gateway call
            await self._execute_via_gateway(gateway, selected_provider, base, quote, amount, selected_pool_address)

        except Exception as e:
            # Handle failure with retry logic
            action = self.handle_gateway_failure(
                error=e,
                operation=f"SWAP {self.config.side.name}",
                trading_pair=self.config.trading_pair,
                signature=self._exchange_order_id,
            )

            # Handle non-retryable errors - transition to FAILED immediately
            if action in (RetryAction.STOP, RetryAction.FAIL_IMMEDIATE):
                self._state = SwapExecutorStates.FAILED

    async def _execute_via_gateway(self, gateway, provider: str, base: str, quote: str,
                                   amount: Decimal, pool_address: Optional[str]):
        """Execute swap via direct gateway call."""
        order_result = await gateway.execute_swap(
            connector=provider,
            base_asset=base,
            quote_asset=quote,
            side=self.config.side,
            amount=amount,
            network=self._network_name,
            wallet_address=self._wallet_address,
            pool_address=pool_address
        )

        transaction_hash = order_result.get("signature")
        if not transaction_hash:
            raise ValueError("No transaction signature in response")

        self._exchange_order_id = transaction_hash

        # Extract executed amounts from the response
        data = order_result.get("data", {})
        amount_in = Decimal(str(data.get("amountIn", "0")))
        amount_out = Decimal(str(data.get("amountOut", "0")))

        # For SELL: amountIn=base sold, amountOut=quote received
        # For BUY: amountIn=quote paid, amountOut=base received
        if self.config.side == TradeType.SELL:
            self._executed_amount = amount_in if amount_in > 0 else amount
            if amount_in > 0 and amount_out > 0:
                self._executed_price = amount_out / amount_in
        else:  # BUY
            self._executed_amount = amount_out if amount_out > 0 else amount
            if amount_in > 0 and amount_out > 0:
                self._executed_price = amount_in / amount_out

        # Extract fee
        fee_amount = Decimal(str(data.get("fee", order_result.get("fee", "0"))))
        self._tx_fee = fee_amount

        # Emit OrderFilledEvent so markets_recorder creates TradeFill
        self._emit_order_filled_event(
            provider=provider,
            base=base,
            quote=quote,
            transaction_hash=transaction_hash,
            fee_amount=fee_amount
        )

        # Success
        self._state = SwapExecutorStates.COMPLETED
        self.reset_retry_state()
        self.logger().info(
            f"Swap completed: {self.config.side.name} {self._executed_amount} "
            f"at {self._executed_price}, tx={transaction_hash[:16]}..."
        )

    def _emit_order_filled_event(self, provider: str, base: str, quote: str,
                                 transaction_hash: str, fee_amount: Decimal):
        """Emit OrderFilledEvent so markets_recorder creates TradeFill."""
        # Get connector to emit event through
        connector = self._get_connector(provider)
        if not connector:
            self.logger().warning(f"No connector for {provider}, TradeFill will not be recorded")
            return

        # Build trade fee - use connector's native currency (e.g., "SOL" not "SOLANA")
        fee_token = connector.native_currency or self._chain.upper()
        trade_fee = AddedToCostTradeFee(
            flat_fees=[TokenAmount(fee_token, fee_amount)]
        )

        # Create unique order ID for this swap
        timestamp = self._strategy.current_timestamp
        if timestamp is None or timestamp != timestamp:  # NaN check
            timestamp = 0
        order_id = f"swap-{base}-{quote}-{int(timestamp * 1000)}"

        # Emit OrderFilledEvent
        connector.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                timestamp=timestamp,
                order_id=order_id,
                trading_pair=self.config.trading_pair,
                trade_type=self.config.side,
                order_type=OrderType.AMM_SWAP,
                price=self._executed_price,
                amount=self._executed_amount,
                trade_fee=trade_fee,
                exchange_trade_id=transaction_hash,
                leverage=1,
                position=PositionAction.NIL.value,
                exchange_order_id=transaction_hash,
            ),
        )
        self.logger().debug(f"Emitted OrderFilledEvent for swap: {order_id}")

    def early_stop(self, keep_position: bool = False):
        """
        Stop the executor early.

        For swaps, keep_position is ignored since swaps are atomic -
        they either complete or don't.
        """
        if self._state in (SwapExecutorStates.NOT_STARTED, SwapExecutorStates.EXECUTING):
            self.close_type = CloseType.EARLY_STOP
            self._state = SwapExecutorStates.FAILED
            self.stop()

    # Required ExecutorBase methods

    @property
    def filled_amount_quote(self) -> Decimal:
        """Returns the filled amount in quote currency."""
        return self._executed_amount * self._executed_price

    def get_net_pnl_quote(self) -> Decimal:
        """
        Returns net P&L in quote currency.

        For single swaps, P&L is not tracked as there's no entry/exit pair.
        Returns 0.
        """
        return Decimal("0")

    def get_net_pnl_pct(self) -> Decimal:
        """Returns net P&L as percentage. Always 0 for single swaps."""
        return Decimal("0")

    def get_cum_fees_quote(self) -> Decimal:
        """Returns cumulative transaction fees."""
        return self._tx_fee

    async def validate_sufficient_balance(self):
        """
        Validate sufficient balance for the swap.

        Gateway handles balance validation during execute_swap,
        so we don't need to pre-validate here.
        """
        pass

    def get_custom_info(self) -> Dict:
        """Return custom info for reporting."""
        return {
            "state": self._state.value,
            "network": self.config.network,
            "side": self.config.side.name,
            "amount": float(self.config.amount),
            "executed_amount": float(self._executed_amount),
            "executed_price": float(self._executed_price),
            "tx_fee": float(self._tx_fee),
            "tx_hash": self._exchange_order_id,
            "exchange_order_id": self._exchange_order_id,
            "current_retries": self._current_retries,
            "max_retries_reached": self._max_retries_reached,
            "swap_provider": self._selected_provider,
        }
