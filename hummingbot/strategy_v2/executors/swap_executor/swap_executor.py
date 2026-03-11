"""
SwapExecutor - Executes single swaps on Gateway AMM connectors.

Provides robust retry logic for handling transaction timeouts and failures
on Gateway connectors (e.g., Jupiter, Raydium).
"""
import logging
from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
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
        connectors = [config.connector_name]
        super().__init__(strategy, connectors, config, update_interval)
        self.init_retry_state(max_retries)
        self.config: SwapExecutorConfig = config
        self._state = SwapExecutorStates.NOT_STARTED
        self._executed_amount: Decimal = Decimal("0")
        self._executed_price: Decimal = Decimal("0")
        self._tx_fee: Decimal = Decimal("0")
        self._active_order_id: Optional[str] = None
        self._exchange_order_id: Optional[str] = None  # Transaction hash/signature

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
                # Retry if not max retries reached
                if not self._max_retries_reached:
                    await self._execute_swap()

            case SwapExecutorStates.COMPLETED:
                self.close_type = CloseType.COMPLETED
                self.stop()

            case SwapExecutorStates.FAILED:
                self.close_type = CloseType.FAILED
                self.stop()

    async def _execute_swap(self):
        """Execute the swap operation with retry logic."""
        connector = self.connectors.get(self.config.connector_name)
        if not connector:
            self.logger().error(f"Connector {self.config.connector_name} not found")
            self._state = SwapExecutorStates.FAILED
            return

        # Generate order_id for tracking
        order_id = connector.create_market_order_id(self.config.side, self.config.trading_pair)
        self._active_order_id = order_id

        # Parse trading pair
        base, quote = self.config.trading_pair.split("-")
        amount = connector.quantize_order_amount(self.config.trading_pair, self.config.amount)

        # Start tracking the order
        connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.config.trading_pair,
            trade_type=self.config.side,
            price=Decimal("0"),
            amount=amount
        )

        try:
            self.logger().info(
                f"Executing swap: {self.config.side.name} {amount} {base} "
                f"on {self.config.connector_name}, order_id={order_id}"
            )

            # Execute swap directly via gateway
            gateway = connector._get_gateway_instance()
            order_result = await gateway.execute_swap(
                connector=connector.connector_name,
                base_asset=base,
                quote_asset=quote,
                side=self.config.side,
                amount=amount,
                network=connector.network,
                wallet_address=connector.address
            )

            transaction_hash = order_result.get("signature")
            if not transaction_hash:
                raise ValueError("No transaction signature in response")

            self._exchange_order_id = transaction_hash

            # Update order state in connector's tracker
            connector.update_order_from_hash(order_id, self.config.trading_pair, transaction_hash, order_result)

            # Extract executed amounts from the response
            # Gateway returns amounts in data field as amountIn/amountOut
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
            self._tx_fee = Decimal(str(data.get("fee", order_result.get("fee", "0"))))

            # Success - transition to completed
            self._state = SwapExecutorStates.COMPLETED
            self.reset_retry_state()
            self._active_order_id = None

            self.logger().info(
                f"Swap completed: {self.config.side.name} {self._executed_amount} "
                f"at {self._executed_price}, tx={transaction_hash[:16]}..."
            )

        except Exception as e:
            # Handle failure with retry logic
            action = self.handle_gateway_failure(
                error=e,
                operation=f"SWAP {self.config.side.name}",
                trading_pair=self.config.trading_pair,
                signature=self._exchange_order_id,
                recoverable_errors=["Price has moved", "Slippage too high"],
            )

            # Update order state to failed in connector's tracker
            if connector and order_id:
                order_update = OrderUpdate(
                    client_order_id=order_id,
                    trading_pair=self.config.trading_pair,
                    update_timestamp=self._strategy.current_timestamp,
                    new_state=OrderState.FAILED
                )
                connector._order_tracker.process_order_update(order_update)

            if action == RetryAction.STOP:
                self._state = SwapExecutorStates.FAILED

            self._active_order_id = None

    def early_stop(self, keep_position: bool = False):
        """
        Stop the executor early.

        For swaps, keep_position is ignored since swaps are atomic -
        they either complete or don't.
        """
        if self._state == SwapExecutorStates.EXECUTING and not self._active_order_id:
            # Not actively executing, can stop immediately
            self.close_type = CloseType.EARLY_STOP
            self._state = SwapExecutorStates.FAILED
            self.stop()
        elif self._state in (SwapExecutorStates.NOT_STARTED,):
            self.close_type = CloseType.EARLY_STOP
            self._state = SwapExecutorStates.FAILED
            self.stop()
        # If actively executing, let the current operation complete

    # Required ExecutorBase methods

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
            "side": self.config.side.name,
            "amount": float(self.config.amount),
            "executed_amount": float(self._executed_amount),
            "executed_price": float(self._executed_price),
            "tx_fee": float(self._tx_fee),
            "tx_hash": self._exchange_order_id,
            "exchange_order_id": self._exchange_order_id,
            "current_retries": self._current_retries,
            "max_retries_reached": self._max_retries_reached,
        }
